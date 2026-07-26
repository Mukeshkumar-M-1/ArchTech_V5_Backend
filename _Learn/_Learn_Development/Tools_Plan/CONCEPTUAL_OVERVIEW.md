# How Sessions, Context, Tools, Agents, and Progress All Fit Together

## The Big Picture

Everything revolves around the query loop in `query.ts`. One "turn" looks like this:

1. User asks question
2. AI responds (maybe with tool calls)
3. Tools execute
4. Results sent back to AI
5. AI responds more (maybe more tools)
6. AI gives final answer
7. Loop ends, next user message waits

This loop can repeat hundreds of times in one session. Here's how every piece fits in:

---

## 1. The Session Is the Container

Each session has a unique UUID and owns everything:

- **One JSONL transcript file** — all messages, tool calls, tool results ever exchanged
- **One context window** — the message chain sent to the API each turn
- **One set of tools** — defined in `Tool.ts`, registered in `tools.ts`
- **Zero or one active agent** — a specialized sub-agent that can run independently

The session state machine (`sessionState.ts`) tracks:

```
idle → running → idle
     ↓
  requires_action (waiting for a tool)
```

`QueryGuard` enforces this — only one query can run at a time.

---

## 2. The Query Loop — The Heart of Everything

Inside `query.ts`, `queryLoop()` is a `while(true)` async generator. Each iteration does:

```
┌─ Per-turn preparation ──────────────────────────────────┐
│ 1. Strip pre-compact messages                           │
│ 2. Release raw tool result payloads (free memory)       │
│ 3. Apply tool result budget (cap oversized results)     │
│ 4. Snip compact (remove old messages per snip boundary) │
│ 5. Microcompact (clear old tool results)                │
│ 6. Context collapse (collapse old spans)                │
│ 7. Auto-compact (summarize old conversation if needed)  │
│ 8. Build final messages array                           │
├─────────────────────────────────────────────────────────┤
│ 9. Call API → stream response                           │
│ 10. Extract tool_use blocks from response               │
│ 11. Execute tools (in parallel or serially)             │
│ 12. Collect tool_results                                │
│ 13. If more tool_use blocks → GOTO step 1               │
│ 14. Otherwise → turn complete                           │
└─────────────────────────────────────────────────────────┘
```

- **Step 1-7** = Context Management (covered in section 3)
- **Step 10-12** = Tools & Agents (covered in section 4)
- **Step 13** = The Agentic Loop (covered in section 5)

---

## 3. Context Management — Keeping the Conversation Under Control

The context window is the API's limit on how much conversation history can be sent per call. When it fills up, Claude Code has a stack of compaction strategies that run in order, each turn.

**Every API turn:**

```
Every API turn:
  │
  ▼
┌─ Step 1: Snip Compact ──────────────────────────────┐
│ - Replaces large file contents in messages with     │
│   stubs (e.g., "[File: /path.ts, 100 lines]")       │
│ - Triggered when message count > 30                 │
│ - Frees tokens without losing information           │
├──────────────────────────────────────────────────────┤
│ - Microcompact (time-based) ────────────────────────┤
│ - Replaces old tool results with                    │
│   '[Old tool result content cleared]'               │
│ - Only applies to "compactable" tools (read, grep,  │
│   web_search, etc.)                                │
│ - Fires every ~10 minutes of conversation           │
│ - Cached variant: uses API cache_edits instead      │
│   of modifying local messages                       │
├──────────────────────────────────────────────────────┤
│ - Context Collapse (marble-origami) ────────────────┤
│ - Commits pre-staged collapses of old message spans │
│ - Read-time projection, no API call needed          │
├──────────────────────────────────────────────────────┤
│ - Auto-Compact (emergency) ─────────────────────────┤
│   FIRST tries Session Memory Compact (uses          │
│   previously extracted memory content as summary)   │
│   Falls back to legacy Compact (sends old messages  │
│   to API for summarization)                         │
│ - Triggered when tokens exceed context threshold    │
│   minus buffer (50K for 800K context, etc.)        │
│ - Circuit breaker: stops after 3 consecutive fails  │
└──────────────────────────────────────────────────────┘
```

**Key insight:** Auto-compact tries session memory first. If you've been using the session long enough for memory extraction to run, it reuses that summary instead of making another API call to summarize. This saves both tokens and money.

After compaction, the final `messagesForQuery` array is what gets sent to the API. It typically contains:

