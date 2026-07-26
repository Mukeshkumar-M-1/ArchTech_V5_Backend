---
title: "Streaming Response Mechanism - Principles of the Claude Code Typewriter Effect"
description: "Analyzing the implementation of streaming responses in Claude Code: how to receive AI output token-by-token via SSE, achieving a real-time typewriter effect and improving the user's waiting experience."
keywords:
  [
    "Streaming response",
    "SSE",
    "streaming",
    "real-time output",
    "API streaming",
  ]
sourceRef: "3ec5675 (2026-04-08)"
---

## Why Streaming is Needed

Imagine if an AI took 30 seconds to generate a complete response—if it only displayed everything at once after 30 seconds, the user experience would be disastrous.

Streaming responses allow users to **see the AI's thinking process in real-time**:

- Text appears character-by-character, allowing users to determine early on if the direction is correct.
- Tool call parameters can be previewed while they are being generated.
- Long-running tasks don't make the user feel like the system has "frozen."

## Core Event Types: `BetaRawMessageStreamEvent`

The streaming API returns a series of `BetaRawMessageStreamEvent` objects. Each event type corresponds to a different stage of the streaming response (`src/services/api/claude.ts`):

```
message_start           ← Message begins, contains model and initial usage values
  ├── content_block_start   ← Content block begins (text / tool_use / thinking)
  │   ├── content_block_delta  ← Incremental data (text_delta / input_json_delta / thinking_delta)
  │   ├── content_block_delta  ← ... continues to arrive
  │   └── content_block_stop   ← Content block ends, yields AssistantMessage
  ├── content_block_start   ← Next content block...
  │   └── ...
  └── message_delta       ← stop_reason + final usage
message_stop            ← Message ends
```

### Event Handling State Machine

The event processing loop in the `queryModelWithStreaming()` function in `src/services/api/claude.ts` implements a state machine based on `switch(part.type)`:

| Event Type            | Processing Logic                                                       | State Change                          |
| :-------------------- | :--------------------------------------------------------------------- | :------------------------------------ |
| `message_start`       | Initialize `partialMessage`, record TTFT (Time To First Token)         | `usage` initialization                |
| `content_block_start` | Create a content block of the corresponding type based on `part.index` | `contentBlocks[index]` initialization |
| `content_block_delta` | Incrementally append data based on subtype                             | Text / thinking / input accumulation  |
| `content_block_stop`  | Build a complete `AssistantMessage` and yield it                       | Message pushed to `newMessages`       |
| `message_delta`       | Update `stop_reason` and final `usage`                                 | Write back to the last message        |
| `message_stop`        | No operation (stream end marker)                                       | —                                     |

### Content Block Types and Their Incremental Data

The `content_block.type` in `content_block_start` determines how subsequent deltas are handled:

| Content Block Type | Delta Type                           | Accumulation Logic                                               |
| :----------------- | :----------------------------------- | :--------------------------------------------------------------- |
| `text`             | `text_delta`                         | `text += delta.text`                                             |
| `thinking`         | `thinking_delta` + `signature_delta` | `thinking += delta.thinking`, `signature = delta.signature`      |
| `tool_use`         | `input_json_delta`                   | `input += delta.partial_json` (incremental string concatenation) |
| `server_tool_use`  | `input_json_delta`                   | Same as `tool_use`                                               |
| `connector_text`   | `connector_text_delta`               | Special connector text (controlled by feature flag)              |

Key design choice: All text fields are initialized as empty strings during `content_block_start` and are only accumulated via `content_block_delta`. This is because the SDK sometimes sends the same text redundantly in both start and delta events.

## Interweaving of Text Chunks and tool_use Blocks

A single AI response can contain multiple content blocks appearing alternately:

```
content_block_start (text, index=0)     "I'll help you fix this bug."
content_block_delta  (text_delta)       "First..."
content_block_stop  (index=0)
content_block_start (tool_use, index=1) { name: "Read", input: "..." }
content_block_delta  (input_json_delta) '{"file_p' → 'ath":' → '"src/foo.ts"}'
content_block_stop  (index=1)
content_block_start (text, index=2)     "I've seen where the problem is..."
content_block_stop  (index=2)
```

Each `content_block_stop` triggers a `yield`, pushing a complete `AssistantMessage` to the consumer. This means a single AI response produces **multiple** `AssistantMessage` objects—alternating between text messages and tool call messages.

The `stop_reason` is only determined when `message_delta` arrives (e.g., `end_turn`, `tool_use`, `max_tokens`, etc.), so the `stop_reason` of the last message is **written back**:

```typescript
// claude.ts — stop_reason write-back logic (direct property modification, not object replacement)
// This is because the transcript write queue holds a reference to message.message
const lastMsg = newMessages.at(-1);
if (lastMsg) {
  lastMsg.message.usage = usage;
  lastMsg.message.stop_reason = stopReason;
}
```

## Error Handling in Streaming

### Network Disconnection

Streaming connections rely on SSE (Server-Sent Events). When a connection is interrupted, the system has two layers of detection mechanisms:

