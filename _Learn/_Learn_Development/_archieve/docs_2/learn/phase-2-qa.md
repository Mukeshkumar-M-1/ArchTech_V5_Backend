# Phase 2 Q&A

## Q1: What is the specific streaming message processing in query.ts?

**Core Question**: How is each message yielded from `deps.callModel()` processed in the `for await` loop body (L659-866) of `queryLoop()`?

### Scenario

User says: **"Help me see the content of package.json"**

Model response: Text "I will read the file." + a `Read` tool call.

### Complete message sequence of callModel yield

`queryModel()` in `claude.ts` will yield two types of messages:

| Type tag | Meaning | Output timing |
|---------|------|---------|
| `stream_event` | Raw SSE event wrapper | One yielded for each SSE event |
| `assistant` | Complete AssistantMessage | Yielded only upon `content_block_stop` |

In this example, `callModel` yields **a total of 13 messages** in sequence:

```
#1 { type: 'stream_event', event: { type: 'message_start', ... }, ttftMs: 342 }
#2 { type: 'stream_event', event: { type: 'content_block_start', index: 0, content_block: { type: 'text' } } }
#3 { type: 'stream_event', event: { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: 'I'll' } } }
#4 { type: 'stream_event', event: { type: 'content_block_delta', index: 0, delta: { type: 'text_delta', text: ' read the file.' } } }
#5 { type: 'stream_event', event: { type: 'content_block_stop', index: 0 } }
#6 { type: 'assistant', uuid: 'uuid-1', message: { content: [{ type: 'text', text: 'I will read the file.' }], stop_reason: null } }
#7 { type: 'stream_event', event: { type: 'content_block_start', index: 1, content_block: { type: 'tool_use', id: 'toulu_001', name: 'Read' } } }
#8 { type: 'stream_event', event: { type: 'content_block_delta', index: 1, delta: { type: 'input_json_delta', partial_json: '{"file_path":' } } }
#9 { type: 'stream_event', event: { type: 'content_block_delta', index: 1, delta: { type: 'input_json_delta', partial_json: '"/path/package.json"}' } } }
#10 { type: 'stream_event', event: { type: 'content_block_stop', index: 1 } }
#11 { type: 'assistant', uuid: 'uuid-2', message: { content: [{ type: 'tool_use', id: 'toulu_001', name: 'Read', input: { file_path: '/path/package.json' } }], stop_reason: null } }
#12 { type: 'stream_event', event: { type: 'message_delta', delta: { stop_reason: 'tool_use' }, usage: { output_tokens: 87 } } }
#13 { type: 'stream_event', event: { type: 'message_stop' } }
```

Note that `#6` and `#11` are of type **`assistant`** (assembled by `claude.ts` at `content_block_stop`), while the rest are of type **`stream_event`**.

### Loop Body Structure

The loop body is at L708-866, with the following structure:

```
for await (const message of deps.callModel({...})) { // L659
    // A. Downgrade check (L712)
    // B. backfill (L747-789)
    // C. withheld check (L801-824)
    // D. yield (L825-827)
    // E. assistant collection + addTool (L828-848)
    // F. getCompletedResults (L850-865)
}
```

### Walkthrough of the Loop

#### #1 stream_event (message_start)

```
A. L712: streamingFallbackOccured = false → skip

B. L748: message.type === 'assistant'?
   → 'stream_event' !== 'assistant' → skip entire backfill block

C. L801-824: withheld check
   → Not assistant type, all checks are false → withheld = false

D. L825: yield message ✅ → Transparently passed to REPL (REPL records ttftMs)

E. L828: message.type === 'assistant'? → No → skip

F. L850-854: streamingToolExecutor.getCompletedResults()
   → tool array is empty → no results
```

**Net Effect**: `yield` transparently passed.

---

#### #2 stream_event (content_block_start, type: text)

```
A-C. Same as #1
D. yield message ✅ → REPL sets spinner to "Responding..."
E-F. Same as #1
```

**Net Effect**: `yield` transparently passed.

---

#### #3 stream_event (text_delta: "I'll")

```
A-C. Same as #1
D. yield message ✅ → REPL appends streamingText += "I'll" (Typewriter effect)
E-F. Same as #1
```

**Net Effect**: `yield` transparently passed.

---

#### #4 stream_event (text_delta: " read the file.")

```
Same as #3
D. yield message ✅ → REPL streamingText += " read the file."
```

