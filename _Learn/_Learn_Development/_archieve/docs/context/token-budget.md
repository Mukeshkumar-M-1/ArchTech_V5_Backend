---
title: "Token Budget Management - Dynamic Calculation of Context Window"
description: "Revealing Claude Code token budget management from the source code perspective: dynamic calculation of 200K context window, truncation mechanism, cache optimization and complete link of automatic compression."
keywords:
  [
    "Token budget",
    "context window",
    "token calculation",
    "truncation mechanism",
    "cache optimization",
  ]
---

{/_ The goal of this chapter: reveal the complete link of dynamic calculation, truncation mechanism, cache optimization and automatic compression of token budget from the source code perspective _/}

## Context window: 200K not all

Claude Code's default context window is 200K tokens (`MODEL_CONTEXT_WINDOW_DEFAULT = 200_000`), but the actual space available for dialogue is much less than this:

```
Context window (200K)
├── System prompt (~15-25K, low cost after caching)
├── Tool definitions (~10-20K, including MCP tools)
├── User context (CLAUDE.md, git status, etc.)
├── Output reservation (maxOutputTokens)
│ ├── Default upper limit: 64K
│ ├── Actual default: 8K (slot-reservation optimization)
│ └── Reaches limit → automatic 64K retry
└── Remaining: conversation history space (grows with conversation)
```

`getContextWindowForModel()` (`src/utils/context.ts:51`) parses the window size in 5 priority levels:

1. `CLAUDE_CODE_MAX_CONTEXT_TOKENS` environment variable override
2. Model name contains `[1m]` suffix → 1M tokens
3. `getModelCapability(model).max_input_tokens`
4. 1M beta header + supported models (claude-sonnet-4, opus-4-6)
5. Bottom line: 200K
   **Effective context** = window size - min(maxOutputTokens, 20K), because compression summary needs to reserve output space.

## Token Counting: Approximate vs Exact

The system uses a two-level token counting strategy:

### Approximate estimate (millisecond level)

```typescript
// src/services/tokenEstimation.ts
function roughTokenCountEstimation(content: string, bytesPerToken = 4): number {
  return Math.round(content.length / bytesPerToken);
}
```

Special handling for different content types:

- **JSON/JSONL**: `bytesPerToken = 2` (dense `{`, `:`, `,` symbols, each only 1-2 tokens)
- **Images/Documents**：Fixed 2000 tokens (conservative estimate based on 2000×2000px limit)
- **Thinking blocks**: by actual text length / 4
- **tool_use**: After serializing `name + JSON.stringify(input)` / 4

### Exact counting (API call)

Use Anthropic's `beta.messages.countTokens` endpoint. Different providers have different paths:

| Provider                                  | Method                                                                        |
| ----------------------------------------- | ----------------------------------------------------------------------------- |
| Anthropic direct connection               | `anthropic.beta.messages.countTokens()`                                       |
| AWS Bedrock                               | `CountTokensCommand` of `@aws-sdk/client-bedrock-runtime`                     |
| Google Vertex                             | Anthropic SDK + beta filtering                                                |
| Keep it secret (not supported by Bedrock) | Use Haiku to send a request with `max_tokens=1` and read `usage.input_tokens` |

Precise counting is used at key decision points (comparison before and after compression, warning judgment), and approximate estimation is used in the hot path (shouldAutoCompact check in each cycle).

### Token count difference of 3P Provider

Different Providers implement precise token counting in different ways, and some providers do not even support precise counting:

| Provider                          | Counting method                          | Notes                                     |
| --------------------------------- | ---------------------------------------- | ----------------------------------------- |
| **Anthropic Direct**              | `anthropic.beta.messages.countTokens()`  | Standard API, most accurate               |
| **AWS Bedrock**                   | `CountTokensCommand`                     | Requires dynamic loading of 279KB AWS SDK |
| **Google Vertex**                 | Anthropic SDK + beta filtering           | Requires specific beta headers            |
| **OpenAI Compatibility Layer**    | No precise count                         | **Fall back to approximate estimate**     |
| **Gemini Compatibility Tier**     | No exact count                           | **Fall back to approximate estimate**     |
| **When Bedrock does not support** | Use Haiku to send `max_tokens=1` request | Read `usage.input_tokens`                 |

OpenAI and Gemini compatibility layers** do not support precise token counting** and the system will fall back to approximate estimates. This affects:

- **Auto compression trigger timing**: may vary slightly
- **Token comparison before and after compression**: only an estimate, not precise
- **Warning/Error threshold judgment**: based on estimates rather than precise counts

```typescript
// src/services/tokenEstimation.ts - Approximate estimation function
function roughTokenCountEstimation(content: string, bytesPerToken = 4): number {
  return Math.round(content.length / bytesPerToken);
}
```

Source code path: `src/services/tokenEstimation.ts`

## Trigger threshold for automatic compression

```
src/services/compact/autoCompact.ts — Core Thresholds
```

