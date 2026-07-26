---
title: "Context Compression - Compaction Three-Layer Strategy and Boundary Mechanism"
description: "In-depth analysis of the complete implementation of Claude Code context compression: Session Memory compression, traditional API summary compression, MicroCompact local compression three-layer strategy, as well as key mechanisms such as CompactBoundary messages, tool pair retention, and PTL emergency downgrade."
keywords:
  [
    "context compression",
    "Compaction",
    "token management",
    "conversation compression",
    "context window",
    "MicroCompact",
  ]
---

{/_ The goal of this chapter: Analyze the three-layer compression strategy, boundary mechanism and key constants from the source code level _/}

## Compression trigger timing

Context compression is not a single operation, but a three-layer progressive policy system, corresponding to different trigger conditions and severity:

| Level                      | Trigger conditions                                             | Implementation location   | Whether API calls are required |
| -------------------------- | -------------------------------------------------------------- | ------------------------- | :----------------------------: |
| **MicroCompact**           | Single tool output is too long                                 | `microCompact.ts`         |               No               |
| **Session Memory Compact** | Automatic compression trigger (feature flag required)          | `sessionMemoryCompact.ts` |               No               |
| **Legacy API Summary**     | Manual `/compact` or automatic fallback when SM is unavailable | `compact.ts`              |              Yes               |

### Priority chain of compression entry

Source code path: `src/commands/compact/compact.ts`

When the user executes `/compact` or the system triggers automatic compaction, compaction commands are attempted with the following priority:

```typescript
// compact.ts:55-99 — Simplified priority chain
if (!customInstructions) {
const sessionMemoryResult = await trySessionMemoryCompaction(messages, ...)
if (sessionMemoryResult) return sessionMemoryResult // Priority: SM compression
}

if (reactiveCompact?.isReactiveOnlyMode()) {
return await compactViaReactive(messages, ...) // Second choice: Reactive compression
}

// Bottom line: Traditional API summary
const microcompactResult = await microcompactMessages(messages, context)
const messagesForCompact = microcompactResult.messages
// → Call the AI model to generate a summary
```

Note: SM compression does not support custom instructions (`/compact focuses on the authentication module`). If there are custom instructions, go directly to the traditional path.

## First layer: MicroCompact — local compression

Source code path: `src/services/compact/microCompact.ts`

MicroCompact does not compress the entire conversation, but cleans the output of the old tool. It maintains a whitelist of:

```typescript
// src/services/compact/microCompact.ts:41-50
const COMPACTABLE_TOOLS = new Set([
  FILE_READ_TOOL_NAME, // 'Read' - file reading
  ...SHELL_TOOL_NAMES, // 'Bash' - command output
  GREP_TOOL_NAME, // 'Grep' - search results
  GLOB_TOOL_NAME, // 'Glob' - file list
  WEB_SEARCH_TOOL_NAME, // 'WebSearch' - search results
  WEB_FETCH_TOOL_NAME, // 'WebFetch' - web content
  FILE_EDIT_TOOL_NAME, // 'Edit' - edit output
  FILE_WRITE_TOOL_NAME, // 'Write' - write output
]);
```

Replacement strategy: Replace tool output content that exceeds the time window with `[Old tool result content cleared]`. This is not a simple truncation - the original content remains in the JSONL transcript, it is just no longer sent to the API.

MicroCompact also has a **time decay configuration** (`timeBasedMCConfig.ts`): the older the tool output is, the easier it is to clear it, and the most recent ones are retained first.

### Special handling of images and documents

```typescript
const IMAGE_MAX_TOKEN_SIZE = 2000;
```

If the image block exceeds the estimated value of 2000 tokens, it will also be cleared by MicroCompact. The same goes for PDF document block.

## Second layer: Session Memory Compact — compression without API calls

Source code path: `src/services/compact/sessionMemoryCompact.ts`

When the two feature flags `tengu_session_memory` + `tengu_sm_compact` are enabled, the system gives priority to using Session Memory for compression - **no need to call the summary model**, and directly uses the extracted Session Memory as the conversation summary.

### Preserve window calculations

```typescript
// sessionMemoryCompact.ts:324-397
export function calculateMessagesToKeepIndex(messages, lastSummarizedIndex) {
  const config = getSessionMemoryCompactConfig();
  //Default: minTokens=10K, minTextBlockMessages=5, maxTokens=40K

  let startIndex = lastSummarizedIndex + 1;
  //Expand forward from lastSummarizedIndex until two lower bounds are met or the upper bound is hit
  for (let i = startIndex - 1; i >= floor; i--) {
    totalTokens += estimateMessageTokens([msg]);
    if (hasTextBlocks(msg)) textBlockMessageCount++;
    startIndex = i;
    if (totalTokens >= config.maxTokens) break;
    if (
      totalTokens >= config.minTokens &&
      textBlockMessageCount >= config.minTextBlockMessages
    )
      break;
  }
  return adjustIndexToPreserveAPIInvariants(messages, startIndex);
}
```

This algorithm ensures that the message window retained after compression satisfies:

- At least 10,000 tokens (with context depth)
- At least 5 messages containing text (with conversation continuity)
- Up to 40,000 tokens (not too large to trigger the next compression)

### Tools for integrity protection

`adjustIndexToPreserveAPIInvariants()` is a **key correctness guarantee** in compression:

The API requires that every `tool_result` has a corresponding `tool_use` and vice versa. If compression happens to be cut at a `tool_result` message, an API error will be reported.

```typescript
// sessionMemoryCompact.ts:232-314
// Step 1: Scan forward to find tool_use referenced by tool_result in all retained messages
// Step 2: Scan forward to find the thinking block that shares message.id with the retained assistant message
// In both cases, startIndex needs to be moved forward
```

