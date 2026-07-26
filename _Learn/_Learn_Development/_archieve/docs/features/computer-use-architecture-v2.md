# Computer Use Architecture Rectification Plan v2

**Updated**: 2026-04-04

## 1. Current Architectural Issues

### Issue A: Platform Code Leakage

`@ant/computer-use-swift` is a wrapper for macOS Swift native modules. However, we have placed Windows (`backends/win32.ts`) and Linux (`backends/linux.ts`) code for screenshots and application management within this package. The name "swift" implies macOS exclusivity, which confuses future maintainers.

The same applies to `@ant/computer-use-input`—originally intended for the macOS `enigo` Rust module, it now contains win32 and linux backends as well.

### Issue B: Incorrect Input Method

The current Windows backend (`packages/@ant/computer-use-input/src/backends/win32.ts`) uses `SetCursorPos` + `SendInput` + `keybd_event`. This is **global input**:

- The mouse physically moves across the screen.
- Keyboard input goes to the current foreground window.
- **This interferes with the user's current operations.**

After binding to a window handle, we should use `SendMessage`/`PostMessage` to send messages to the target `HWND`:

- `WM_CHAR` — Sends characters without moving the cursor.
- `WM_KEYDOWN`/`WM_KEYUP` — Sends key presses.
- `WM_LBUTTONDOWN`/`WM_LBUTTONUP` — Sends mouse clicks (coordinates relative to the window's client area).
- `PrintWindow` — Captures window content without requiring the window to be in the foreground.
- **Does not grab focus or interfere with the user's current operations.**

**Verified**: Successfully wrote text to Notepad via `SendMessage(WM_CHAR)` while Notepad was in the background and the terminal remained in the foreground.

### Issue C: Screenshots are a Common Capability

Screenshotting (`screenshot`), display enumeration (`display`), and application management (`apps`) are common capabilities required by all platforms. They should not reside in `@ant/computer-use-swift` (a macOS-specific package name).

## 2. Revised Architecture

### 2.1 Layering Principles

```
packages/@ant/                     ← macOS native module wrappers (no other platform code)
├── computer-use-input/             ← macOS: enigo .node keyboard/mouse (darwin only)
├── computer-use-swift/             ← macOS: Swift .node screenshot/apps (darwin only)
└── computer-use-mcp/               ← Cross-platform: MCP server + tool definitions (unchanged)

src/utils/computerUse/
├── platforms/                     ← NEW: Cross-platform abstraction layer
│   ├── types.ts                    ← Common interfaces: InputPlatform, ScreenshotPlatform, AppsPlatform, DisplayPlatform
│   ├── index.ts                    ← Platform dispatcher: Loads backend based on process.platform
│   ├── darwin.ts                   ← macOS: Delegates to @ant/computer-use-{input,swift}
│   ├── win32.ts                    ← Windows: SendMessage input + PrintWindow screenshot + EnumWindows + UIA + OCR
│   └── linux.ts                    ← Linux: xdotool + scrot + xrandr + wmctrl
│
├── win32/                         ← Windows-specific enhanced capabilities (not in common interfaces)
│   ├── windowCapture.ts            ← PrintWindow bound window capture
│   ├── windowEnum.ts               ← EnumWindows window enumeration
│   ├── windowMessage.ts            ← SendMessage/PostMessage focus-less input (NEW)
│   ├── uiAutomation.ts             ← IUIAutomation UI element operations
│   └── ocr.ts                      ← Windows.Media.Ocr character recognition
│
├── executor.ts                    ← REFACTORED: Gets implementation via platforms/, no direct calls to @ant packages
├── swiftLoader.ts                 ← REFACTORED: darwin only
├── inputLoader.ts                 ← REFACTORED: darwin only
└── ... (Other files remain unchanged)
```

### 2.2 Public Interfaces (`platforms/types.ts`)

```typescript
/** Window Handle — Cross-platform */
export interface WindowHandle {
  id: string           // macOS: bundleId, Windows: HWND string, Linux: window ID
  pid: number
  title: string
  exePath?: string     // Windows/Linux: process path
}

/** Input Platform Interface — Two Modes */
export interface InputPlatform {
  // Mode A: Global Input (Default for macOS/Linux, sent to foreground window)
  moveMouse(x: number, y: number): Promise<void>
  click(x: number, y: number, button: 'left' | 'right' | 'middle'): Promise<void>
  typeText(text: string): Promise<void>
  key(name: string, action: 'press' | 'release'): Promise<void>
  keys(combo: string[]): Promise<void>
  scroll(amount: number, direction: 'vertical' | 'horizontal'): Promise<void>
  mouseLocation(): Promise<{ x: number; y: number }>
  
  // Mode B: Bound Window Input (Windows SendMessage, focus-less)
  sendChar?(hwnd: string, char: string): Promise<void>
  sendKey?(hwnd: string, vk: number, action: 'down' | 'up'): Promise<void>
  sendClick?(hwnd: string, x: number, y: number, button: 'left' | 'right'): Promise<void>
  sendText?(hwnd: string, text: string): Promise<void>
}

/** Screenshot Platform Interface */
export interface ScreenshotPlatform {
  // Full-screen capture
  captureScreen(displayId?: number): Promise<ScreenshotResult>
  // Region capture
  captureRegion(x: number, y: number, w: number, h: number): Promise<ScreenshotResult>
  // Window capture (Windows: PrintWindow, macOS: SCContentFilter, Linux: xdotool+import)
  captureWindow?(hwnd: string): Promise<ScreenshotResult | null>
}

/** Display Platform Interface */
export interface DisplayPlatform {
  listAll(): DisplayInfo[]
  getSize(displayId?: number): DisplayInfo
}

/** App Management Platform Interface */
export interface AppsPlatform {
  listRunning(): WindowHandle[]
  listInstalled(): Promise<InstalledApp[]>
  open(name: string): Promise<void>
  getFrontmostApp(): FrontmostAppInfo | null
  findWindowByTitle(title: string): WindowHandle | null
}

export interface ScreenshotResult {
  base64: string
  width: number
  height: number
}

export interface DisplayInfo {
  width: number
  height: number
  scaleFactor: number
  displayId: number
}

export interface InstalledApp {
  id: string       // macOS: bundleId, Windows: exe path, Linux: .desktop name
  displayName: string
  path: string
}

export interface FrontmostAppInfo {
  id: string
  appName: string
}
```

### 2.3 Platform Dispatcher (`platforms/index.ts`)

```typescript
import type { InputPlatform, ScreenshotPlatform, DisplayPlatform, AppsPlatform } from './types.js'

export interface Platform {
  input: InputPlatform
  screenshot: ScreenshotPlatform
  display: DisplayPlatform
  apps: AppsPlatform
}

export function loadPlatform(): Platform {
  switch (process.platform) {
    case 'darwin':
      return require('./darwin.js').platform
    case 'win32':
      return require('./win32.js').platform
    case 'linux':
      return require('./linux.js').platform
    default:
      throw new Error(`Computer Use not supported on ${process.platform}`)
  }
}
```

### 2.4 Platform Implementations

**`platforms/darwin.ts`** — Delegates to `@ant` packages (maintains compatibility):
```typescript
// macOS: Via @ant/computer-use-input and @ant/computer-use-swift
// The darwin backends for these two packages remain unchanged
import { requireComputerUseInput } from '../inputLoader.js'
import { requireComputerUseSwift } from '../swiftLoader.js'

export const platform = {
  input: { /* Delegates to requireComputerUseInput() */ },
  screenshot: { /* Delegates to requireComputerUseSwift().screenshot */ },
  display: { /* Delegates to requireComputerUseSwift().display */ },
  apps: { /* Delegates to requireComputerUseSwift().apps */ },
}
```

**`platforms/win32.ts`** — Uses `src/utils/computerUse/win32/` modules:
```typescript
// Windows: SendMessage input + PrintWindow screenshot + EnumWindows apps
import { sendChar, sendKey, sendClick, sendText } from '../win32/windowMessage.js'
import { captureWindow } from '../win32/windowCapture.js'
import { listWindows } from '../win32/windowEnum.js'
// ... PowerShell P/Invoke global input as fallback

export const platform = {
  input: {
    // Global Mode: PowerShell SetCursorPos/SendInput (fallback)
    // Window Mode: SendMessage (preferred)
    sendChar, sendKey, sendClick, sendText,  // Window bound
    moveMouse, click, typeText, ...           // Global fallback
  },
  screenshot: {
    captureScreen,     // CopyFromScreen
    captureRegion,     // CopyFromScreen(rect)
    captureWindow,     // PrintWindow (focus-less)
  },
  display: { /* Screen.AllScreens */ },
  apps: { /* EnumWindows */ },
}
```

**`platforms/linux.ts`** — Uses `xdotool`/`scrot`:
```typescript
// Linux: xdotool + scrot + xrandr + wmctrl
export const platform = {
  input: { /* xdotool mousemove/click/key/type */ },
  screenshot: { /* scrot */ },
  display: { /* xrandr */ },
  apps: { /* wmctrl + ps */ },
}
```

### 2.5 executor.ts Refactoring

```typescript
// Previously: Direct calls to requireComputerUseSwift() and requireComputerUseInput()
// Now: Unified access via platforms/

import { loadPlatform } from './platforms/index.js'

const platform = loadPlatform()

// Screenshot
platform.screenshot.captureScreen()
platform.screenshot.captureWindow(hwnd)  // Window bound

// Input (Window bound mode, focus-less)
platform.input.sendText?.(hwnd, 'Hello')
platform.input.sendClick?.(hwnd, 100, 200, 'left')

// Input (Global mode, fallback)
platform.input.moveMouse(500, 500)
platform.input.click(500, 500, 'left')
```

## 3. Windows Input Mode Comparison

| Method | API | Focus Grabbing | Mouse Movement | Minimizable Window | Use Case |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Global Input** | `SetCursorPos` + `SendInput` | ✅ Grabs | ✅ Moves | ❌ No | Coordinate-based clicks (fallback) |
| **Window Message** | `SendMessage(WM_CHAR/WM_KEYDOWN)` | ❌ None | ❌ None | ✅ Yes | Typing, key presses (preferred) |
| **Window Message** | `SendMessage(WM_LBUTTONDOWN)` | ❌ None | ❌ None | ⚠️ Partial | Clicks within window |
| **Window Capture** | `PrintWindow(hwnd, PW_RENDERFULLCONTENT)` | ❌ None | ❌ None | ✅ Yes | Window screenshot |
| **UI Operations** | `UIAutomation InvokePattern` | ❌ None | ❌ None | ✅ Yes | Button clicks, text entry |

**Strategy**: Prioritize Window Messages + UIAutomation (to avoid user interference), with Global Input as a fallback.

## 4. Files to be Added

| File | Description |
| :--- | :--- |
| `src/utils/computerUse/platforms/types.ts` | Common interface definitions. |
| `src/utils/computerUse/platforms/index.ts` | Platform dispatcher. |
| `src/utils/computerUse/platforms/darwin.ts` | macOS: Delegates to `@ant` packages. |
| `src/utils/computerUse/platforms/win32.ts` | Windows: Composes modules from `win32/`. |
| `src/utils/computerUse/platforms/linux.ts` | Linux: `xdotool`/`scrot`. |
| `src/utils/computerUse/win32/windowMessage.ts` | **NEW**: `SendMessage` focus-less input. |

## 5. Files to be Removed/Cleaned

| File | Action | Reason |
| :--- | :--- | :--- |
| `packages/@ant/computer-use-input/src/backends/win32.ts` | Delete | Windows code should not be in a macOS package. |
| `packages/@ant/computer-use-input/src/backends/linux.ts` | Delete | Linux code should not be in a macOS package. |
| `packages/@ant/computer-use-swift/src/backends/win32.ts` | Delete | Same as above. |
| `packages/@ant/computer-use-swift/src/backends/linux.ts` | Delete | Same as above. |
| `packages/@ant/computer-use-input/src/types.ts` | Delete | Moved to `platforms/types.ts`. |
| `packages/@ant/computer-use-swift/src/types.ts` | Delete | Moved to `platforms/types.ts`. |

## 6. Files to be Modified

| File | Changes |
| :--- | :--- |
| `packages/@ant/computer-use-input/src/index.ts` | Restore to darwin-only dispatcher (remove win32/linux cases). |
| `packages/@ant/computer-use-swift/src/index.ts` | Restore to darwin-only dispatcher (remove win32/linux cases). |
| `src/utils/computerUse/executor.ts` | Get implementation via `platforms/`, no direct calls to `@ant` packages. |
| `src/utils/computerUse/swiftLoader.ts` | Load only on darwin. |
| `src/utils/computerUse/inputLoader.ts` | Load only on darwin. |

## 7. Role of @ant Packages (Revised)

| Package | Responsibility | Platform |
| :--- | :--- | :--- |
| `@ant/computer-use-input` | Wrapper for macOS `enigo` native module. | **darwin only** |
| `@ant/computer-use-swift` | Wrapper for macOS Swift native modules. | **darwin only** |
| `@ant/computer-use-mcp` | MCP Server + tool definitions + call routing. | **Cross-platform** (No platform code) |

Windows/Linux platform implementations reside entirely within `src/utils/computerUse/platforms/` and `src/utils/computerUse/win32/`.

## 8. Execution Order

```
Phase 1: Create platforms/ abstraction layer
  ├── platforms/types.ts (Common interfaces)
  ├── platforms/index.ts (Dispatcher)
  └── platforms/darwin.ts (Delegate to @ant packages)

Phase 2: Create Windows platform implementation
  ├── win32/windowMessage.ts (SendMessage focus-less input)
  └── platforms/win32.ts (Compose win32/ modules)

Phase 3: Create Linux platform implementation
  └── platforms/linux.ts (xdotool/scrot)

Phase 4: Refactor executor.ts
  └── Use platforms/ for implementation; no direct @ant calls

Phase 5: Clean up @ant packages
  ├── Remove win32/linux backends from @ant/computer-use-input
  ├── Remove win32/linux backends from @ant/computer-use-swift
  └── Restore index.ts to darwin-only

Phase 6: Verification + PR
```