| constant                               | value  | meaning                                                 |
| -------------------------------------- | ------ | ------------------------------------------------------- |
| `AUTOCOMPACT_BUFFER_TOKENS`            | 13,000 | Window minus this value = autocompression trigger point |
| `WARNING_THRESHOLD_BUFFER_TOKENS`      | 20,000 | Display warning at trigger point + 20K                  |
| `ERROR_THRESHOLD_BUFFER_TOKENS`        | 20,000 | Display error at trigger point + 20K                    |
| `MANUAL_COMPACT_BUFFER_TOKENS`         | 3,000  | Blocking limit for manual /compact                      |
| `MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES` | 3      | Stop trying after 3 consecutive failures                |

Take the 200K window as an example:

- **~167K**: warning flashes, and the user sees a prompt suggesting compression.
- **~180K**: automatic compression trigger (200K - 20K output reservation = 180K effective, then - 13K buffer)
- **~197K**: blocking limit reached, new messages are blocked

`shouldAutoCompact()` has multiple escape conditions:

- Queries from `compact` / `session_memory` sources are never triggered (anti-recursive deadlock)
- `DISABLE_COMPACT` / `DISABLE_AUTO_COMPACT` environment variables
- User configuration `autoCompactEnabled = false`
- Suppress when Context Collapse mode is activated (collapse manages the context itself)
- Reactive Compact suppresses active compression in experimental mode
- Exceeding the upper limit of consecutive failures (circuit breaker)

## Micro-Compact: Progressive compression of tool results

Before triggering full compaction, the system first attempts **micro-compact** - only compressing the results of old tool calls:

```
List of compressible tools (COMPACTABLE_TOOLS):
FileRead, Bash, Grep, Glob, WebSearch, WebFetch, FileEdit, FileWrite
```

Strategies are based on time:

- Tool results older than a certain time (controlled by `timeBasedMCConfig`) are replaced with short placeholders
- Image/document results are replaced with `[image]` / `[document]` text
- Each replacement releases tokens, which may delay full compression

The tool itself also has a hard limit of `maxResultSizeChars` (usually 100K), and very long results are truncated before being written to the message.

## Complete process of full compression

```
autoCompactIfNeeded() / compactConversation()
↓
1. Execute PreCompact hooks (custom instructions can be injected externally)
↓
2. Try Session Memory compression (more lightweight, try first)
↓
3. Session Memory failed → Full compression
a. The image/document is stripped from the message (replaced with [image]/[document])
b. skill_discovery/skill_listing attachment stripping (will be re-injected after compression)
c. Send summary request through forked agent (reuse the prompt cache of the main thread)
d. If the digest request itself triggers prompt-too-long → truncateHeadForPTLRetry()
Delete starting from the oldest API round and retry up to 3 times
↓
4. Rebuild the context after successful compression:
- compactBoundaryMarker (record compression type, number of first tokens, etc.)
- Summary message (invisible user message)
- Reread of last 5 files (POST_COMPACT_TOKEN_BUDGET = 50K)
- plan file attachment (if any)
- plan mode directive (if in plan mode)
- Called skill content (each skill ≤5K, total ≤25K)
- Incremental re-injection of deferred tools / agent listing / MCP directives
- SessionStart hooks re-execution
- PostCompact hooks execution
↓
5. Update the cache baseline to prevent it from being misjudged as cache break
```

### Prompt Cache Sharing

Compression API calls are one of the most expensive operations in the entire session. The system reuses the cache prefix of the main thread (system prompt + tools + context messages) through `runForkedAgent`, increasing the cache hit rate from 2% to nearly 100%. This optimization alone saves approximately 0.76% of `cache_creation` tokens at fleet level.

## Slot optimization of output Token

An often overlooked optimization: dynamic adjustment of maxOutputTokens.

```typescript
// src/services/api/claude.ts — getMaxOutputTokensForModel()
const defaultTokens = isMaxTokensCapEnabled()
  ? Math.min(maxOutputTokens.default, 8_000) // The default is reduced to 8K
  : maxOutputTokens.default; // Original default 32K/64K
```

Why? Because the API's slot mechanism reserves inference capacity based on `max_tokens`. BQ p99 outputs only 4,911 tokens, and the default value of 32K wastes 8-16 times the slot capacity. After dropping to 8K, less than 1% of requests are truncated - these requests automatically get a 64K clean retry.

The impact of this optimization on the token budget is indirect: more slot capacity means less queuing delay, which indirectly reduces timeouts and retries.

## Partial Compact: Selectively compress

In addition to full compression, users can also select a certain position in the message history and only compress the content before or after that position:

- **`up_to` direction**: compress the content before the selected message and keep the most recent conversation
- **`from` direction**: compress the content after the selected message and retain the earlier conversation

The `from` direction preserves the prompt cache (the prefix remains unchanged), and the `up_to` direction destroys the cache (the summary is inserted before the retained content).

The PTL (prompt-too-long) retry strategy is the same in both directions: start deletion from the oldest API round, ensuring that at least one set of messages is retained for digestion.
