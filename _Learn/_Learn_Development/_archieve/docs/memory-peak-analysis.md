# Memory and Performance Peak Analysis Report

> Runtime: Bun | RSS Baseline: **682 MB** | Peak: **1.8 GB** | Date: 2026-05-02
> Status: **Investigation Complete** (12 iterations)
> Fixed Commits: `ef10ad28` + `ab0bbbc4` (Reduction: 100-300 MB)
> Architectural Limit: Bun's mimalloc/JSC do not return memory pages to the OS (~150-250 MB permanent overhead).

## Fixed Issues (10 Items)

| Issue | Original Peak | Fix | Location |
| :--- | :--- | :--- | :--- |
| **Streaming String O(n²)** | 2-20 MB | `+=` → Array accumulation | `claude.ts:1834,2271` |
| **Messages.tsx Traversals** | 100-270 MB | Merged into a single pass | `Messages.tsx:417-418` |
| **ColorFile Cache** | 50-100 MB | LRU-50 | `HighlightedCode.tsx:14-61` |
| **Ink StylePool (Unbounded)** | 10-50+ MB | 1000 entry limit | `@ant/ink/screen.ts:122` |
| **CompanionSprite Frequency** | CPU Peak | TICK_MS → 1000ms | `CompanionSprite.tsx:15` |
| **MCP stderr Buffering** | 1-640 MB | 64 → 8MB per server | `mcp-client/connection.ts:117` |
| **BashTool Output Buffers** | 30-330 MB | 32 → 2MB | `stringUtils.ts:88` |
| **Transcript Write Queue** | 5-50 MB | 1000 entry limit | `sessionStorage.ts:613-619` |
| **contentReplacementState** | Growth | Cleaned up via compact | `compact/compact.ts` |
| **SSE Buffering** | Unbounded | 1MB cap | SSE processing code |

## P0 — Core Bottlenecks (6 Items)

| # | Issue | Peak | Location | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **1** | **7-8x spread copies of message arrays** (3-4 copies reside in memory at turn end). | 120-320 MB | `query.ts` (7 locations: :477, :491, :897, :1135, :1745, :1857, :1878) | Remove spread; use pass-by-reference or `push`. |
| **2** | **AutoCompact Timing Defects** (Checks occur before API call; growth occurs after). | API Limit | `query.ts:575` | Implement predictive threshold checks. |
| **3** | **reactiveCompact Stubs** (No emergency compression on API 413). | No Fallback | `reactiveCompact.ts` | Replace stubs with functional logic. |
| **4** | **buildMessageLookups (8 Map/Set Rebuilds)** (Triggered on every streaming delta). | GC STW 100-173ms | `Messages.tsx:519` | Implement incremental updates or split `useMemo` chains. |
| **5** | **useDeferredValue Double Buffering** | 100-200 MB | `REPL.tsx:1569` | React scheduling inherent; limited optimization space. |
| **6** | **Compact Peak Window** (`preCompactReadFileState` + summary + attachments). | 20-80 MB | `compact.ts:524-644` | Release `preCompactReadFileState` and `summaryResponse` earlier. |

## P1 — Important Bottlenecks (14 Items)

| # | Issue | Peak | Location | Recommendation |
| :--- | :--- | :--- | :--- | :--- |
| **7** | **Compatibility Layer O(n²) Concatenation** (OpenAI/Gemini/Grok). | 25-75 MB | 9 locations across 3 files | Switch to array accumulation (same pattern as `claude.ts`). |
| **8** | **messages.ts O(n²) Concatenation** | 10-25 MB | `messages.ts:3252,3268` | Switch to array accumulation. |
| **9** | **highlight.js Full Grammar (192 languages)** | 8-12 MB | `color-diff-napi/index.ts:21` | Use custom build (target 26 languages). |
| **10** | **hlLineCache Singleton (2048 entries)** | ~4 MB | `color-diff-napi/index.ts:508` | Switch to LRU with size limits. |
| **11** | **colorFileCache (3x code storage)** | 2-5 MB | `HighlightedCode.tsx:14` | Remove `code` field from `value`. |
| **12** | **Virtual Scroll (200 permanent components)** | 50 MB | `useVirtualScroll.ts` | Reduce `OVERSCAN_ROWS` and `MAX_MOUNTED_ITEMS`. |
| **13** | **FileReadTool (Large files)** (100K output limit, but full file loads). | Several MB | `FileReadTool.ts:342` | Check size before reading; implement streaming truncation. |
| **14** | **Session Recovery (Full load)** (Disk → JSON → REPL pipeline). | 200-300 MB | `sessionStorage.ts:3482` | Use streaming JSONL or incremental recovery. |
| **15** | **Session Writes (100MB accumulation)** | ~100 MB | `sessionStorage.ts:652` | Use streaming writes. |
| **16** | **Forked Agent Cache Cloning** | 50N MB | `forkedAgent.ts:382` | Implement shared/layered caching. |
| **17** | **GC Threshold (350MB < Baseline)** (Excessive per-second GC). | CPU Waste | `cli/print.ts:554` | Increase to 800MB+. |
| **18** | **PDF Processing (100 pages)** | ~100 MB | `apiLimits.ts:54` | Implement paginated streaming. |
| **19** | **Image Processing (base64 → decode → resize)** | ~16 MB/img | `apiLimits.ts:22` | Implement streaming resize. |
| **20** | **Token Estimation Error (±25-50%)** | Threshold inaccuracy | `tokenEstimation.ts:215` | Use content-type aware estimation. |

