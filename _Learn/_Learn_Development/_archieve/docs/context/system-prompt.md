---
title: "System Prompt Dynamic Assembly - AI Working Memory Construction"
description: "In-depth analysis of Claude Code's System Prompt dynamic assembly process: caching strategies, boundarymarkers, Section registry, CLAUDE.md multi-level merging, and how to assemble scattered context into API-consumable cache-friendly structures."
keywords:
  [
    "System Prompt",
    "System Prompt Word",
    "Dynamic Assembly",
    "CLAUDE.md",
    "Prompt Cache",
    "Cache Strategy",
  ]
---

## From Array to API Call: The Complete Linkage of System Prompt

System Prompt in Claude Code is not a fixed text but a **`string[]` array** (branded type `SystemPrompt`, defined in `src/utils/systemPromptType.ts:8`), assembled, chunked, cache-marked, and sent to the API.

### Three-stage pipeline

```
getSystemPrompt()          →  string[]       （Assembled content）
  ↓
buildEffectiveSystemPrompt() →  SystemPrompt   （Priority selection path）
  ↓
buildSystemPromptBlocks()  →  TextBlockParam[] （Chunking + cache_control marking）
```

1. **`getSystemPrompt()`**（`src/constants/prompts.ts:444`）—— Collects static segments + dynamic segments, inserting `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` boundary marker
2. **`buildEffectiveSystemPrompt()`**（`src/utils/systemPrompt.ts:41`）—— Selects by Override > Coordinator > Agent > Custom > Default priority
3. **`buildSystemPromptBlocks()`**（`src/services/api/claude.ts:3279`）—— Calls `splitSysPromptPrefix()` for chunking, appending `cache_control` to each block

## SystemPrompt Branded Type

```typescript
// packages/@ant/model-provider/src/types/systemPrompt.ts:4
export type SystemPrompt = readonly string[] & {
  readonly __brand: "SystemPrompt";
};
export function asSystemPrompt(value: readonly string[]): SystemPrompt {
  return value as SystemPrompt; // Zero-cost type assertion
}
```

Branded type prevents ordinary `string[]` from being passed to API calls—only by explicitly converting through `asSystemPrompt()` can `SystemPrompt` type be obtained.

## getSystemPrompt(): Content Assembly Overview

`src/constants/prompts.ts:444` is the core factory function for System Prompt, returning an ordered array:

| Stage        | Content                                                                                                                                                    | Cache Policy                                                                                           |
| ------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Static**   | Intro Section、System Rules、Doing Tasks、Actions、Using Tools、Tone & Style、Output Efficiency                                                            | Cross-organization cacheable (`scope: 'global'`)                                                       |
| **BOUNDARY** | `SYSTEM_PROMPT_DYNAMIC_BOUNDARY = '__SYSTEM_PROMPT_DYNAMIC_BOUNDARY__'`                                                                                    | Boundary marker (not sent to API, used only to separate static and dynamic regions for global caching) |
| **Dynamic**  | Session Guidance、Memory、Model Override、Env Info、Language、Output Style、MCP Instructions、Scratchpad、FRC、Summarize Tool Results、Token Budget、Brief | Different for each session (`scope: 'org'` or no cache)                                                |

> **What is Boundary?**: It divides System Prompt into a "constant static region" and a "dynamic region that varies with user/session". The static region is the same for all users and can obtain `scope: 'global'` cross-organization caching; the dynamic region is different for each session and can only be `scope: 'org'` or not cached. It is itself a special string that is removed before being sent to the API, and the AI never sees it.

### Dynamic Section Registry

Dynamic regions are registered through `systemPromptSection()` / `DANGEROUS_uncachedSystemPromptSection()`, defined in `src/constants/systemPromptSections.ts`:

```typescript
// Cached section: calculated once, only recalculated after /clear or /compact
systemPromptSection("memory", () => loadMemoryPrompt());

// Dangerous: recalculates every turn, which breaks Prompt Cache
DANGEROUS_uncachedSystemPromptSection(
  "mcp_instructions",
  () =>
    isMcpInstructionsDeltaEnabled()
      ? null
      : getMcpInstructionsSection(mcpClients),
  "MCP servers connect/disconnect between turns", // must provide reason to break cache
);
```

`resolveSystemPromptSections()` parses all Sections. For sections with `cacheBreak: false`, it preferentially uses the cached value in `getSystemPromptSectionCache()`. Only truly dynamic content like MCP instructions uses `DANGEROUS_uncachedSystemPromptSection`.

### `CLAUDE_CODE_SIMPLE` Fast Path

When the `CLAUDE_CODE_SIMPLE` environment variable is true, the entire System Prompt is reduced to one line:

