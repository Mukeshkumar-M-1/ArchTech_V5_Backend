# Langfuse Monitoring Integration

> Implementation Status: Completed; enabled via environment variables.
> Dependencies: `@langfuse/otel`, `@langfuse/tracing`, `@opentelemetry/sdk-trace-base`.

## I. Feature Overview

Langfuse is an open-source LLM observability platform used to track, monitor, and debug the request chains of AI applications. CCB integrates Langfuse into its query flow via an OpenTelemetry (OTel) bridge, enabling:

- **LLM Call Tracing**: Records the model, provider, inputs/outputs, and token usage for every API request.
- **Tool Execution Tracing**: Records the name, inputs, outputs, duration, and errors for every tool call.
- **Multi-Agent Tracing**: Independent trace chains for both main agents and subagents.
- **Data Sanitization**: Automatically masks sensitive information (API keys, file contents, shell output, etc.).

## II. Enablement

Langfuse is open-source and can be **self-hosted** (via Docker or Kubernetes) or tested for free using the official **[Langfuse Cloud](https://cloud.langfuse.com)**. After registering, obtain your keys from the **Project Settings → API Keys** page.

Only three core environment variables are required:

| Environment Variable | Description |
| :--- | :--- |
| `LANGFUSE_PUBLIC_KEY` | Langfuse public key (Required). |
| `LANGFUSE_SECRET_KEY` | Langfuse secret key (Required). |
| `LANGFUSE_BASE_URL` | Service URL. Defaults to `https://cloud.langfuse.com`. Change this to your address for self-hosted instances (Required). |

If these are not configured, all tracing functions become no-ops with zero overhead.

### Configuration via `settings.json` (Recommended)

Add these to the `env` field in `.claude/settings.json` to have them take effect automatically upon startup:

```json
{
  "env": {
    "LANGFUSE_PUBLIC_KEY": "pk-xxx",
    "LANGFUSE_SECRET_KEY": "sk-xxx",
    "LANGFUSE_BASE_URL": "https://cloud.langfuse.com"
  }
}
```

### Optional Parameters

| Environment Variable | Default Value | Description |
| :--- | :--- | :--- |
| `LANGFUSE_TRACING_ENVIRONMENT` | `development` | Environment label for filtering in the Langfuse dashboard. |
| `LANGFUSE_FLUSH_AT` | `20` | Threshold for the number of spans to send in a batch. |
| `LANGFUSE_FLUSH_INTERVAL` | `10` | Interval (in seconds) for timed flushes. |
| `LANGFUSE_EXPORT_MODE` | `batched` | Export mode: `batched` or `immediate`. |
| `LANGFUSE_TIMEOUT` | `5` | Request timeout in seconds. |

## IV. Architecture

### 4.1 Module Structure

```
src/services/langfuse/
├── index.ts          # Unified exports
├── client.ts         # OTel Provider + LangfuseSpanProcessor initialization
├── tracing.ts        # Trace/Span creation; LLM and tool observation recording
├── convert.ts        # Internal Message type → OpenAI-compatible format conversion
└── sanitize.ts       # Data sanitization (sensitive fields, file paths, tool outputs)
```

### 4.2 Trace Hierarchy

```
Trace (Agent Span)                    ← createTrace() / createSubagentTrace()
  ├── Generation (LLM call)           ← recordLLMObservation()
  ├── Tool Observation (Tool call)    ← recordToolObservation()
  ├── Tool Observation (Tool call)    ← recordToolObservation()
  └── ...
```

### 4.3 Data Flow

```
query.ts  ──→  createTrace()           # Create root trace for each query turn
  │
  ├── claude.ts  ──→  recordLLMObservation()   # Record LLM observation after API call
  │
  ├── toolExecution.ts  ──→  recordToolObservation()  # Record each tool execution
  │
  └── query.ts  ──→  endTrace()         # Close trace at end of turn

runAgent.ts  ──→  createSubagentTrace()  # Subagents have independent traces
```

## V. Tracing Details

### 5.1 Main Agent Trace

Each `query()` call (representing one user interaction turn) creates a root span of type `agent`:

- **Name**: `agent-run` or `agent-run:<querySource>`.
- **Metadata**: `provider`, `model`, `agentType: "main"`.
- **Session ID**: Associated with Langfuse Session features, supporting aggregation by conversation.

### 5.2 Subagent Trace

Subagents launched via `AgentTool` create independent traces:

- **Name**: `agent:<agentType>`.
- **Metadata**: `provider`, `model`, `agentType`, `agentId`.
- Independent of the main trace, with their own session associations.

### 5.3 LLM Generation

Each API call is recorded as a span of type `generation`:

- **Name**: Mapped by provider (e.g., `ChatAnthropic`, `ChatOpenAI`, `ChatBedrockAnthropic`).
- **Data Recorded**: Input messages, output messages, and token usage (input/output).
- **Timing**: Precisely records `startTime`, `endTime`, and `completionStartTime` (TTFT metrics).

**Provider Name Mapping:**

| Provider | Generation Name |
| :--- | :--- |
| `firstParty` | `ChatAnthropic` |
| `bedrock` | `ChatBedrockAnthropic` |
| `vertex` | `ChatVertexAnthropic` |
| `foundry` | `ChatFoundry` |
| `openai` | `ChatOpenAI` |
| `gemini` | `ChatGoogleGenerativeAI` |
| `grok` | `ChatXAI` |

### 5.4 Tool Execution

Each tool call is recorded as a span of type `tool`:

- **Name**: The tool name (e.g., `FileEditTool`, `BashTool`).
- **Data Recorded**: Inputs (sanitized), outputs (sanitized), and `toolUseId`.
- **Error Markers**: `isError` flag + `level: ERROR`.

## VI. Data Sanitization

All data uploaded to Langfuse passes through sanitization (`sanitize.ts`) to ensure sensitive information is not leaked:

### 6.1 Global Sanitization (`sanitizeGlobal`)

- **Home Path Replacement**: `/Users/xxx` → `~`.
- **Sensitive Field Masking**: Field values matching keywords like `api_key`, `token`, `secret`, `password`, `credential`, or `auth_header` are replaced with `[REDACTED]`.

### 6.2 Tool Input Sanitization (`sanitizeToolInput`)

- Sensitive field masking (same as global).
- Home directory replacement for paths in fields like `file_path`, `path`, and `directory`.

### 6.3 Tool Output Sanitization (`sanitizeToolOutput`)

| Tool | Sanitization Strategy |
| :--- | :--- |
| `FileReadTool`, `FileWriteTool`, `FileEditTool` | Fully masked; only character count is retained: `[file content redacted, N chars]`. |
| `BashTool`, `PowerShellTool` | Truncated to 500 characters. |
| `ConfigTool`, `MCPTool` | Fully masked. |
| Other Tools | Retained as-is. |

## VII. Message Format Conversion

`convert.ts` transforms internal CCB message types into the OpenAI-compatible format expected by Langfuse:

- **Input**: `UserMessage | AssistantMessage[]` + optional system prompt → `{ role, content }[]`.
- **Output**: `AssistantMessage[]` → `{ role: 'assistant', content }`.
- **Content Block Mapping**:
    - `text` → `{ type: 'text', text }`.
    - `thinking` / `redacted_thinking` → `{ type: 'thinking', thinking }`.
    - `tool_use` → `{ type: 'tool_use', id, name, input }`.
    - `tool_result` → `{ type: 'tool_result', tool_call_id, content }`.
    - `image` / `document` → Placeholder markers `[image]` or `[document: name]`.

## VIII. Lifecycle

1.  **Initialization**: `initLangfuse()` is called during startup in `src/entrypoints/init.ts`, creating the `LangfuseSpanProcessor` and `BasicTracerProvider`.
2.  **Runtime**: Tracing functions check `isLangfuseEnabled()`; if not configured, they return `null` or skip execution.
3.  **Shutdown**: `shutdownLangfuse()` is called upon process exit, forcing a flush and closing the processor.

## IX. Self-Hosting Langfuse

Langfuse is open-source and supports self-hosting via Docker or Kubernetes:

```bash
docker run -d \
  --name langfuse \
  -p 3000:3000 \
  -e DATABASE_URL=postgresql://... \
  langfuse/langfuse:latest
```

After self-hosting, point `LANGFUSE_BASE_URL` to your instance address. See the [Langfuse Self-Hosting Documentation](https://langfuse.com/docs/deployment/self-host) for details.

If you do not wish to self-host, use [Langfuse Cloud](https://cloud.langfuse.com), which offers a free tier for testing.

## X. Related Files

| File | Description |
| :--- | :--- |
| `src/services/langfuse/client.ts` | OTel Provider initialization and lifecycle management. |
| `src/services/langfuse/tracing.ts` | Trace/Span creation and observation recording. |
| `src/services/langfuse/convert.ts` | Message format conversion. |
| `src/services/langfuse/sanitize.ts` | Data sanitization logic. |
| `src/services/langfuse/__tests__/langfuse.test.ts`| Comprehensive tests (568 lines). |
| `src/query.ts` | Integration of tracing into the main query flow. |
| `src/services/tools/toolExecution.ts` | Observation recording during tool execution. |
| `packages/builtin-tools/src/tools/AgentTool/runAgent.ts`| Creation of subagent traces. |
