# Claude API Request Parameters — Deep Understanding Plan

## Context

This project is a reverse-engineered Claude Code CLI ("claude-code-best"). I've traced the complete path from user input → API request → response to understand every parameter sent to Anthropic's API endpoints.

---

## 1. API Client Setup

**File:** [client.ts](src/services/api/client.ts)

The client (`getAnthropicClient()`) supports **4 providers**:

| Provider | Env Var | Auth Method |
|---|---|---|
| **Direct API** (default) | none | `ANTHROPIC_API_KEY` or OAuth token |
| **AWS Bedrock** | `CLAUDE_CODE_USE_BEDROCK` | AWS credentials / Bearer token |
| **Azure Foundry** | `CLAUDE_CODE_USE_FOUNDRY` | API key or Azure AD |
| **Google Vertex** | `CLAUDE_CODE_USE_VERTEX` | GCP credentials |

**Request headers sent on every call:**
```
x-app: cli
User-Agent: <built at runtime>
X-Claude-Code-Session-Id: <session UUID>
x-claude-remote-container-id: <if in container>
x-claude-remote-session-id: <if remote>
x-client-app: <if SDK>
x-auth-nonce: <if SSH proxy>
x-anthropic-additional-protection: true (optional)
Authorization: Bearer <token>
x-client-request-id: <UUID, first-party only>
```

---

## 2. The API Request Construction

**File:** [claude.ts](src/services/api/claude.ts) — the `queryModel()` function (line ~1057)

This is where the entire API request is assembled. Here are **all parameters sent**:

### Core Parameters

```typescript
{
  model: "<normalized model string, e.g. 'claude-sonnet-4-5-20250514'>",
  messages: [...],           // Normalized conversation history
  system: [...],             // System prompt as blocks (Beta API)
  tools: [...],              // Tool definitions (Beta API)
  tool_choice: {...},        // Optional: {type: 'auto'|'any'|'tool', name?}
  betas: [...],              // Beta feature headers array
  metadata: {...},           // API metadata (user_id, session_id)
  max_tokens: <number>,      // max_output_tokens for the model
  thinking: {...},           // Optional: thinking configuration
  temperature: <number>,     // Only sent when thinking is disabled (defaults to 1)
  context_management: {...}, // Optional: context management beta params
  output_config: {...},      // Optional: effort, format, task_budget
  speed: 'fast',             // Optional: fast mode (beta)
}
```

### Streaming
```typescript
{ ...params, stream: true }
```
Always streamed. Falls back to non-streaming only on errors.

---

## 3. System Prompt

**Files:** [api.ts](src/utils/api.ts), [claude.ts](src/services/api/claude.ts)

The system prompt is built as an **array of text blocks** (not a single string). Each block can have `cache_control` for prompt caching.

### System Prompt Components (built at [claude.ts:1446-1457](src/services/api/claude.ts#L1446-L1457)):

1. **Attribution header** — `x-anthropic-billing-header:<fingerprint>`
2. **CLI sysprompt prefix** — `x-anthropic-cli-prefix:<identifier>`
3. **Custom/default system prompt** — from `fetchSystemPromptParts()`
4. **Advisor tool instructions** — if advisor is enabled
5. **Chrome tool search instructions** — if Chrome MCP tools are active

### System Prompt Splitting for Caching