**Net Effect**: `yield` transparently passed.

---

#### #5 stream_event (content_block_stop, index:0)

```
Same as #2
D. yield message ✅ → REPL no special action (the actual AssistantMessage is in next #6)
```

**Net Effect**: `yield` transparently passed.

---

#### #6 assistant (Text block complete message) ★

The first message with `type: 'assistant'` takes a completely different path:

```
A. L712: streamingFallbackOccured = false → skip

B. L748: message.type === 'assistant'? → ✅ Enter backfill
   L750: contentArr = [{ type: 'text', text: 'I will read the file.' }]
   L752: for i=0: block.type === 'text'
   L754: block.type === 'tool_use'? → No → skip
   L783: cloneContent is undefined → yieldMessage = message (unchanged)

C. L801: let withheld = false
   L802: feature('CONTEXT_COLLAPSE') → false → skip
   L813: reactiveCompact?.isWithheldPromptTooLong(message) → no → false
   L822: isWithheldMaxOutputTokens(message)
         → message.message.stop_reason === null → false
   → withheld = false

D. L825: yield message ✅ → REPL clears streamingText and adds complete text message to list

E. L828: message.type === 'assistant'? → ✅
   L830: assistantMessages.push(message)
         → assistantMessages = [uuid-1(text)]

   L832-834: msgToolUseBlocks = content.filter(type === 'tool_use')
             → [] (this is a text block, no tool_use)

   L835: length > 0? → No → No needsFollowUp
   L844: msgToolUseBlocks is empty → do not call addTool

F. L854: getCompletedResults() → empty
```

**Net Effect**: `yield` message + `assistantMessages` added. `needsFollowUp` remains `false`.

---

#### #7 stream_event (content_block_start, tool_use: Read)

```
A-C. Same as stream_event common path
D. yield message ✅ → REPL sets spinner to "tool-input" and adds streamingToolUse
E. Not assistant → skip
F. getCompletedResults() → empty
```

---

#### #8 stream_event (input_json_delta: `'{"file_path":'')

```
D. yield message ✅ → REPL appends tool input JSON fragment
F. getCompletedResults() → empty
```

---

#### #9 stream_event (input_json_delta: '"/path/package.json"}')

```
D. yield message ✅
F. getCompletedResults() → empty
```

---

#### #10 stream_event (content_block_stop, index:1)

```
D. yield message ✅
F. getCompletedResults() → empty
```

---

#### #11 assistant (tool_use block complete message) ★★

This is the **most critical** — triggering tool execution:

```
A. L712: streamingFallbackOccured = false → skip

B. L748: message.type === 'assistant'? → ✅ Enter backfill
   L750: contentArr = [{ type: 'tool_use', id: 'toulu_001', name: 'Read',
                          input: { file_path: '/path/package.json' } }]
   L752: for i=0:
   L754: block.type === 'tool_use'? → ✅
   L756: typeof block.input === 'object' && !== null? → ✅
   L759: tool = findToolByName(tools, 'Read') → Read tool definition
   L763: tool.backfillObservableInput exists? → Assumed to exist
   L764-766: inputCopy = { file_path: '/path/package.json' }
             tool.backfillObservableInput(inputCopy)
             → Potentially adds absolutePath field
   L773-776: addedFields? → Assume new fields exist
             clonedContent = [...contentArr]
             clonedContent[0] = { ...block, input: inputCopy }
   L783-788: yieldMessage = {
                ...message, // uuid, type, timestamp remain unchanged
                message: {
                  ...message.message, // stop_reason, usage unchanged
                  content: clonedContent // ★ Replaced with copy containing absolutePath
                }
              }
              // ★ Original message remains unchanged (for API return to ensure cache consistency)

C. L801-824: withheld check → all false → withheld = false

D. L825: yield yieldMessage ✅
         → Yields cloned version (with backfill fields), used by REPL and SDK
         → Original message remains in assistantMessages, returned to API to ensure cache consistency.

E. L828: message.type === 'assistant'? → ✅
   L830: assistantMessages.push(message) // ★ Pushes ORIGINAL message, not yieldMessage
         → assistantMessages = [uuid-1(text), uuid-2(tool_use)]

   L832-834: msgToolUseBlocks = content.filter(type === 'tool_use')
             → [{ type: 'tool_use', id: 'toulu_001', name: 'Read', input: {...} }]

   L835: length > 0? → ✅
   L836: toolUseBlocks.push(...msgToolUseBlocks)
         → toolUseBlocks = [Read_block]
   L837: needsFollowUp = true // ★★★ Determines while(true) will NOT terminate
   
   L840-842: streamingToolExecutor exists ✓ && !aborted ✓
   L844-846: for (const toolBlock of msgToolUseBlocks):
             streamingToolExecutor.addTool(Read_block, uuid-2 message)
             // ★★★ Tool starts executing!
             // → Inside StreamingToolExecutor:
             // isConcurrencySafe = true (Read is safe)
             // queued → processQueue() → canExecuteTool() → true
             // → executeTool() → runToolUse() → Asynchronously reads file in background

F. L850-854: getCompletedResults()
   → Read just started executing, status = 'executing' → No completed results yet
```

