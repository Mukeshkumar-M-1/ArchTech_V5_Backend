# How System Prompts Are Created and Dynamically Managed

## The Big Idea

The system prompt is not a single string. It's an array of blocks assembled from multiple pieces — some static (never change), some dynamic (change per turn), some cached per session. It's split into a prefix (the "who you are" part) and tail (the "here's what's happening now" part).

---

## 1. The Assembly Pipeline — Three Sources

Three independent pieces are fetched at session start (`queryContext.ts:44-74`):

```
fetchSystemPromptParts()
  │
  ├─► getSystemPrompt(tools, model)     → The main prompt body (~3K-5K tokens)
  │      static blocks + dynamic blocks
  │
  ├─► getUserContext()                  → CLAUDE.md + today's date
  │      injected as synthetic user message before each API call
  │
  └─► getSystemContext()                → Git status (branch, uncommitted changes, recent commits)
         appended to system prompt array
```

`getUserContext()` and `getSystemContext()` are memoized (cached for the session lifecycle) — they run once and are reused every turn.

---

## 2. The System Prompt Structure — Static vs Dynamic

The system prompt array is built by `getSystemPrompt()` and has a critical divider — the `__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__` marker. Everything before it is static; everything after it is dynamic.

```
┌─── STATIC (Cacheable) ───────────────────────────────┐
│                                                        │
│  "You are Claude Code, Anthropic's official CLI..."   │  ← CLI sysprompt prefix
│                                                        │
│  # Simple introduction                                │  ← Identity
│  # System sections                                    │  ← Rules, constraints
│  # Doing tasks                                        │  ← "Do not add features..."
│  # Actions                                            │  ← How to use tools
│  # Using your tools                                   │  ← Tool descriptions (based on enabled tools)
│  # Tone and style                                     │  ← Communication guidance
│  # Output efficiency                                  │  ← How to communicate
│                                                        │
│  __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__ ← DIVIDER         │
│                                                        │
└────────────────────────────────────────────────────────┘

┌─── DYNAMIC (Recomputed, with selective caching) ─────┐
│                                                        │
│  session_guidance    ← Tool-specific guidance          │
│  memory              ← Memory file content             │
│  ant_model_override  ← Ant-internal config            │
│  env_info_simple     ← Git status, OS info            │
│  language            ← User language preference        │
│  output_style        ← Custom output style config      │
│  mcp_instructions    ← MCP server instructions ◄UNCACHED│  ← Changes every turn!
│  scratchpad          ← Scratchpad instructions         │
│  frc                 ← Function result clearing        │
│  summarize_tool_results ← Summarization guidance      │
│  token_budget        ← Token budget instructions       │
│  brief               ← Kairos brief (if enabled)      │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## 3. How the Dynamic Registry Works

Each dynamic block is defined as a `systemPromptSection` (`prompts.ts:581-633`):

```typescript
systemPromptSection('memory', () => loadMemoryPrompt())
DANGEROUS_uncachedSystemPromptSection('mcp_instructions', () => getMcpInstructionsSection(mcpClients))
```

The registry has two types:

- **`systemPromptSection(name, computeFn)`** — Computed once, cached in `STATE.systemPromptSectionCache`, reused on every turn
- **`DANGEROUS_uncachedSystemPromptSection(name, computeFn, reason)`** — Recomputed on every single API call because the data changes mid-session (MCP servers connect/disconnect)

`resolveSystemPromptSections()` (`prompts.ts:636-637`) iterates all sections, calls the compute function, and caches the result. The cache is cleared on `/clear` or `/compact`.

---

## 4. Prompt Caching — The Three Cache Scopes

The function `splitSysPromptPrefix()` converts the system prompt array into blocks with cache scopes:

| Block | Cache Scope | What It Means |
|-------|-------------|---------------|
| Attribution header | `null` | Never cached (unique per session) |
| CLI sysprompt prefix | `null` | Never cached (different per mode) |
| Static blocks (before boundary) | `global` | Shared across ALL users/sessions |
| Dynamic blocks (after boundary) | `null` | Never cached (changes per session) |
| MCP instructions | `org` | Scoped to your organization only |

**Why this matters for performance:**

- **`global` scope** = Anthropic's API caches the static prefix for everyone. If you're the first person to send a request, it gets computed. Everyone else gets a cache hit — the API doesn't need to re-process the same 3K tokens of "You are Claude Code..." every single time.
- **`org` scope** = Cached within your organization.
- **`null` scope** = Always recomputed from scratch.

This is why only MCP instructions are marked as `DANGEROUS_uncached` — MCP servers are the only thing that actually changes frequently enough to warrant busting the cache every turn. Everything else is either truly static (the "who you are" part) or session-scoped (the dynamic part is `null` scope anyway, so caching it globally wouldn't help).

---

## 5. How the System Prompt Changes Between Turns

Here's the surprising part: the system prompt changes on every turn, but only the dynamic part changes.

```
Turn 1:
  Static: "You are Claude Code..." (cached globally by API)
  Dynamic: [memory, git status, MCP instructions, scratchpad, ...]