```typescript
`You are Claude Code, Anthropic's official CLI for Claude.\n\nCWD: ${getCwd()}\nDate: ${getSessionStartDate()}`;
```

Skips all Section registration, chunking, and dynamic assembly - used for minimal token consumption in test scenarios.

## buildEffectiveSystemPrompt(): Five-Level Priority

`src/utils/systemPrompt.ts:41` determines which System Prompt to use:

| Priority           | Condition                                         | Behavior                                                                            |
| ------------------ | ------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **0. Override**    | `overrideSystemPrompt` is not empty               | Completely replaces, returns `[override]`                                           |
| **1. Coordinator** | `COORDINATOR_MODE` feature + environment variable | Uses coordinator-specific prompt                                                    |
| **2. Agent**       | `mainThreadAgentDefinition` exists                | Proactive mode: appended to default prompt tail; otherwise: replaces default prompt |
| **3. Custom**      | `--system-prompt` parameter specified             | Replaces default prompt                                                             |
| **4. Default**     | No special conditions                             | Uses `getSystemPrompt()` full output                                                |

`appendSystemPrompt` always appends to the tail (except Override).

## Provider System Overview

Claude Code supports multiple API providers, divided into two major categories:

| Category             | Provider     | Environment Variable        | Description                                    |
| -------------------- | ------------ | --------------------------- | ---------------------------------------------- |
| **1P (First Party)** | `firstParty` | Default                     | Anthropic Official API direct connection       |
| **3P (Third Party)** | `bedrock`    | `CLAUDE_CODE_USE_BEDROCK=1` | AWS Bedrock hosted service                     |
| **3P**               | `vertex`     | `CLAUDE_CODE_USE_VERTEX=1`  | Google Vertex AI                               |
| **3P**               | `openai`     | `CLAUDE_CODE_USE_OPENAI=1`  | OpenAI compatible layer (Ollama/DeepSeek/vLLM) |
| **3P**               | `gemini`     | `CLAUDE_CODE_USE_GEMINI=1`  | Google Gemini API                              |
| **3P**               | `grok`       | `CLAUDE_CODE_USE_GROK=1`    | xAI Grok                                       |

Provider determines:

- **Available beta headers**: some beta features are only available to 1P users
- **Cache strategy**: global cache `scope: 'global'` is only available to 1P
- **Token counting method**: Bedrock has a separate countTokens endpoint, OpenAI/Gemini rely on estimation

```typescript
// src/utils/model/providers.ts:5-13
export type APIProvider =
  | "firstParty" // 1P - Anthropic direct connection
  | "bedrock" // 3P - AWS Bedrock
  | "vertex" // 3P - Google Vertex
  | "foundry" // 3P - Anthropic Foundry
  | "openai" // 3P - OpenAI compatible layer
  | "gemini" // 3P - Google Gemini
  | "grok"; // 3P - xAI Grok