Streaming will split an assistant message into multiple storage records (thinking, tool_use, etc. each have independent uuid but share `message.id`), which increases the complexity of edge cases.

## Layer 3: Traditional API digest compression

Source code path: `src/services/compact/compact.ts`

When SM compression is not available, the system falls back to traditional methods: calling an AI model to generate conversation summaries.

### Pre-compression processing

Messages go through multiple layers of preprocessing before being sent to the digest model:

```typescript
// compact.ts:147-202
const stripped = stripImagesFromMessages(messages); // Picture → [image] text mark
const stripped2 = stripReinjectedAttachments(stripped); // Remove attachments that will be re-injected
```

Images are replaced with `[image]` tags, preventing the summary API call itself from triggering prompt-too-long errors.

### Re-injection after compression

After compression, key context is re-injected from the digest:

```typescript
// compact.ts:126-134
export const POST_COMPACT_TOKEN_BUDGET = 50_000; //Total budget
export const POST_COMPACT_MAX_FILES_TO_RESTORE = 5; // Restore up to 5 files
export const POST_COMPACT_MAX_TOKENS_PER_FILE = 5_000; // 5K token per file
export const POST_COMPACT_MAX_TOKENS_PER_SKILL = 5_000; // 5K token per skill
export const POST_COMPACT_SKILLS_TOKEN_BUDGET = 25_000; // Total skill budget 25K
```

This 50K token re-injection budget is used for:

1. Restore the contents of recently read files (up to 5 files, each truncated to 5K tokens)
2. Restore activated skill commands (each skill is truncated to 5K tokens, totaling 25K)
3. Re-inject CLAUDE.md content
4. Restore MCP tool discovery results

## CompactBoundary: Compacted boundary marker

Source code path: `src/utils/messages.ts` (`createCompactBoundaryMessage`)

After each compression, the system inserts a `SystemCompactBoundaryMessage` into the message stream:

```typescript
type SystemCompactBoundaryMessage = {
  type: "system";
  message: {
    type: "compact_boundary";
    compactMetadata: {
      compactType: "auto" | "manual" | "micro";
      preCompactTokenCount: number;
      lastUserMessageUuid: string;
      preCompactDiscoveredTools?: string[];
    };
  };
};
```

All subsequent operations will only process the messages after the last boundary:

```typescript
// messages.ts
export function getMessagesAfterCompactBoundary(
  messages: Message[],
): Message[] {
  const lastBoundary = messages.findLastIndex((m) =>
    isCompactBoundaryMessage(m),
  );
  return lastBoundary >= 0 ? messages.slice(lastBoundary + 1) : messages;
}
```

### Preserved Segment Notes

The boundary message is also appended with the `preservedSegment` annotation to record which messages are retained rather than compressed:

```typescript
// compact.ts — annotateBoundaryWithPreservedSegment
boundaryMarker.compactMetadata.preservedSegment = {
summaryMessageUuid: string
preservedMessageUuids: string[]
}
```

This helps the loader correctly rebuild the message chain when the session is restored, avoiding repeated compression of retained messages.

### Microcompact Boundary

Microcompact operations use a separate boundary type, different from the fully compressed `compact_boundary`:

```typescript
// src/utils/messages.ts:4599-4614
type SystemMicrocompactBoundaryMessage = {
  type: "system";
  subtype: "microcompact_boundary";
  content: "Context microcompacted";
  compactMetadata: {
    trigger: "auto"; // Microcompact only triggers automatically
    preTokens: number; // Number of tokens before compression
    tokensSaved: number; // Number of tokens saved
    compactedToolIds: string[]; // List of compressed tool IDs
    clearedAttachmentUUIDs: string[]; // Cleared attachment UUIDs
  };
};
```

Difference from `compact_boundary`:

- **Keep original message**: Microcompact only clears the tool output, not the message itself
- **Traceability**: `compactedToolIds` records which tool results were cleared
- **Lightweight**: no summary generation, no API calls

## PTL emergency downgrade: Prompt Too Long

When the token limit is still exceeded after compression (`PROMPT_TOO_LONG` error), the system will enter the emergency downgrade path:

1. **Reactive Compact**: `reactiveCompactOnPromptTooLong()` attempts more aggressive compression
2. **Truncate and retry**: If reactive also fails, `truncateHeadForPTLRetry()` directly truncates the earliest message
3. Give up and report an error

Reactive Compact is currently a stub (`isReactiveOnlyMode() → false`) in the decompiled version, indicating that this is an experimental feature internal to Anthropic.

## Compressed Hook mechanism

Custom Hooks can be executed before and after compression:

- **Pre-compact Hook** (`executePreCompactHooks`): executed before compression, can inject "must retain" tags
- **Post-compact Hook** (`executePostCompactHooks`): executed after compression, you can verify whether key information is retained
- **Session Start Hook** (`processSessionStartHooks('compact')`): SM compression uses this Hook to restore contexts such as CLAUDE.md

Hook results are appended to the compression results in the form of `HookResultMessage`, ensuring that user-defined logic is respected during the compression process.

## Snip Compact (Experimental)

Source code path: `src/services/compact/snipCompact.ts` (stub)

Snip Compact is another experimental compression strategy, implemented as an empty shell in the decompiled version. Inferred from the stub's type signature:

```typescript
snipCompactIfNeeded(messages, options?: { force?: boolean }) → {
  messages: Message[]
  executed: boolean
  tokensFreed: number
  boundaryMessage?: Message
}
```

It appears to be a more fine-grained message-level pruning (snip = snipping), possibly further compression of individual messages rather than entire conversations. `shouldNudgeForSnips()` and `SNIP_NUDGE_TEXT` imply that it may be triggered by prompting the user.
