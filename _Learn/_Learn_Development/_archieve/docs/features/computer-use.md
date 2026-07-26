# Computer Use — macOS / Windows / Linux Cross-Platform Implementation Plan

**Updated**: 2026-04-03
**Reference Project**: `E:\Source\claude-code-source-main\claude-code-source-main`

## 1. Current Status

The reference project's Computer Use **only supports macOS**, with hardcoded `darwin` checks from entry point to backend. Our project has completed the following in Phases 1-3:

- ✅ `@ant/computer-use-mcp` stub replaced with full implementation (12 files).
- ✅ `@ant/computer-use-input` refactored into dispatcher + backends (darwin + win32).
- ✅ `@ant/computer-use-swift` refactored into dispatcher + backends (darwin + win32).
- ✅ `CHICAGO_MCP` compilation flag enabled.
- ✅ macOS hardcoding in the `src/` layer removed (Phase 2 completed).

## 2. Panorama of Blockers

### 2.1 Entry Layer

| # | File:Line | Blocking Code | Impact |
| :--- | :--- | :--- | :--- |
| 1 | `src/main.tsx:2366` | `feature("CHICAGO_MCP")` gating | CU initialization entry point. |

### 2.2 Loading Layer

| # | File:Line | Blocking Code | Impact |
| :--- | :--- | :--- | :--- |
| 2 | `src/utils/computerUse/swiftLoader.ts` | macOS-only loader (now modified for darwin-only load). | Non-darwin platforms use a `platforms/` alternative. |
| 3 | `src/utils/computerUse/executor.ts:302` | `process.platform !== 'darwin'` → cross-platform executor. | Non-darwin platforms follow the cross-platform path. |

### 2.3 macOS-Specific Dependencies

| # | File:Line | Dependency | macOS Implementation | Needed Alternative |
| :--- | :--- | :--- | :--- | :--- |
| 4 | `executor.ts:72-96` | Clipboard | `pbcopy`/`pbpaste` / PowerShell / xclip | Win: PowerShell `Get/Set-Clipboard`; Linux: `xclip`/`wl-copy`. |
| 5 | `drainRunLoop.ts` | CFRunLoop pump | `cu._drainMainRunLoop()` | Non-darwin: Execute `fn()` directly; no pump required. |
| 6 | `escHotkey.ts` | ESC Hotkey | `CGEventTap` | Non-darwin: Return `false` (Ctrl+C fallback exists). |
| 7 | `hostAdapter.ts` | System Permissions | TCC accessibility + screenRecording | Win: Granted directly; Linux: Check `xdotool`. |
| 8 | `common.ts:55-58` | Platform ID | Dynamic retrieval | Replaced with `process.platform` dispatch. |
| 9 | `executor.ts:232` | Paste Shortcut | `command`/`ctrl` dispatch | Paste shortcut dispatched by platform. |

### 2.4 Missing Linux Backend

| Package | macOS | Windows | Linux |
| :--- | :--- | :--- | :--- |
| `computer-use-input/backends/` | ✅ darwin.ts | ✅ win32.ts | ❌ Needs `linux.ts`. |
| `computer-use-swift/backends/` | ✅ darwin.ts | ✅ win32.ts | ❌ Needs `linux.ts`. |

## 3. Capability Dependencies by Platform

### 3.1 computer-use-input (Keyboard/Mouse)

| Feature | macOS | Windows | Linux |
| :--- | :--- | :--- | :--- |
| **Mouse Movement** | CGEvent JXA | SetCursorPos P/Invoke | `xdotool mousemove` |
| **Mouse Click** | CGEvent JXA | SendInput P/Invoke | `xdotool click` |
| **Mouse Wheel** | CGEvent JXA | SendInput MOUSEEVENTF_WHEEL | `xdotool scroll` |
| **Keyboard Key** | System Events osascript | keybd_event P/Invoke | `xdotool key` |
| **Key Combination** | System Events osascript | keybd_event combo | `xdotool key combo` |
| **Text Input** | System Events keystroke | SendKeys.SendWait | `xdotool type` |
| **Foreground App** | System Events osascript | GetForegroundWindow P/Invoke | `xdotool getactivewindow` + `/proc` |
| **Tool Dependency** | osascript (built-in) | powershell (built-in) | `xdotool` (requires installation) |