```

## Cache Strategy: Chunking, Marking, Hit

This is the most sophisticated part of the System Prompt design.

### Anthropic Prompt Cache Foundation

Anthropic API's Prompt Cache allows reuse of the same System Prompt prefix across requests, billed by cache hits (far cheaper than full input price). The cache key is determined by the Blake2b hash of the content - any character change will cause cache invalidation.

### `splitSysPromptPrefix()`: Three Chunking Modes

`src/utils/api.ts:321` is the core of the cache strategy, selecting three chunking modes based on conditions:

#### Mode 1: When MCP Tools Exist (`skipGlobalCacheForSystemPrompt=true`)

```
[attribution header]    → cacheScope: null     (not cached)
[system prompt prefix]  → cacheScope: 'org'    (organization-level cache)
[everything else]       → cacheScope: 'org'    (organization-level cache)
```

MCP tool list may change during the session (connected/disconnected), destroying the basis for cross-organization caching, so it's downgraded to the organization level.

#### Mode 2: Global Cache + Boundary Exists (1P Only)

```
[attribution header]    → cacheScope: null     (not cached)
[system prompt prefix]  → cacheScope: null     (not cached)
[static content]        → cacheScope: 'global' (global cache! cross-org sharing)
[dynamic content]       → cacheScope: null     (not cached)
```

This is the mode with the highest cache efficiency. The static content before `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` (Intro, Rules, Tone & Style, etc.) is the same for all users and can be cached across organizations.

> **Boundary Insertion Condition**: The `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` marker is inserted **only under specific conditions**:

```typescript
// src/utils/betas.ts:226-229
export function shouldUseGlobalCacheScope(): boolean {
  return (
    getAPIProvider() === "firstParty" &&
    !isEnvTruthy(process.env.CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS)
  );
}
```

```typescript
// src/constants/prompts.ts:574
...(shouldUseGlobalCacheScope() ? [SYSTEM_PROMPT_DYNAMIC_BOUNDARY] : []),
```

This means:

- **3P Users (Bedrock/Vertex/OpenAI/Gemini)**: Boundary never exists, always uses Mode 3
- **1P Users disabling experimental features**: Set `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS=1`, Boundary is not inserted
- **1P Users default**: Boundary exists, uses Mode 2 (highest cache efficiency)

#### Mode 3: Default (3P Provider or Boundary Missing)

```
[attribution header]    → cacheScope: null     (not cached)
[system prompt prefix]  → cacheScope: 'org'    (organization-level cache)
[everything else]       → cacheScope: 'org'    (organization-level cache)
```

### `getCacheControl()`: TTL Decision

`src/services/api/claude.ts:348` generates the `cache_control` object:

```typescript
{
  type: 'ephemeral',
  ttl?: '1h',         // Only when specific querySource matches
  scope?: 'global',   // Only static region
}
```

The 1-hour TTL decision logic (`should1hCacheTTL()`, line 383):

- **Bedrock Users**: Enabled via environment variable `ENABLE_PROMPT_CACHING_1H_BEDROCK`
- **1P Users**: Matches `querySource` against the `allowlist` array in GrowthBook configuration, supports prefix wildcards (e.g., `"repl_main_thread*"`)
- **Session-Level Locking**: Qualification decision is cached in the bootstrap state to prevent the same session from having inconsistent TTL due to mid-session changes in GrowthBook configuration

### Cache Destruction: Placement of Session-Specific Guidance

The content of `getSessionSpecificGuidanceSection()` (line 354 of `src/constants/prompts.ts`) must be placed **after** `SYSTEM_PROMPT_DYNAMIC_BOUNDARY`. Because it contains:

- Current session's enabledTools set
- Runtime decision of `isForkSubagentEnabled()`
- Result of `getIsNonInteractiveSession()`

These runtime bits would produce 2^N Blake2b hash variants (N = number of runtime conditions) if placed in the static region, completely destroying cache hit rates. The source code comments clearly warn:

> Each conditional here is a runtime bit that would otherwise multiply the Blake2b prefix hash variants (2^N). See PR #24490, #24171 for the same bug class.

### `CLAUDE_CODE_SIMPLE` Mode

When `CLAUDE_CODE_SIMPLE` environment variable is set, the entire system prompt is greatly reduced:

```typescript
return [
  `You are Claude Code, Anthropic's official CLI for Claude.\n\nCWD: ${getCwd()}\nDate: ${getSessionStartDate()}`,
];
```

## Context Injection: System Context and User Context

The System Prompt array itself does not contain runtime context (git status, CLAUDE.md content). Context is injected through two independent channels:

### System Context (`src/context.ts:116`)

```typescript
export const getSystemContext = memoize(async () => {
  return {
    gitStatus, // git branch, status, recent commits (truncated to MAX_STATUS_CHARS=2000)
    cacheBreaker, // cache breaker only for ant users
  };
});
```

- Uses `lodash.memoize` for caching, calculated **only once per session**
- Git status snapshot includes 5 parallel `git` commands (branch, defaultBranch, status, log, userName)
- `status` is truncated to 2000 characters with a prompt to use BashTool for more information
- When `systemPromptInjection` changes, `getUserContext.cache.clear?.()` is called to clear all context caches

### User Context (`src/context.ts:155`)

```typescript
export const getUserContext = memoize(async () => {
  return {
    claudeMd, // merged CLAUDE.md content
    currentDate, // "Today's date is YYYY-MM-DD."
  };
});
```

- **CLAUDE.md disable condition**: `CLAUDE_CODE_DISABLE_CLAUDE_MDS` environment variable, or `--bare` mode (unless explicitly specified directory through `--add-dir`)
- The meaning of `--bare` mode is "skip what I didn't ask for" rather than"ignore all"

### Injection position

At `src/query.ts:449`:

```typescript
// System Context appended to System Prompt tail
const fullSystemPrompt = asSystemPrompt(
  appendSystemContext(systemPrompt, systemContext), // simple concatenation
);
```

User Context is injected as the first user message wrapped in `<system-reminder>` tags through `prependUserContext()` (src/utils/api.ts:449), placed before all conversation messages.

## Attribution Header: Billing and Security

The first block of each API request's System Prompt is the Attribution Header (src/constants/system.ts:30), containing:

- **`cc_version`**: Claude Code version + fingerprint
- **`cc_entrypoint`**: entry point identifier (REPL / SDK / pipe, etc.)
- **`cch=00000`** (when NATIVE_CLIENT_ATTESTATION is enabled): the Bun native HTTP layer replaces zero with a calculated hash value before sending. The server verifies this token to confirm that the request comes from the real Claude Code client

The header always has `cacheScope: null` - it varies with version and fingerprint, so it is not suitable for caching.

## CLAUDE.md: Project-Level Knowledge Injection

This is one of Claude Code's most ingenious designs. Placing a `CLAUDE.md` file in the project root allows the AI to "understand" your project:

- **Project Overview**: What this project does, what technologies it uses
- **Development Conventions**: Code style, naming conventions, branching strategy
- **Common Commands**: How to build, test, and deploy
- **Precautions**: Known pitfalls, special configurations

Automatically discovering and merging multi-level CLAUDE.md:

```
~/.claude/CLAUDE.md              ← user global (personal preference)
  └── /project/CLAUDE.md         ← project root (team sharing)
        └── /project/src/CLAUDE.md  ← subdirectory (module-specific)