1.  **Passive Stall Detection** (stall detection logic in `src/services/api/claude.ts`): When the next event arrives, the time interval since the last event is calculated. If it exceeds a threshold (30 seconds, `STALL_THRESHOLD_MS = 30_000`), it is recorded as a stall, the count is accumulated, and it is written to telemetry logs. This is passive—it only triggers when the next chunk arrives and does not actively interrupt the stream.
2.  **Active Idle Timeout Watchdog** (`STREAM_IDLE_TIMEOUT_MS` logic in `src/services/api/claude.ts`): A hard timeout of 90 seconds (configurable via the `CLAUDE_STREAM_IDLE_TIMEOUT_MS` environment variable) is set using `setTimeout`. If no event is received during this period, the stream is actively terminated, and an error is thrown to enter the retry process.
3.  **Non-streaming Fallback**: As a last resort, the `didFallBackToNonStreaming` flag is set, and the system falls back to a non-streaming request via `executeNonStreamingRequest()` (getting the full response at once).

```typescript
// claude.ts — Passive stall detection
const STALL_THRESHOLD_MS = 30_000; // 30 seconds without events is considered a stall
let totalStallTime = 0;
let stallCount = 0;

// claude.ts — Active idle timeout
const STREAM_IDLE_TIMEOUT_MS =
  parseInt(process.env.CLAUDE_STREAM_IDLE_TIMEOUT_MS || "", 10) || 90_000;
```

### API Rate Limiting

When the API returns a rate limit error, the system uses the `withRetry` wrapper for exponential backoff retries. The retry logic considers:

- Error type (429 Rate Limit vs. 500 Server Error)
- Maximum number of retries
- Backoff interval

### Token Limit Exceeded

Two token limit scenarios are handled differently:

| Scenario                    | stop_reason                     | Handling Method                                                              |
| :-------------------------- | :------------------------------ | :--------------------------------------------------------------------------- |
| **Output Exceeded**         | `max_tokens`                    | Generate an error message suggesting setting `CLAUDE_CODE_MAX_OUTPUT_TOKENS` |
| **Context Window Exceeded** | `model_context_window_exceeded` | Trigger compaction to compress conversation history, then retry              |

```typescript
// claude.ts — stop_reason handling
if (stopReason === "max_tokens") {
  yield createAssistantAPIErrorMessage({ error: "max_output_tokens", ... });
}
if (stopReason === "model_context_window_exceeded") {
  // Reuse the recovery path for max_output_tokens
  yield createAssistantAPIErrorMessage({ error: "max_output_tokens", ... });
}
```

### Stream Stall Monitoring

The system continuously monitors event arrival intervals to detect "stalls":

```typescript
// claude.ts — stall detection logic
const STALL_THRESHOLD_MS = 30_000; // 30 seconds without events is considered a stall
if (timeSinceLastEvent > STALL_THRESHOLD_MS) {
  stallCount++;
  totalStallTime += timeSinceLastEvent;
  logEvent("tengu_streaming_stall", {
    stall_duration_ms,
    stall_count,
    ...
  });
}
```

This is **passive detection**—the comparison only triggers when the next chunk arrives. It is complemented by the 90-second active idle timeout watchdog (`STREAM_IDLE_TIMEOUT_MS`), which directly interrupts streams that are unresponsive for a long time.

## Streaming Feedback for Tool Execution

Command execution in `BashTool` is also streamed—output is pushed line-by-line via the `onProgress` callback:

```
BashTool.call() → runShellCommand() → AsyncGenerator
  ├── Polling output file every second → onProgress(lastLines, allLines, ...)
  ├── yield { type: 'progress', output, fullOutput, elapsedTimeSeconds }
  └── return { code, stdout, interrupted, ... }
```

The UI layer uses the `useToolCallProgress` hook to display command output in real-time, rather than waiting for the command to finish completely. Long-running commands also support automatic backgrounding (`shouldAutoBackground`).

## Multi-Provider Adaptation

| Provider                          | Streaming Protocol          | Special Handling                               |
| :-------------------------------- | :-------------------------- | :--------------------------------------------- |
| **firstParty** (Anthropic Direct) | Native SSE                  | Lowest latency, fastest TTFT                   |
| **AWS Bedrock**                   | AWS SDK Streaming Interface | Requires extra beta headers and authentication |
| **Google Vertex**                 | gRPC → Event Stream         | Adapted via `getMergedBetas()`                 |
| **foundry**                       | Anthropic-compatible API    | Internal deployment                            |
| **openai**                        | OpenAI Streaming Adapter    | Converted to Anthropic internal format         |
| **gemini**                        | Gemini Streaming Adapter    | Converted to Anthropic internal format         |
| **grok** (xAI)                    | Grok Streaming Adapter      | Converted to Anthropic internal format         |

All providers are masked behind a unified `Stream<BetaRawMessageStreamEvent>` abstraction layer. Upper-level code (QueryEngine, REPL) does not need to know which provider is being used under the hood.

### Provider Selection

`getAPIProvider()` in `src/utils/model/providers.ts` determines which provider to use based on configuration:

```typescript
// Selection based on api_provider configuration:
// "anthropic" → Direct connection
// "bedrock"   → AWS SDK
// "vertex"    → Google SDK
// Third-party base URL → Automatic detection
```

Details that each provider needs to adapt include authentication methods, beta headers, request parameter formats, and error code mappings—but these differences are handled uniformly in the `queryStream()` function in `claude.ts`.