**File:** [api.ts:321-433](src/utils/api.ts#L321-L433) — `splitSysPromptPrefix()`

The system prompt is split into blocks with different cache scopes:
- **`cacheScope: null`** — Attribution header, CLI prefix, dynamic content
- **`cacheScope: 'global'`** — Static content before dynamic boundary (1P only)
- **`cacheScope: 'org'`** — MCP tool content, rest of prompt

This enables **prompt caching** where static parts are cached and reused across requests.

---

## 4. Messages (Conversation History)

**File:** [claude.ts](src/services/api/claude.ts)

Messages are passed through `normalizeMessagesForAPI()` which converts internal `Message` objects to `BetaMessageParam` format.

### Message types sent to API:

| Internal Type | API Format |
|---|---|
| User message | `{role: 'user', content: [...]}` |
| Assistant message | `{role: 'assistant', content: [...]}` |
| Tool result | `{role: 'user', content: [{type: 'tool_result', tool_call_id, content}]}` |

### Message content block types:
- `text` — Plain text
- `tool_use` — Tool invocation (with `id`, `name`, `input`)
- `tool_result` — Tool output (with `tool_call_id`, `content`)
- `thinking` — Chain of thought (with `thinking`, `signature`)
- `redacted_thinking` — Compact chain of thought
- `image` — Image blocks
- `document` — Document blocks
- `server_tool_use` — Server-side tools (advisor)
- `connector_text` — Connector text blocks
- `tool_reference` — Deferred tool references

### Caching on messages:
The **last content block** of user/assistant messages gets `cache_control: {type: 'ephemeral'}` to cache the most recent conversation turn.

---

## 5. Tools

**File:** [api.ts](src/utils/api.ts) — `toolToAPISchema()` function

Tools are sent as **BetaTool** objects:

```typescript
{
  name: "Bash",
  description: "Description shown to the model...",
  input_schema: { /* JSON Schema */ },
  strict: true,                    // If feature flag + model supports it
  eager_input_streaming: true,     // Fine-grained tool streaming (1P only)
  defer_loading: true,             // Tool search (deferred discovery)
  cache_control: {type: 'ephemeral', scope: 'global'|'org', ttl: '5m'|'1h'},
}
```

### Built-in tools:
- `Bash` — Command execution
- `FileRead` — Read files
- `FileWrite` — Write files
- `FileEdit` — Edit files
- `Agent` — Subagent spawning
- `ExitPlanModeV2` — Plan mode exit
- `TaskOutput` — Task result
- `ToolSearch` — Discover deferred tools
- `ComputerUse` — Computer control
- `Sleep` — Delay execution
- `SyntheticOutput` — Structured output enforcement

### Tool features:
- **Dynamic tool loading** — Only tools discovered via `tool_reference` blocks are sent (saves tokens)
- **Strict mode** — JSON schema validation on tool inputs (feature-gated)
- **Fine-grained tool streaming** — Sends `input_json_delta` events for large tool inputs

---

## 6. Beta Feature Headers

**File:** [claude.ts](src/services/api/claude.ts)

The `betas` array includes these feature flags:

| Beta Header | Purpose |
|---|---|
| `prompt-caching-2024-07-31` | Prompt caching |
| `prompt-caching-scope` | Global/org cache scope |
| `tools-declarative` | Tool definitions |
| `computer-use-2025-03-13` | Computer use |
| `redacted-thinking-2025-03-31` | Redacted thinking output |
| `cache-editing-2026-05-13` | Cache editing for microcompact |
| `advanced-tool-use` / `tool-search-tool` | Dynamic tool loading |
| `task-budgets-2026-03-13` | API-side token budgets |
| `effort` | Effort level (high/medium/low/max) |
| `structured-outputs` | JSON output format |
| `context-1m` | 1M context window |
| `context-management` | Context management |
| `fast-mode` | Fast mode streaming |
| `afk-mode` | Auto-kill mode |
| `advisor-20260301` | Advisor server tool |

---

## 7. Thinking Configuration

**File:** [claude.ts](src/services/api/claude.ts:1703-1737)

Two modes:

| Mode | Config | Use Case |
|---|---|---|
| **adaptive** | `{type: 'adaptive'}` | Models that support adaptive thinking (default) |
| **enabled** | `{type: 'enabled', budget_tokens: N}` | Manual budget control |

Thinking is **disabled** by default for Haiku, or when `CLAUDE_CODE_DISABLE_THINKING` is set.

When thinking is enabled, `temperature` is **not sent** (API requires `temperature: 1` by default).

---

## 8. Memory System

**File:** [attachments.ts](src/utils/attachments.ts), [memdir/](src/memdir/)

Memory works as **attachments injected between turns** (not in the system prompt):

1. **Memory prefetch** runs asynchronously during model streaming
2. **Relevant memories** are loaded based on conversation context
3. Memories are sent as **attachment messages** with `tool_results`
4. Memory mechanics are described in the system prompt when `CLAUDE_COWORK_MEMORY_PATH_OVERRIDE` is set

**Memory prompt** is loaded from the memory directory and injected into the system prompt to teach the model how to use the memory files.

---

## 9. Context Management / Compaction

The query loop ([query.ts](src/query.ts)) handles context window management:

1. **Microcompact** — Compresses old tool results by tool_call_id
2. **Snip compact** — Replaces file content with snippets
3. **Auto-compact** — Summarizes conversation when near context limit
4. **Context collapse** — Replaces old messages with summaries
5. **Reactive compact** — Recovers from prompt-too-long errors

After compaction, a `compact_boundary` system message is inserted and old messages are removed from history.

---

## 10. Output Config

**File:** [claude.ts](src/services/api/claude.ts)

Sent in `extraBodyParams.output_config`:

```typescript
{
  effort: 'high'|'medium'|'low'|'max',   // Effort level for thinking
  format: {type: 'json', schema: {...}},  // JSON output enforcement
  task_budget: {type: 'tokens', total: N, remaining: M},  // Token budget for agentic turns
}
```

---

## 11. Metadata

**File:** [claude.ts](src/services/api/claude.ts:496-541) — `getAPIMetadata()`

```typescript
{
  user_id: JSON.stringify({
    device_id: "<uuid>",
    account_uuid: "<oauth account>",      // Only with OAuth
    session_id: "<session uuid>",
    ...extra                              // From CLAUDE_CODE_EXTRA_METADATA env
  })
}
```

---

## 12. The Request Pipeline (End-to-End)

```
User Input
  ↓
handlePromptSubmit (src/utils/handlePromptSubmit.ts)
  ↓ processUserInput — parses input, handles slash commands, attachments
  ↓
QueryEngine.submitMessage (src/QueryEngine.ts)
  ↓ fetches system prompt parts, builds systemPrompt array
  ↓
query() (src/query.ts)
  ↓ auto-compact, snip, microcompact, context collapse
  ↓
deps.callModel() → queryModelWithStreaming() (src/query/deps.ts)
  ↓
queryModel() (src/services/api/claude.ts)
  ↓ normalize messages, filter tools, build tool schemas
  ↓ build system prompt blocks with cache_control markers
  ↓ assemble params object (model, messages, system, tools, betas, etc.)
  ↓
anthropic.beta.messages.create({ ...params, stream: true })
  ↓
Stream processing — message_start, content_block_start/delta/stop, message_delta, message_stop
```

---

## Verification

To verify this understanding:
1. Run `CLAUDE_CODE_DEBUG_LOGGING=1 npx ccb` and watch the debug output for request parameters
2. Check `src/services/api/logging.ts` for `logAPIQuery()` which logs the request params
3. Check `captureAPIRequest()` in [log.ts](src/utils/log.ts) for request body capture (used for bug reports)