### 3.2 computer-use-swift (Screenshot + App Management)

| Feature | macOS | Windows | Linux |
| :--- | :--- | :--- | :--- |
| **Full Screenshot** | screencapture | CopyFromScreen | gnome-screenshot / scrot / grim |
| **Region Screenshot** | screencapture -R | CopyFromScreen(rect) | gnome-screenshot -a / scrot -a / grim -g |
| **Display List** | CGGetActiveDisplayList JXA | Screen.AllScreens | `xrandr --query` |
| **Running Apps** | System Events JXA | Get-Process | `wmctrl -l` / `ps` |
| **Open App** | osascript activate | Start-Process | `xdg-open` / `gtk-launch` |
| **Hide/Show** | System Events visibility | ShowWindow/SetForegroundWindow | `wmctrl -c` / `xdotool` |
| **Tool Dependency** | screencapture + osascript | powershell | `xdotool` + `scrot`/`grim` + `wmctrl` |

### 3.3 Executor Layer

| Feature | macOS | Windows | Linux |
| :--- | :--- | :--- | :--- |
| **drainRunLoop** | CFRunLoop pump | Not needed | Not needed |
| **ESC Hotkey** | CGEventTap | Skip (Ctrl+C fallback) | Skip (Ctrl+C fallback) |
| **Clipboard Read** | pbpaste | `powershell Get-Clipboard` | `xclip -o` / `wl-paste` |
| **Clipboard Write** | pbcopy | `powershell Set-Clipboard` | `xclip` / `wl-copy` |
| **Paste Shortcut** | command+v | ctrl+v | ctrl+v |
| **Terminal Detection**| __CFBundleIdentifier | WT_SESSION / TERM_PROGRAM | TERM_PROGRAM |
| **System Permissions**| TCC check | Granted directly | Check `xdotool` installation |

## 4. Execution Steps

### Phase 1: Completed ✅

- [x] `@ant/computer-use-mcp` stub → Full implementation.
- [x] `@ant/computer-use-input` dispatcher + darwin/win32 backends.
- [x] `@ant/computer-use-swift` dispatcher + darwin/win32 backends.
- [x] `CHICAGO_MCP` compilation flag.

### Phase 2: Removing 6 macOS Hardcodings (Unlocking macOS + Windows)

**Principle: Keep macOS code paths unchanged; add win32/linux branches after each darwin guard.**

| Step | File | Change |
| :--- | :--- | :--- |
| **2.1** | `src/main.tsx:2366` | `feature("CHICAGO_MCP")` → Updated to cross-platform entry point. |
| **2.2** | `src/utils/computerUse/swiftLoader.ts` | Modified to load only on darwin; non-darwin uses `platforms/`. |
| **2.3** | `src/utils/computerUse/executor.ts:302-309` | Updated for cross-platform dispatch (non-darwin → `createCrossPlatformExecutor`). |
| **2.4** | `src/utils/computerUse/executor.ts:72-96` | Clipboard dispatched by platform: darwin→pbcopy/pbpaste, win32→PowerShell, linux→xclip. |
| **2.5** | `src/utils/computerUse/executor.ts:232` | Paste shortcut dispatched by platform: darwin→command, others→ctrl. |
| **2.6** | `src/utils/computerUse/executor.ts:302-309` | Non-darwin platforms now use `createCrossPlatformExecutor()`. |
| **2.7** | `src/utils/computerUse/drainRunLoop.ts` | Non-darwin does not require a pump (executes `fn` directly). |
| **2.8** | `src/utils/computerUse/escHotkey.ts` | Non-darwin returns `false` (Ctrl+C fallback exists). |
| **2.9** | `src/utils/computerUse/hostAdapter.ts` | Permission check logic implemented for non-darwin. |
| **2.10** | `src/utils/computerUse/common.ts:58` | Updated for dynamic `process.platform` dispatch. |
| **2.11** | `src/utils/computerUse/common.ts:55` | Updated: darwin→'native', others→'none'. |
| **2.12** | `src/utils/computerUse/gates.ts:55` | Updated (requires verification of default enabled values). |
| **2.13** | `src/utils/computerUse/gates.ts:39` | `hasRequiredSubscription()` updated. |

### Phase 3: Adding Linux Backend

