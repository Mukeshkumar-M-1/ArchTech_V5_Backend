# EXPERIMENTAL_SKILL_SEARCH — Semantic Skill Search

> Feature Flag: `FEATURE_EXPERIMENTAL_SKILL_SEARCH=1`
> Implementation Status: All stubbed (8 files); wiring is complete.
> Reference Count: 21

## I. Feature Overview

`EXPERIMENTAL_SKILL_SEARCH` provides the `DiscoverSkills` tool, which semantically searches for available skills based on the current task. The goal is to enable the model to automatically discover and recommend relevant skills (both local and remote) during task execution, eliminating the need for manual user searches.

## II. Implementation Architecture

### 2.1 Module Status

| Module | File | Status | Description |
| :--- | :--- | :--- | :--- |
| **DiscoverSkillsTool** | `src/tools/DiscoverSkillsTool/prompt.ts` | **Stub** | Empty tool name. |
| **Prefetching** | `src/services/skillSearch/prefetch.ts` | **Stub** | 3 functions are no-ops. |
| **Remote Loading** | `src/services/skillSearch/remoteSkillLoader.ts` | **Stub** | Returns empty results. |
| **Remote State** | `src/services/skillSearch/remoteSkillState.ts` | **Stub** | Returns null/undefined. |
| **Signals** | `src/services/skillSearch/signals.ts` | **Stub** | `DiscoverySignal = any`. |
| **Telemetry** | `src/services/skillSearch/telemetry.ts` | **Stub** | No-op logging. |
| **Local Search** | `src/services/skillSearch/localSearch.ts` | **Stub** | No-op caching. |
| **Feature Check** | `src/services/skillSearch/featureCheck.ts` | **Stub** | `isSkillSearchEnabled => false`. |
| **SkillTool Integration** | `src/tools/SkillTool/SkillTool.ts` | **Wired** | Dynamically loads all remote skill modules. |
| **Prompt Integration** | `src/constants/prompts.ts` | **Wired** | `DiscoverSkills` schema injection. |

### 2.2 Expected Data Flow

```
Model processes user task
      │
      ▼
DiscoverSkills tool triggers [TO BE IMPLEMENTED]
      │
      ├── Local Search: Index metadata of installed skills
      │   └── localSearch.ts → Match skill names/descriptions/keywords
      │
      └── Remote Search: Query skill marketplace/registry
          └── remoteSkillLoader.ts → Fetch and parse
      │
      ▼
Results sorting and filtering
      │
      ▼
Return recommended skills list
      │
      ▼
Model uses SkillTool to call recommended skills
```

### 2.3 Prefetching Mechanism

`prefetch.ts` is expected to analyze message content before the user submits input, allowing for early search of relevant skills:

- `startSkillDiscoveryPrefetch()` — Initiates prefetching.
- `collectSkillDiscoveryPrefetch()` — Collects prefetch results.
- `getTurnZeroSkillDiscovery()` — Obtains skill discovery results for turn 0.

## III. Missing Implementations

| Priority | Module | Effort | Description |
| :--- | :--- | :--- | :--- |
| 1 | `DiscoverSkillsTool` | Large | Semantic search tool schema and execution. |
| 2 | `skillSearch/prefetch.ts` | Medium | User input analysis and prefetch logic. |
| 3 | `skillSearch/remoteSkillLoader.ts` | Large | Remote marketplace/registry fetching. |
| 4 | `skillSearch/remoteSkillState.ts` | Small | State management for discovered skills. |
| 5 | `skillSearch/localSearch.ts` | Medium | Local index construction and querying. |
| 6 | `skillSearch/featureCheck.ts` | Small | GrowthBook and configuration gating. |
| 7 | `skillSearch/signals.ts` | Small | `DiscoverySignal` type definition. |

## IV. Key Design Decisions

1.  **Prefetch Optimization**: Start searching before the user submits to reduce initial response latency.
2.  **Dual Local/Remote Search**: Rapid matching via local index combined with deep searching in the remote marketplace.
3.  **SkillTool Integration**: Discovered skills are invoked via `SkillTool`, requiring no new calling mechanism.
4.  **Independence from MCP_SKILLS**: `MCP_SKILLS` discovers skills from MCP servers, whereas `EXPERIMENTAL_SKILL_SEARCH` discovers them from the skill marketplace.

## V. Usage

```bash
# Enable the feature (requires implementation to be functional)
FEATURE_EXPERIMENTAL_SKILL_SEARCH=1 bun run dev
```

## VI. File Index

| File | Responsibility |
| :--- | :--- |
| `src/tools/DiscoverSkillsTool/prompt.ts` | Tool schema (stub). |
| `src/services/skillSearch/prefetch.ts` | Prefetch logic (stub). |
| `src/services/skillSearch/remoteSkillLoader.ts` | Remote loading (stub). |
| `src/services/skillSearch/remoteSkillState.ts` | Remote state management (stub). |
| `src/services/skillSearch/signals.ts` | Signal types (stub). |
| `src/services/skillSearch/telemetry.ts` | Telemetry (stub). |
| `src/services/skillSearch/localSearch.ts` | Local search (stub). |
| `src/services/skillSearch/featureCheck.ts` | Feature verification (stub). |
| `src/tools/SkillTool/SkillTool.ts` | `SkillTool` integration point. |
| `src/constants/prompts.ts:95,335,778` | Prompt enhancement. |