```

Loading logic is implemented in `getClaudeMds()` and `getMemoryFiles()` in `src/utils/claudemd.ts` - traverses the directory tree from CWD upward, merging all matching CLAUDE.md file contents.

## Design Insights: Why `string[]` and Not a Single `string`

Designing the System Prompt as an array instead of a single block of text is for **cache segmentation**:

1. Anthropic Prompt Cache takes the **content block** (TextBlock) as the cache unit
2. Splitting the System Prompt into multiple blocks allows immutable parts (Intro, Rules) to obtain independent cache hits
3. If it were a single `string`, any character change (such as date update) would cause the entire System Prompt's cache to fail
4. The `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` marker allows `splitSysPromptPrefix()` to precisely mark the static region as `scope: 'global'`, and the dynamic region is not marked or marked as `scope: 'org'`

This is the core design of Claude Code for token cost optimization - a typical System Prompt is about 20K+ tokens, and cache segmentation can save 30-50% of input token costs.

## OpenAI and Gemini Compatible Layers

Claude Code provides OpenAI and Gemini protocol compatible layers, allowing the use of non-Anthropic endpoints.

### OpenAI Compatibility Layer

Enabled by `CLAUDE_CODE_USE_OPENAI=1`, supports any OpenAI Chat Completions protocol endpoint (Ollama, DeepSeek, vLLM, etc.).

Implemented using **stream adapter pattern**:

1. Convert Anthropic format requests to OpenAI format
2. Call OpenAI compatible endpoint
3. Convert SSE stream back to `BetaRawMessageStreamEvent`
4. Downstream code is completely unaware

```
src/services/api/openai/
├── client.ts           # OpenAI client configuration
├── convertMessages.ts  # Message format conversion (Anthropic → OpenAI)
├── convertTools.ts     # Tool definition conversion
├── streamAdapter.ts    # SSE stream adaptation (OpenAI → Anthropic)
├── modelMapping.ts     # Model name mapping
└── index.ts            # Entry function queryModelOpenAI()
```

Key environment variables:

- `CLAUDE_CODE_USE_OPENAI=1` — enable OpenAI provider
- `OPENAI_API_KEY` — API key
- `OPENAI_BASE_URL` — API endpoint (default `https://api.openai.com/v1`)
- `OPENAI_MODEL` — directly specify model name

### Gemini Compatibility Layer

Enabled by `CLAUDE_CODE_USE_GEMINI=1`, supports Google Gemini API.

```
src/services/api/gemini/
├── client.ts           # Gemini client configuration
├── convertMessages.ts  # Message format conversion
├── convertTools.ts     # Tool definition conversion
├── streamAdapter.ts    # Stream adaptation
├── modelMapping.ts     # Model name mapping
├── types.ts            # Type definition
└── index.ts            # Entry function
```

Key environment variables:

- `CLAUDE_CODE_USE_GEMINI=1` — enable Gemini provider
- `GEMINI_API_KEY` — API key
- `GEMINI_BASE_URL` — API endpoint (default `https://generativelanguage.googleapis.com/v1beta`)
- `GEMINI_MODEL` — directly specify model name
- `GEMINI_DEFAULT_SONNET_MODEL` / `GEMINI_DEFAULT_OPUS_MODEL` — mapping by capability level

### Limitations of Compatible Layers

When using 3P compatible layers, some features are limited:

- **No precise token counting** - system falls back to approximate estimation, affecting automatic compression trigger timing
- **No global cache** - can only use organization-level cache `scope: 'org'`
- **Some beta features unavailable** - features depending on Anthropic-specific beta headers are restricted

See `docs/plans/openai-compatibility.md` and the relevant sections in `CLAUDE.md`.