Turn 2:
  Static: "You are Claude Code..." (same — API cache HIT for this block)
  Dynamic: [memory, git status*, MCP instructions*, scratchpad, ...]
                ↑                    ↑
                same (cached)        changed! (MCP servers may have reconnected)

Turn 3:
  Static: "You are Claude Code..." (API cache HIT)
  Dynamic: [memory, git status*, MCP instructions*, scratchpad*, ...]
```

**What stays the same:**

- The static prefix (identity, rules, tool descriptions, tone)
- CLAUDE.md content (cached in `getUserContext`)
- Git status (cached in `getSystemContext`)

**What changes:**

- MCP instructions (always recomputed — servers can connect/disconnect)
- Attached context (skills, plans, memory files — these are attachments, not system prompt)

---

## 6. Additional Context Injection — What Happens Outside the System Prompt

Beyond the system prompt, Claude Code injects context in two other ways:

### a) User Context (as a synthetic user message)

`getUserContext()` returns:

```typescript
{
  claudeMd: "Contents of CLAUDE.md files found in project...",
  currentDate: "Today's date is 2026-06-16."
}
```

This is prepended to the messages array before each API call via `prependUserContext()` — it appears as if the user typed "Here are your project instructions..." before their actual message. It's not in the system prompt; it's in the conversation history.

### b) System Context (appended to system prompt)

`getSystemContext()` returns:

```typescript
{
  gitStatus: "This is the git status at the start of the conversation.\n" +
             "Current branch: main\n" +
             "Status:\n M src/file.ts\n ?? new_file.py\n" +
             "Recent commits:\n abc1234 Fix auth bug\n def5678 Add feature"
}
```

This is appended to the system prompt array via `appendSystemContext()` (`api.ts:435-445`).

---

## 7. Attachments — The Third Context Channel

Memory, skills, plans, and other context are injected as attachment messages in the conversation, separate from the system prompt. Defined in `attachments.ts`, these are generated by `getAttachmentMessages()` — an async generator that yields `AttachmentMessage` objects.

### Common Attachment Types

| Attachment | When It Appears |
|------------|-----------------|
| `relevant_memories` | During normal turns (memory prefetch runs async) |
| `skill_listing` | Skills are available |
| `plan_mode` / `auto_mode` | In plan mode or auto mode |
| `plan_file_reference` | A plan file exists |
| `todo_reminder` | TODOs exist from TodoWrite calls |
| `edited_text_file` / `edited_image_file` | Files were modified |
| `token_usage` / `budget_usd` | Usage display after each turn |
| `invoked_skills` | Skills invoked before compaction |

These are appended to the message chain after tool results in the turn loop, not to the system prompt.

---

## 8. Prompt Priority — Overriding the Default

`buildEffectiveSystemPrompt()` determines the final prompt by priority:

```
1. Override system prompt (replaces everything)     ← Highest
2. Coordinator system prompt (coordinator mode)
3. Agent system prompt (proactive mode appends; others replace)
4. Custom system prompt (--system-prompt CLI flag)
5. Default system prompt (from getSystemPrompt())    ← Lowest
6. appendSystemPrompt (always appended at the end)
```

If you pass `--system-prompt "You are a Python assistant"`, it replaces the entire default system prompt.

---

## 9. What Happens on Compaction

When compaction fires, the system prompt is reset (`postCompactCleanup.ts`):

- `clearSystemPromptSections()` — Clears the section cache. All dynamic content will be recomputed on the next turn.
- `getUserContext.cache.clear()` — Clears CLAUDE.md cache.
- `resetGetMemoryFilesCache()` — Clears memory file cache.

Then post-compact attachments re-inject context that may have been lost:

- `createPostCompactFileAttachments()` — Re-reads the 5 most recently accessed files
- `createPlanAttachmentIfNeeded()` — Re-injects plan file content
- `createSkillAttachmentIfNeeded()` — Re-injects invoked skills (capped at 25K tokens)
- `createPlanModeAttachmentIfNeeded()` — Re-injects plan mode instructions

---

## 10. The Complete Flow — From Session Start to API Call

```
Session Start:
  ┌─────────────────────────────────────────────────────┐
  │ fetchSystemPromptParts() — runs once                │
  │                                                     │
  │ getSystemPrompt(tools, model)                       │
  │   ├─ Static blocks (computed once per session)     │
  │   │   ├─ Identity: "You are Claude Code..."        │
  │   │   ├─ System rules                              │
  │   │   ├─ Tool descriptions (filtered by enabled)   │
  │   │   ├─ Tone & style                              │
  │   │   └─ __SYSTEM_PROMPT_DYNAMIC_BOUNDARY__        │
  │   │                                                │
  │   └─ Dynamic blocks (cached per section)           │
  │       ├─ session_guidance (cached)                 │
  │       ├─ memory (cached)                           │
  │       ├─ env_info_simple (cached)                  │
  │       ├─ mcp_instructions (UNCACHED every turn!)   │
  │       └─ ... (other sections)                      │
  │                                                     │
  │ getUserContext() — memoized                         │
  │   → { claudeMd, currentDate }                      │
  │                                                     │
  │ getSystemContext() — memoized                       │
  │   → { gitStatus }                                  │
  └─────────────────────────────────────────────────────┘