| Step | File | Content |
| :--- | :--- | :--- |
| **3.1** | `packages/@ant/computer-use-input/src/backends/linux.ts` | `xdotool` for keyboard/mouse (mousemove/click/key/type/getactivewindow). |
| **3.2** | `packages/@ant/computer-use-swift/src/backends/linux.ts` | `scrot`/`grim` for screenshots, `xrandr` for displays, `wmctrl` for window management. |
| **3.3** | `packages/@ant/computer-use-input/src/index.ts` | Added `case 'linux'` to dispatcher. |
| **3.4** | `packages/@ant/computer-use-swift/src/index.ts` | Added `case 'linux'` to dispatcher. |

### Phase 4: Verification

| Test Item | macOS | Windows | Linux |
| :--- | :--- | :--- | :--- |
| **Build Succeeded** | ✅ | Verify | Verify |
| **MCP Tool List Not Empty** | Verify | Verify | Verify |
| **Mouse Movement** | Verify | ✅ Passed | Verify |
| **Screenshot** | Verify | ✅ Passed | Verify |
| **Keyboard Input** | Verify | Verify | Verify |
| **Foreground Window** | Verify | ✅ Passed | Verify |
| **Clipboard** | Verify | Verify | Verify |

## 5. Overview of File Changes

### Unchanged Files (14 Files)

`cleanup.ts`, `computerUseLock.ts`, `wrapper.tsx`, `toolRendering.tsx`, `mcpServer.ts`, `setup.ts`, `appNames.ts`, `inputLoader.ts`, `src/services/mcp/client.ts`, `@ant/computer-use-mcp/src/*` (Phase 1 completed), `backends/darwin.ts` (both packages).

### Modified `src/` Files (8 Files)

| File | Change Volume | Risk |
| :--- | :--- | :--- |
| `main.tsx` | 1 line | Low |
| `swiftLoader.ts` | 2 lines | Low |
| `executor.ts` | ~40 lines (Clipboard dispatch, platform guards, paste shortcut) | **Medium** |
| `drainRunLoop.ts` | 1 line | Low |
| `escHotkey.ts` | 3 lines | Low |
| `hostAdapter.ts` | 5 lines | Low |
| `common.ts` | 3 lines | Low |
| `gates.ts` | 3 lines | Low |

### New Files (2 Files)

| File | Estimated LoC |
| :--- | :--- |
| `packages/@ant/computer-use-input/src/backends/linux.ts` | ~150 lines |
| `packages/@ant/computer-use-swift/src/backends/linux.ts` | ~200 lines |

## 6. Linux Tool Dependencies

| Tool | Purpose | Installation Command (Ubuntu) |
| :--- | :--- | :--- |
| `xdotool` | Keyboard/Mouse simulation + Window management. | `sudo apt install xdotool` |
| `scrot` or `gnome-screenshot` | Screenshots. | `sudo apt install scrot` |
| `xrandr` | Display information. | Usually pre-installed. |
| `xclip` | Clipboard. | `sudo apt install xclip` |
| `wmctrl` | Window listing/switching. | `sudo apt install wmctrl` |

For Wayland environments, alternative tools are required: `ydotool` (replaces `xdotool`), `grim` (replaces `scrot`), and `wl-clipboard` (replaces `xclip`). Initial support will prioritize X11, with Wayland marked as a to-do.

## 7. Recommended Execution Order

```
Phase 2 (Unlocking macOS + Windows)
  ├── 2.1-2.3  Remove 3 hardcoded throw/skip instances.
  ├── 2.4-2.5  Platform dispatch for clipboard + paste shortcuts.
  ├── 2.6      swiftLoader → direct instantiation.
  ├── 2.7-2.9  Platform branches for drainRunLoop / escHotkey / permissions.
  ├── 2.10-2.11 Dynamic platform ID in common.ts.
  ├── 2.12-2.13 Default values in gates.ts.
  └── Verify Windows.

Phase 3 (Linux Backend)
  ├── 3.1  input/backends/linux.ts.
  ├── 3.2  swift/backends/linux.ts.
  ├── 3.3-3.4  Add linux case to dispatchers.
  └── Verify Linux.

Phase 4 (Integrated Verification + PR)
```

Each phase can be verified and committed independently. After Phase 2, macOS and Windows will be functional; after Phase 3, all three platforms will be supported.