## P2 — Minor Issues (10 Items)

| # | Issue | Peak | Location |
| :--- | :--- | :--- | :--- |
| **21** | `lastAPIRequestMessages` Retention | 30-50 MB | `bootstrap/state.ts:118` |
| **22** | MCP Tool Schema Double Storage | ~40 MB | `manager.ts:73` + `AppStateStore.ts:175` |
| **23** | `ContentReplacementState` Growth | 0.5-2 MB | `toolResultStorage.ts:390` |
| **24** | Perfetto 100K Events | ~30 MB | `perfettoTracing.ts:106` |
| **25** | `StreamingMarkdown` Double Render | Transient | `Markdown.tsx:185` |
| **26** | `MarkdownTable` Traversals | CPU Peak | `MarkdownTable.tsx:99` |
| **27** | Search Index WeakMap | 5-10 MB | `transcriptSearch.ts:17` |
| **28** | ACP `FileStateCache` / Session | 50 MB | `acp/agent.ts:554` |
| **29** | Agent `initialMessages` Shallow Copy | 1-5 MB/agent | `runAgent.ts:382` |
| **30** | Hook Result Accumulation | ~1 MB+ | `toolExecution.ts:1474` |

## CPU / Rendering Hotspots

| # | Issue | Impact | Location |
| :--- | :--- | :--- | :--- |
| **C2** | **Ink/Yoga Layout Trigger** (On every React commit). | ~1-3ms/commit | `reconciler.ts:279` → `ink.tsx:323` |
| **C3** | **MessageRow Mount (~1.5ms)** (React/Yoga/Ink pipeline). | ~290ms lag for batches | `useVirtualScroll.ts` |
| **C4** | **Layout Shift** (Triggers full screen damage). | O(rows × cols) | `ink.tsx:655-661` |
| **C9** | **Synchronous fs blocking** (Blocks main thread). | Intermittent lag | `projectOnboardingState.ts:20` |

**Existing Mitigations**: React ConcurrentRoot batching, 16ms framerate limits, virtual scroll overscan (80 rows), slide step (25 rows), `useDeferredValue`, Markdown `tokenCache` (LRU-500), `hasMarkdownSyntax` fast path, and Yoga incremental caching.

## Dismissed Hypotheses

VSZ 516 GB is virtual mapping | Zod ~650KB | Markdown LRU-500 optimized | `useSkillsChange`/`useSettingsChange` correct cleanup | `useInboxPoller` convergent design (non-cyclic) | React Compiler `_c(N)` unused | File watchers ~5KB | React reconciler `WeakMap` + `freeRecursive` | Ink screen buffer ~86KB | `CharPool`/`HyperlinkPool` ~1-5MB with 5min reset | AWS/Google/Azure SDKs are lazy-loaded | Sentry empty implementation | `useCallback` closures via `messagesRef` (no leak) | `MCP stderrHandler` 64MB cap + cleanup | `useRef` cleaned by `clearConversation`/`compact` | `apiMetricsRef` reset at turn end | `useEffect` has cleanup functions | `lodash-es` is tree-shakable | `AppState useSyncExternalStore` updates only on relevant slices | SDK has no global retry queue | Ink unmount handles cleanup.

## Conclusion

**Memory Root Cause Ranking**:
1.  **7-8x spread copies of message arrays** (120-320 MB) — Primary bottleneck.
2.  **useDeferredValue buffering + useMemo chain recomputation** (100-200 MB + GC STW).
3.  **Session Recovery/Write peaks** (200-300 MB).
4.  **AutoCompact timing + reactiveCompact stubs** (API overflow risk).
5.  **Forked Agent Cache cloning** (50N MB).
6.  **Virtual Scroll permanence** (~50MB).
7.  **Bun/JSC page retention** (Architectural).

**CPU Root Causes**: `useInboxPoller` per-second polling → React commit → Yoga layout → Full screen Ink diff pipeline. Markdown rendering batch mounts cause ~290ms lag.

**Estimated Optimization Potential**:

| Priority | Measures | Estimated Reduction |
| :--- | :--- | :--- |
| **P0** | 6 | 240-600 MB |
| **P1** | 14 | 300-600 MB |
| **P2** | 10 | 80-200 MB |
| **Total** | **30 Items** | **620-1400 MB** |

Theoretically, RSS could be reduced from 400-700 MB to **200-350 MB**, constrained by mimalloc/JSC architectural limits.