Each API Call (per queryLoop turn):
  ┌─────────────────────────────────────────────────────┐
  │ 1. Build fullSystemPrompt =                         │
  │    [                                              │
  │      attributionHeader ("x-anthropic-billing-header:cc_version=...")  │
  │    , cliSyspromptPrefix ("You are Claude Code...")    │
  │    , systemPrompt (from above, recomputed dynamic sections)  │
  │    , appendSystemPrompt (if --append-system-prompt)  │
  │    ]                                                │
  │                                                   │
  │ 2. Append systemContext → gitStatus                │
  │                                                   │
  │ 3. Split into blocks with cache_control:          │
  │    [                                              │
  │      { text: attribution, cache_scope: null },    │
  │      { text: prefix, cache_scope: null },         │
  │      { text: "You are Claude Code...",            │
  │        cache_control: { type: 'ephemeral',       │
  │          scope: 'global', ttl: '1h' } },          │
  │      { text: dynamic content,                     │
  │        cache_scope: null },                       │
  │    ]                                              │
  │                                                   │
  │ 4. Prepend userContext → synthetic user message   │
  │    { role: "user", content: "CLAUDE.md + date" }  │
  │                                                   │
  │ 5. Call API:                                      │
  │    anthropic.beta.messages.create({               │
  │      model,                                        │
  │      messages: [userContext, ...],                 │
  │      system: splitSystemPromptBlocks,             │
  │      tools: [...],                                │
  │      betas: [...],                                │
  │      stream: true                                 │
  │    })                                              │
  └─────────────────────────────────────────────────────┘
```

---

## 11. Summary: The Three Layers of Context

| Layer | Source | Contents |
|-------|--------|----------|
| **Layer 1** — System Prompt (sent as "system" parameter) | Static prefix: Identity, rules, tools (global cache scope) | Dynamic tail: MCP, memory, env info (null cache scope, MCP always recomputed) | Attribution header: Version, entrypoint, workload (null cache scope) |
| **Layer 2** — User Context (prepended as synthetic user message) | CLAUDE.md content from project | Today's date |
| **Layer 3** — Attachments (injected as attachment messages in conversation) | Memory, skills, plans, TODOs | File change notifications | Usage displays |

The system prompt is designed to be maximally cacheable — the static prefix (which is ~60% of the prompt) gets a global API cache hit on every turn, dramatically reducing cost and latency. Only the dynamic parts (MCP instructions) are recomputed per turn, and even those are minimal.
