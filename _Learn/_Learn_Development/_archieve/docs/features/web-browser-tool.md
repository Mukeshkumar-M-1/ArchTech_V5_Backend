# WEB_BROWSER_TOOL — Browser Tool

> Feature Flag: `FEATURE_WEB_BROWSER_TOOL=1`
> Implementation Status: Core tools implemented; panel is a stub; wiring is complete.
> Reference Count: 4

## I. Feature Overview

`WEB_BROWSER_TOOL` allows the model to launch browser instances, navigate the web, and interact with page elements. It leverages Bun's built-in WebView API to provide headless or headed browser capabilities.

## II. Implementation Architecture

### 2.1 Module Status

| Module | File | Status |
| :--- | :--- | :--- |
| **Browser Panel** | `packages/builtin-tools/src/tools/WebBrowserTool/WebBrowserPanel.ts` | **Stub** — Returns null. |
| **Browser Tool** | `packages/builtin-tools/src/tools/WebBrowserTool/WebBrowserTool.ts` | **Implemented**. |
| **REPL Integration** | `src/screens/REPL.tsx` | **Wired** — Renders `WebBrowserPanel`. |
| **Tool Registration**| `src/tools.ts` | **Wired** — Dynamically loaded. |
| **WebView Detection**| `src/main.tsx` | **Wired** — Checks for `'WebView' in Bun`. |

### 2.2 Expected Data Flow

```
Model calls WebBrowserTool
         │
         ▼
Bun WebView creates browser instance
         │
         ├── navigate(url) — Navigates to URL
         ├── click(selector) — Clicks an element
         ├── screenshot() — Captures a page screenshot
         └── extract(selector) — Extracts page content
         │
         ▼
Results returned to the model
         │
         ▼
WebBrowserPanel displays browser status in the REPL sidebar
```

## III. Missing Implementations

| Module | Effort | Description |
| :--- | :--- | :--- |
| `WebBrowserTool.ts` | ✅ Done | Tool schema and Bun WebView API execution. |
| `WebBrowserPanel.tsx`| Medium | Status panel for the browser in the REPL sidebar (currently a stub). |

## IV. Key Design Decisions

1.  **Bun WebView API**: Utilizes Bun's built-in WebView rather than external drivers like Puppeteer or Playwright.
2.  **REPL Side Panel**: Browser status is rendered independently within the REPL layout.
3.  **Bun Feature Detection**: Uses `'WebView' in Bun` to check for runtime support.

## V. Usage

```bash
FEATURE_WEB_BROWSER_TOOL=1 bun run dev
```

## VI. File Index

| File | Responsibility |
| :--- | :--- |
| `packages/builtin-tools/src/tools/WebBrowserTool/WebBrowserPanel.ts` | Panel component (stub). |
| `packages/builtin-tools/src/tools/WebBrowserTool/WebBrowserTool.ts` | Tool implementation. |
| `src/screens/REPL.tsx:471,5676` | Panel rendering. |
| `src/tools.ts:115-116` | Tool registration. |