- System prompt
- Compact boundary message (meta: "messages X-Y were summarized")
- Compact summary (the summarized version of old messages)
- Recent preserved messages (the tail that wasn't compacted)

---

## 4. Tools — The Bridge Between AI and Action

Tools are Claude Code's "hands." The AI has a brain, but tools let it touch files, run commands, and browse the web.

### Tool Definition (`Tool.ts`)

```typescript
interface Tool {
  name: string;                          // e.g., "tools_read_file"
  inputSchema: ZodSchema;                // Validates arguments the AI sends
  outputSchema: ZodSchema;               // Validates output the tool returns
  prompt(options): Promise<string>;      // Description shown to the API
  call(input, context, canUseTool, ...): Promise<ToolResult>; // Actual work
  isConcurrencySafe(input): boolean;     // Can run in parallel?
  renderToolUseMessage(...);             // How it appears in the UI
  renderToolUseProgressMessage(...);     // Live progress rendering
  renderToolResultMessage(...);          // Completed result rendering
  // ... plus permission hooks, interrupt behavior, etc.
}
```

### Tool Execution Flow

When the API returns a `tool_use` block:

```
API response chunk:
{ type: "tool_use", id: "toolu_001", name: "Bash",
  input: { command: "ls -la" } }
       │
       ▼
StreamingToolExecutor.addTool() [if concurrent mode]
OR runTools() [if serial mode]
       │
       ▼
runToolUse() ────────────────────────────────────────
  │
  ├── PreToolUse hooks (plugins can intercept)
  │
  ├── Permission check (canUseTool function)
  │     │
  │     ├── user prompt → "Allow running: ls -la?"
  │     ├── auto-allow / auto-deny rules
  │     └── permissionMode (full-auto / recommend / skip)
  │
  ├── tool.call(input, context, canUseTool, onProgress)
  │     │
  │     ├── Tool runs the actual work
  │     ├── onProgress() called with ToolProgress objects
  │     │     → UI renders live progress
  │     │     → NOT saved to transcript (UI-only)
  │     └── Returns ToolResult<Output>
  │
  ├── PostToolUse hooks (plugins can modify output)
  │
  └── createUserMessage() wraps result in tool_result block
        { type: "tool_result", tool_call_id: "toolu_001",
          content: "<command output>", is_error: false }
```

**Concurrency:** `StreamingToolExecutor` runs concurrency-safe tools (file reads, grep, web fetch) in parallel. Non-safe tools (Bash, FileEdit, FileWrite) run serially. Bash errors cascade — if one Bash command fails, sibling commands are cancelled.

---

## 5. Agents — Specialized Sub-Agents

Agents are "Claude Code within Claude Code." They get their own system prompt, tool set, and model.

### Two Types

| Type | How It's Triggered | Inherits Context |
|------|-------------------|------------------|
| Subagent | Agent tool call | Gets a restricted context window |
| Fork subagent | Special fork flag | Inherits full conversation context |

### Agent Execution Flow

When the AI decides to use the Agent tool:

```
API returns: { type: "tool_use", name: "Agent",
  input: { prompt: "...", model: "sonnet", ... } }
       │
       ▼
Agent tool calls runAgent() [runAgent.ts]
       │
       ├── Creates isolated context (separate AppState)
       │     → Own setAppState() (does not affect parent)
       │     → Own toolUseContext
       │     → Own permission mode ('bubble' for parent terminal)
       │     → Own query() loop (full agentic loop inside)
       │
       ├── Runs the subagent's own query loop
       │     → Can make API calls, use tools, call more agents
       │     → Gets its own tool_use/tool_result cycle
       │
       └── Returns tool_result to parent
             { content: "Subagent completed: ..." }
```

The parent agent sees this as a single `tool_result` — the entire subagent's work is summarized.

---

## 6. Progress — What the User Sees

Progress is transient — it appears live but is **NOT** stored in the transcript.

### Progress Types (`sessionStorage.ts:186-196`)

```typescript
EPHEMERAL_PROGRESS_TYPES = new Set([
  'bash_progress',      // Bash output chunks (1/sec)
  'powershell_progress',
  'mcp_progress',       // MCP tool progress
  'sleep_progress',     // Sleep/delay progress (if enabled)
])
```

### How Progress Flows

```
tool.call() executes
  │
  ├── onProgress({ type: 'stdout', content: 'building...', is_complete: false })
  │     │
  │     ├── createProgressMessage() wraps it in ProgressMessage<P>
  │     │     → pushed to pendingProgress on TrackedTool
  │     │
  │     └── StreamingToolExecutor yields it immediately
  │           → onQueryEvent() in REPL.tsx receives it
  │           → handleMessageFromStream() → setMessages([...])
  │           → React re-renders → user sees output appear live
  │
  └── When complete:
      ├── renderToolResultMessage() shows the result
      └── tool_result block is written to transcript (permanent)
```

**Key distinction:** Progress messages are rendered and then effectively discarded. Only `tool_use` (the call) and `tool_result` (the outcome) are saved to the JSONL transcript. This keeps transcript files small — a 2-hour session with thousands of bash output lines only saves the final result, not every intermediate tick.

---

## 7. The Full Interconnected Flow

Here's how everything connects in one complete turn:

```
                    ╔══════════════════════════════════╗
                    ║        SESSION (UUID)            ║
                    ║  owns: transcript, context,       ║
                    ║  tools, agent state               ║
                    ╚══════════════════════════════════╝
                             │
                  User types: "fix the auth bug"
                             │
                             ▼
              ┌──────────────────────────────┐
              │     queryGuard.tryStart()     │  ← Session state: running
              └──────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────────┐
              │  Context Management Chain    │
              │  ┌─ snip compact             │
              │  ├─ microcompact             │
              │  ├─ context collapse         │
              │  └─ auto-compact (if needed) │
              └──────────────────────────────┘
                             │
              Messages after compaction:
              [system, boundary, summary, recent messages]
                             │
                             ▼
              ┌──────────────────────────────┐
              │   API CALL (streaming)        │
              │   model + messages + tools + │
              │   system_prompt + betas      │
              └──────────────────────────────┘
                             │
              ┌──────────────────────────────┐
              │   RESPONSE (streaming back)   │
              │  { role: "assistant",         │
              │    content: [                 │
              │      { type: "text",          │
              │        text: "Let me fix it" }│
              │      { type: "tool_use",      │
              │        id: "toolu_001",       │
              │        name: "FileEdit",      │
              │        input: {...} },        │
              │      { type: "tool_use",      │
              │        id: "toolu_002",       │
              │        name: "Bash",          │
              │        input: {...} }         │
              │    ]                          │
              │  }                            │
              └──────────────────────────────┘
                             │
              ┌──────────────────────────────┐
              │   TOOL EXECUTION             │
              │  toolu_001: FileEdit → serial│
              │    ├── PreToolUse hooks       │
              │    ├── Permission check       │
              │    ├── tool.call()            │
              │    │   ├── onProgress() → UI  │
              │    │   └── Returns result     │
              │    └── PostToolUse hooks      │
              │  toolu_002: Bash → parallel   │
              │    ├── PreToolUse hooks       │
              │    ├── Permission check       │
              │    ├── tool.call()            │
              │    │   ├── onProgress() → UI  │
              │    │   │   ┌─ stdout: "make:   │
              │    │   │   │   compiling..."   │
              │    │   │   └─ ...              │
              │    │   └── Returns result     │
              │    └── PostToolUse hooks      │
              └──────────────────────────────┘
                             │
              ┌──────────────────────────────┐
              │   TOOL RESULTS ASSEMBLED     │
              │  [tool_result: toolu_001,     │
              │   tool_result: toolu_002]     │
              └──────────────────────────────┘
                             │
              ┌──────────────────────────────┐
              │   MESSAGE CHAIN BUILT        │
              │  old_messages +               │
              │  assistant_messages +         │
              │  tool_results                 │
              │                               │
              │  "Did the AI want more tools?"│
              │  → Yes: loop back to API call │
              │  → No: turn complete          │
              └──────────────────────────────┘
                             │
              ┌──────────────────────────────┐
              │   PER-TURN SIDE EFFECTS      │
              │  recordTranscript() → JSONL  │
              │  post-sampling hooks         │
              │  session memory (periodic)   │
              └──────────────────────────────┘
                             │
              queryGuard.end() → session state: idle
                             │
              ┌──────────────────────────────┐
              │   USER SEES ANSWER ON SCREEN │
              │   (character by character)    │
              └──────────────────────────────┘
```

---

## 8. Progress Tracking — Where It Lives

| What | Where It Lives | When It's Updated |
|------|---------------|-------------------|
| Session state (idle/running/requires_action) | `sessionState.ts` | Each turn start/end |
| Query guard (concurrency lock) | `QueryGuard.ts` | Each query start/end |
| Tool progress (live output) | `pendingProgress` on TrackedTool | During tool execution |
| Memory extraction state | SessionMemory utils | After each turn (periodic) |
| Auto-compact tracking | `state.ts` autoCompactTracking | Each auto-compact attempt |
| Context collapse state | `ContextCollapseSnapshotEntry` in transcript | When collapses are committed |
| Cost/state (tokens used, budget) | `state.ts` telemetry counters | Each API call |
| TODO list | Extracted from TodoWrite tool in transcript | On each TodoWrite call |

**Progress that is NOT persisted:** Bash output ticks, Sleep progress, per-chunk streaming. Only the final `tool_result` is saved. This is intentional — progress is for the living session, not for history.

**Progress that IS persisted:** The `tool_use` entry (what was called and with what arguments) and the `tool_result` entry (what it returned). These form the permanent record of what happened during the session.
