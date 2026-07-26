# WebSearchTool — Web Search Tool

> Implementation Status: Adapter-based architecture complete; supports API, Bing, and Brave backends.
> Reference Count: Core tool; always enabled (no feature flag).

## I. Feature Overview

`WebSearchTool` enables the model to search the internet for the latest information. The original implementation only supported server-side searches via the Anthropic API (`web_search_20250305`), which is unavailable when using third-party proxy endpoints. This tool has been refactored using an **adapter-based architecture**, supporting official API searches as well as Bing (HTML scraping) and Brave (LLM Context API) backends, ensuring search functionality across all API endpoints.

## II. Implementation Architecture

### 2.1 Adapter Pattern

```
WebSearchTool.call()
       │
       ▼
  createAdapter()  ← Adapter Factory
       │
       ├── ApiSearchAdapter  — Official Anthropic API search
       │     └── Uses web_search_20250305 server tool
       │         via queryModelWithStreaming
       │
       ├── BingSearchAdapter — Bing HTML scraping + Regex extraction
       │     └── Directly scrapes Bing search results
       │         Extracts titles/URLs/snippets from b_algo blocks
       │
       └── BraveSearchAdapter — Brave LLM Context API
             └── Calls the Brave HTTPS GET interface
                 Maps grounding payloads to titles/URLs/snippets
```

### 2.2 Module Structure

| Module | File | Description |
| :--- | :--- | :--- |
| **Tool Entry** | `packages/builtin-tools/src/tools/WebSearchTool/WebSearchTool.ts` | `buildTool()` definition: schema, permissions, execution, and output formatting. |
| **Tool Prompt** | `packages/builtin-tools/src/tools/WebSearchTool/prompt.ts` | System prompts for the search tool. |
| **UI Rendering** | `packages/builtin-tools/src/tools/WebSearchTool/UI.tsx` | Terminal UI component for rendering search results. |
| **Adapter Interface**| `packages/builtin-tools/src/tools/WebSearchTool/adapters/types.ts` | `WebSearchAdapter` interface and associated types (`SearchResult`, `SearchOptions`, etc.). |
| **Adapter Factory** | `packages/builtin-tools/src/tools/WebSearchTool/adapters/index.ts` | `createAdapter()` factory function for selecting backends. |
| **API Adapter** | `packages/builtin-tools/src/tools/WebSearchTool/adapters/apiAdapter.ts` | Wraps the original `queryModelWithStreaming` logic for server tools. |
| **Bing Adapter** | `packages/builtin-tools/src/tools/WebSearchTool/adapters/bingAdapter.ts` | Bing HTML scraping and regex parsing logic. |
| **Brave Adapter** | `packages/builtin-tools/src/tools/WebSearchTool/adapters/braveAdapter.ts` | Brave LLM Context API adapter and result mapping. |

### 2.3 Data Flow

```
Model calls WebSearchTool(query, allowed_domains, blocked_domains)
       │
       ▼
  validateInput() — Validates non-empty query; ensures allowed/blocked lists don't coexist
       │
       ▼
  createAdapter() → ApiSearchAdapter | BingSearchAdapter | BraveSearchAdapter
       │
       ▼
  adapter.search(query, { allowedDomains, blockedDomains, signal, onProgress })
       │
       ├── onProgress({ type: 'query_update', query })
       │
       ├── axios.get(search-engine-url)
       │     └── API Auth Headers
       │
       ├── extractResults(payload) — Backend-specific extraction
       │
       ├── Client-side domain filtering (allowedDomains / blockedDomains)
       │
       ├── onProgress({ type: 'search_results_received', resultCount })
       │
       ▼
  Formatted as a list of Markdown links for the model
```

## III. Bing Adapter Technical Details

### 3.1 Anti-Bot Bypass

Uses a set of 13 Edge browser request headers (including `Sec-Ch-Ua` and `Sec-Fetch-*`) to prevent Bing from returning empty JS-rendered pages:
- `User-Agent`: Mimics a recent Edge browser.
- `setmkt=en-US`: Forces the US English market to avoid region-locked results based on IP geolocation.

### 3.2 URL Decoding (`resolveBingUrl()`)

Bing redirect URLs are formatted as: `bing.com/ck/a?...&u=a1aHR0cHM6Ly9...`
- The first two characters of the `u` parameter are protocol prefixes: `a1` = https, `a0` = http.
- The remaining string is base64url-encoded.
- Internal Bing links and relative paths are filtered out.

### 3.3 Snippet Extraction (`extractSnippet()`)

Uses a three-level fallback strategy:
1. `<p class="b_lineclamp...">`: The primary Bing search snippet segment.
2. `<p>` tags within `<div class="b_caption">`: Alternative snippet location.
3. Direct text within `<div class="b_caption">`: Final fallback.

### 3.4 Domain Filtering

Implemented on the client side with subdomain support:
- `allowedDomains`: A whitelist; results must match an entry in the list (including subdomains).
- `blockedDomains`: A blacklist; matching results are discarded.
- `validateInput` ensures both lists are not used simultaneously.

## IV. Adapter Selection Logic

`createAdapter()` selects a backend based on the following priorities and caches the instance:
1.  **Explicit Environment Variable**: `WEB_SEARCH_ADAPTER=api|bing|brave`.
2.  **Anthropic Official API Base URL**: Defaults to `ApiSearchAdapter`.
3.  **Third-party Proxy / Non-official Endpoints**: Defaults to `BingSearchAdapter`.

When `WEB_SEARCH_ADAPTER=brave` is specified, the system requires `BRAVE_SEARCH_API_KEY` or `BRAVE_API_KEY`.

## V. Interface Definitions

### WebSearchAdapter
```typescript
interface WebSearchAdapter {
  search(query: string, options: SearchOptions): Promise<SearchResult[]>
}

interface SearchResult {
  title: string
  url: string
  snippet?: string
}

interface SearchOptions {
  allowedDomains?: string[]
  blockedDomains?: string[]
  signal?: AbortSignal
  onProgress?: (progress: SearchProgress) => void
}

interface SearchProgress {
  type: 'query_update' | 'search_results_received'
  query?: string
  resultCount?: number
}
```

### Tool Input Schema
```typescript
{
  query: string              // Search keywords (min 2 characters)
  allowed_domains?: string[] // Domain whitelist
  blocked_domains?: string[] // Domain blacklist
}
```

## VI. File Index

| File | Responsibility |
| :--- | :--- |
| `packages/builtin-tools/src/tools/WebSearchTool/WebSearchTool.ts` | Tool entry point. |
| `packages/builtin-tools/src/tools/WebSearchTool/prompt.ts` | Search tool prompt. |
| `packages/builtin-tools/src/tools/WebSearchTool/UI.tsx` | Terminal UI rendering. |
| `packages/builtin-tools/src/tools/WebSearchTool/adapters/types.ts` | Adapter interfaces. |
| `packages/builtin-tools/src/tools/WebSearchTool/adapters/index.ts` | Adapter factory. |
| `packages/builtin-tools/src/tools/WebSearchTool/adapters/apiAdapter.ts` | API server-side search adapter. |
| `packages/builtin-tools/src/tools/WebSearchTool/adapters/bingAdapter.ts` | Bing HTML parsing adapter. |
| `packages/builtin-tools/src/tools/WebSearchTool/__tests__/bingAdapter.test.ts` | Unit tests (32 cases). |
| `packages/builtin-tools/src/tools/WebSearchTool/__tests__/bingAdapter.integration.ts` | Integration tests. |
| `src/tools.ts` | Tool registration. |