**Net Effect**:
- `yield` cloned message (with backfill fields)
- `assistantMessages` pushes original message
- `needsFollowUp = true`
- **Read tool starts asynchronous execution in background**

---

#### #12 stream_event (message_delta, stop_reason: 'tool_use')

```
A-C. Same as stream_event common path
D. yield message ✅

E. Not assistant → skip

F. L854: getCompletedResults()
   → ★ Read may have finished by now! (File reading is usually <1ms)
   → if completed: status = 'completed', results has values
     L428(StreamingToolExecutor): tool.status = 'yielded'
     L431-432: yield { message: UserMsg(tool_result) }
   → Back to query.ts:
     L855: result.message exists
     L856: yield result.message ✅ → REPL displays tool results
     L857-862: toolResults.push(normalizeMessagesForAPI([result.message])...)
               → toolResults = [Read tool_result]
```

**Net Effect**: `yield` stream_event + **may yield tool results** if tool execution completed.

---

#### #13 stream_event (message_stop)

```
D. yield message ✅
F. getCompletedResults()
   → if Read already harvested at #12 → empty
   → if Read just completed → yield tool result (same as F logic in #12)
```

---

### After for await Loop Exits

```
L1018: aborted? → false → skip

L1065: if (!needsFollowUp)
       → needsFollowUp = true → do not enter → skip termination logic

L1383: toolUpdates = streamingToolExecutor.getRemainingResults()
       → If Read already harvested at #12/#13 → returns empty immediately
       → If Read not yet completed → Blocks and waits → Yields result upon completion

L1387-1404: for await (const update of toolUpdates) {
              yield update.message → REPL displays
              toolResults.push(...) → collects
            }

L1718-1730: Build next State:
  state = {
    messages: [
      ...messagesForQuery, // [UserMessage("Help me see...")]
      ...assistantMessages, // [AssistantMsg(text), AssistantMsg(tool_use)]
      ...toolResults, // [UserMsg(tool_result)]
    ],
    turnCount: 1,
    transition: { reason: 'next_turn' },
  }
  → continue → while(true) 2nd iteration → Initiates next API call with tool results
```

### Summary of Loop Body Decision Tree

```
for await (const message of deps.callModel(...)) {
    │
    ├─ message.type === 'stream_event'?
    │ │
    │ └─ YES → Almost zero operations
    │ ├─ yield message (Transparently passed to REPL for real-time UI)
    │ └─ getCompletedResults() (Briefly checks for completed tools)
    │
    └─ message.type === 'assistant'?
        │
        ├─ B. backfill: tool_use present + backfillObservableInput?
        │ ├─ YES → Clone message, yield clone (original reserved for API return)
        │ └─ NO → yield original message
        │
        ├─ C. withheld: prompt_too_long / max_output_tokens?
        │ ├─ YES → No yield (withheld until subsequent recovery logic)
        │ └─ NO → yield
        │
        ├─ E. assistantMessages.push(original message)
        │
        ├─ E. tool_use block present?
        │ ├─ YES → toolUseBlocks.push()
        │ │ + needsFollowUp = true
        │ │ + streamingToolExecutor.addTool() → ★ Start tool execution immediately
        │ └─ NO → do nothing
        │
        └─ F. getCompletedResults() → Harvest any completed tool results
}
```

**One-sentence Summary**: `stream_event` is transparently passed but not processed; `assistant` messages are the "real cargo" — they are collected, checked for withholding, triggered for execution immediately upon tool availability, and used to harvest any tool results completed along the way.