# Computer Use Windows Enhancement Implementation Plan

**Updated**: 2026-04-03
**Dependency Documents**: `docs/features/windows-ai-desktop-control.md`, `docs/features/computer-use.md`

## 1. Objectives

Building upon the existing PowerShell subprocess solution, this plan leverages native Windows APIs to enhance the Windows implementation of Computer Use, addressing three core issues:

1.  **Window-Bound Screenshots**: Current `CopyFromScreen` is limited to full-screen captures; it cannot capture specific windows (especially those obscured or minimized).
2.  **UI Structural Awareness**: Currently limited to coordinate-based clicking; lacks the ability to understand the UI element tree like macOS Accessibility.
3.  **Performance**: Each PowerShell startup takes approximately 273ms; high-frequency operations such as clipboard access and window enumeration require faster methods.

## 2. Verified Windows API Capabilities

All the following APIs have been successfully verified through PowerShell P/Invoke:

| Capability | API | Verification Result |
| :--- | :--- | :--- |
| **Window-Bound Screenshot** | `PrintWindow(hwnd, hdc, PW_RENDERFULLCONTENT)` | ✅ VS Code 342KB, Chrome 273KB. |
| **Enumerate Windows + HWND** | `EnumWindows` + `GetWindowText` + `GetWindowThreadProcessId` | ✅ 38 windows, including HWND/PID/Title. |
| **UI Element Tree** | `System.Windows.Automation.AutomationElement` | ✅ 39 elements in Notepad. |
| **UI Value Setting** | `ValuePattern.SetValue()` | ✅ Successfully wrote text to Notepad. |
| **UI Clicking** | `InvokePattern.Invoke()` | ✅ Programmatic button clicking. |
| **Coordinate Element Identification** | `AutomationElement.FromPoint(x, y)` | ✅ Returns element type and name. |
| **OCR** | `Windows.Media.Ocr.OcrEngine` | ✅ English and Chinese engines available. |
| **Global Hotkeys** | `RegisterHotKey` | ✅ API callable. |
| **Direct Clipboard Operation**| `System.Windows.Forms.Clipboard` | ✅ Read/Write/Image detection. |
| **Shell Startup** | `ShellExecute` | ✅ Open files/URLs/Applications. |

## 3. Architectural Design

### 3.1 File Structure

New Windows-specific modules will be added to the existing `backends/win32.ts` foundation:

```
packages/@ant/computer-use-input/src/
├── backends/
│   ├── darwin.ts          ← Unchanged
│   ├── win32.ts           ← ENHANCED: Direct Win32 API replaces some PowerShell
│   └── linux.ts           ← Unchanged

packages/@ant/computer-use-swift/src/
├── backends/
│   ├── darwin.ts          ← Unchanged
│   ├── win32.ts           ← ENHANCED: PrintWindow screenshot + EnumWindows
│   └── linux.ts           ← Unchanged

packages/@ant/computer-use-mcp/src/
│   └── tools.ts           ← ADDED: Windows-specific tool definitions (UIA, OCR)

src/utils/computerUse/
│   └── win32/              ← NEW: Windows-specific capability modules
│       ├── uiAutomation.ts  ← UI element tree, clicks, value setting
│       ├── ocr.ts           ← Screenshot + OCR character recognition
│       ├── windowCapture.ts ← PrintWindow window-bound screenshots
│       └── windowEnum.ts    ← EnumWindows window enumeration
```

### 3.2 Layering

```
┌──────────────────────────────────────────────┐
│           Computer Use MCP Tools             │
│  screenshot / click / type / request_access  │
│  + Windows Exclusive: ui_tree / ocr / window_cap│
├──────────────────────────────────────────────┤
│           src/utils/computerUse/             │
│  executor.ts → Dispatch by platform          │
│  win32/ → Windows-specific capability modules │
├──────────────────────────────────────────────┤
│     packages/@ant/computer-use-{input,swift}  │
│  backends/win32.ts → PowerShell + Win32 API  │
├──────────────────────────────────────────────┤
│           Windows Native API                 │
│  PrintWindow / EnumWindows / UI Automation   │
│  SendInput / Clipboard / OCR / ShellExecute  │
└──────────────────────────────────────────────┘
```

## 4. Implementation Plan

### Phase A: Window-Bound Screenshots (Core Issue)

**Problem**: Current `CopyFromScreen` is limited to full-screen captures.
**Solution**: Implement window-level screenshots using `PrintWindow` + `FindWindow`.

| Step | File | Change |
| :--- | :--- | :--- |
| **A.1** | `src/utils/computerUse/win32/windowCapture.ts` | NEW: `captureWindow(title)` captures a specific window via `PrintWindow`. |
| **A.2** | `src/utils/computerUse/win32/windowEnum.ts` | NEW: `listWindows()` returns `{hwnd, pid, title}[]` using `EnumWindows`. |
| **A.3** | `packages/@ant/computer-use-swift/src/backends/win32.ts` | `screenshot.captureExcluding` adds window-based capture capability. |
| **A.4** | `packages/@ant/computer-use-swift/src/backends/win32.ts` | `apps.listRunning` uses `EnumWindows` instead of `Get-Process` (returns HWND). |

**PowerShell Script Core**:

```powershell
# PrintWindow for capturing a specific window
Add-Type -AssemblyName System.Drawing
Add-Type -ReferencedAssemblies System.Drawing @'
using System; using System.Runtime.InteropServices; using System.Drawing; using System.Drawing.Imaging;
public class WinCap {
    [DllImport("user32.dll", CharSet=CharSet.Unicode)]
    public static extern IntPtr FindWindow(string c, string t);
    [DllImport("user32.dll")]
    public static extern bool GetWindowRect(IntPtr h, out RECT r);
    [DllImport("user32.dll")]
    public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint f);
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT { public int L, T, R, B; }
    // ... CaptureByTitle(string title) → base64
}
'@
```

**Verification Criteria**:
- Successfully capture screenshots by window title.
- Obscured windows can still be captured.
- Returns base64, width, and height.

### Phase B: UI Automation (Windows Exclusive New Capability)

**Problem**: macOS has an Accessibility API for reading and interacting with UI elements; Windows is currently limited to coordinate clicking.
**Solution**: Use `System.Windows.Automation` for UI tree reading and element manipulation.

| Step | File | Change |
| :--- | :--- | :--- |
| **B.1** | `src/utils/computerUse/win32/uiAutomation.ts` | NEW: Core UIA operation encapsulation. |
| **B.2** | `packages/@ant/computer-use-mcp/src/tools.ts` | ADDED: Windows-specific tool definitions. |

**`uiAutomation.ts` Exported Functions**:

```typescript
// Obtain the UI element tree of a window
getUITree(windowTitle: string, depth: number): UIElement[]

// Find elements by name/type/AutomationId
findElement(windowTitle: string, query: {name?, controlType?, automationId?}): UIElement | null

// Click an element (InvokePattern)
clickElement(windowTitle: string, automationId: string): boolean

// Set element value (ValuePattern)
setValue(windowTitle: string, automationId: string, value: string): boolean

// Identify element at coordinates
elementAtPoint(x: number, y: number): UIElement | null
```

**`UIElement` Type**:
```typescript
interface UIElement {
  name: string
  controlType: string    // Button, Edit, Text, List, etc.
  automationId: string
  boundingRect: { x: number, y: number, w: number, h: number }
  isEnabled: boolean
  value?: string         // Available when ValuePattern is applicable
  children?: UIElement[]
}
```

**PowerShell Script Core**:
```powershell
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# Read UI Tree
$root = [AutomationElement]::RootElement
$window = $root.FindFirst([TreeScope]::Children, 
  [PropertyCondition]::new([AutomationElement]::NameProperty, $title))
$elements = $window.FindAll([TreeScope]::Descendants, [Condition]::TrueCondition)

# Write Text
$element.GetCurrentPattern([ValuePattern]::Pattern).SetValue($text)

# Click Button
$element.GetCurrentPattern([InvokePattern]::Pattern).Invoke()
```

**Verification Criteria**:
- Successfully read the UI tree of Notepad (buttons, textboxes, menus).
- Successfully write content to textboxes.
- Successfully click buttons.
- Successfully identify elements at specific coordinates.

### Phase C: OCR Screen Character Recognition

**Problem**: After taking a screenshot, the AI only sees an image and cannot read text directly.
**Solution**: Use `Windows.Media.Ocr` for character recognition on screenshots.

| Step | File | Change |
| :--- | :--- | :--- |
| **C.1** | `src/utils/computerUse/win32/ocr.ts` | NEW: Screenshot + OCR identification. |
| **C.2** | `packages/@ant/computer-use-mcp/src/tools.ts` | ADDED: `screen_ocr` tool definition. |

**`ocr.ts` Exported Functions**:
```typescript
// OCR on a screen region
ocrRegion(x: number, y: number, w: number, h: number, lang?: string): OcrResult

// OCR on a specific window
ocrWindow(windowTitle: string, lang?: string): OcrResult

interface OcrResult {
  text: string
  lines: { text: string, bounds: {x,y,w,h} }[]
  language: string
}
```

**Verified Available Languages**: English (en-US) + Chinese (zh-Hans-CN).

**Verification Criteria**:
- Successfully identify English and Chinese in screen regions.
- Return text content along with positional information for each line.

### Phase D: High-Frequency Operation Performance Optimization

**Problem**: 273ms overhead for each PowerShell startup slows down high-frequency operations like mouse movement.
**Solution**: Use .NET APIs like `System.Windows.Forms.Clipboard` directly instead of PowerShell subprocesses.

| Step | File | Change |
| :--- | :--- | :--- |
| **D.1** | `src/utils/computerUse/executor.ts` | Replace PowerShell with direct API for clipboard operations. |
| **D.2** | Persistent PowerShell Process | Consider maintaining a persistent process via stdin/stdout to eliminate startup costs. |

**Direct Clipboard API** (Bypasses PowerShell subprocess):
```powershell
# Read: 50ms → <1ms
[System.Windows.Forms.Clipboard]::GetText()

# Write: 50ms → <1ms  
[System.Windows.Forms.Clipboard]::SetText($text)

# Image Detection
[System.Windows.Forms.Clipboard]::ContainsImage()
```

### Phase E: `request_access` Windows Adaptation

**Problem**: `request_access` relies on macOS bundleId for app identification, a concept that does not exist on Windows.
**Solution**: Use executable paths and window titles in place of bundleId on Windows.

| Step | File | Change |
| :--- | :--- | :--- |
| **E.1** | `packages/@ant/computer-use-mcp/src/toolCalls.ts` | `resolveRequestedApps` uses executable path matching on Windows. |
| **E.2** | `packages/@ant/computer-use-mcp/src/sentinelApps.ts` | ADDED: Windows dangerous apps list (cmd.exe, powershell.exe, etc.). |
| **E.3** | `packages/@ant/computer-use-mcp/src/deniedApps.ts` | ADDED: Identification rules for Windows browsers and terminals. |
| **E.4** | `src/utils/computerUse/hostAdapter.ts` | `ensureOsPermissions` checks UAC status on Windows. |

**Windows App Identification Mapping**:
```
macOS bundleId          →  Windows Equivalent
com.apple.Safari        →  msedge.exe (or window title match)
com.google.Chrome       →  chrome.exe
com.apple.Terminal      →  WindowsTerminal.exe / cmd.exe
```

### Phase F: Global Hotkeys (ESC Interception)

**Problem**: Currently, non-darwin platforms skip ESC hotkeys, using Ctrl+C instead.
**Solution**: Implement using `RegisterHotKey` or `SetWindowsHookEx(WH_KEYBOARD_LL)`.

| Step | File | Change |
| :--- | :--- | :--- |
| **F.1** | `src/utils/computerUse/escHotkey.ts` | Windows Branch: RegisterHotKey for ESC. |

**Low Priority**: The current Ctrl+C fallback is functional; ESC hotkey is an experience optimization.

## 5. Execution Priority

```
Phase A: Window-Bound Screenshots       ← P0 Core requirement; "operate on other interfaces"
Phase B: UI Automation                  ← P0 Core capability; AI understands UI structure
Phase C: OCR                            ← P1 Value-added capability; AI reads screen text
Phase D: Performance Optimization       ← P1 Experience optimization; speed up frequent ops
Phase E: request_access Adaptation      ← P1 Feature completeness; permission model adaptation
Phase F: ESC Hotkey                     ← P2 Experience optimization; later phase
```

## 6. Estimated Modification Volume per Phase

| Phase | New Files | Modified Files | New LoC | Risk |
| :--- | :--- | :--- | :--- | :--- |
| **A Window Screenshots** | 2 | 1 | ~200 | Low |
| **B UI Automation** | 1 | 1 | ~300 | Medium |
| **C OCR** | 1 | 1 | ~150 | Low |
| **D Performance Optimization** | 0 | 2 | ~50 | Low |
| **E request_access** | 0 | 3 | ~100 | Medium |
| **F ESC Hotkey** | 0 | 1 | ~50 | Low |
| **Total** | **4** | **9** | **~850** | — |

## 7. Files to Remain Unchanged

- `backends/darwin.ts` (both packages).
- `backends/linux.ts` (both packages).
- macOS-related code paths in `src/utils/computerUse/`.
- Copied reference project code in `packages/@ant/computer-use-mcp/src/` (only Windows tools will be appended).

## 8. Comparison with macOS/Linux Solutions

| Capability | macOS | Windows (Post-Enhancement) | Linux |
| :--- | :--- | :--- | :--- |
| **Screenshotting** | `SCContentFilter` (per-app) | **`PrintWindow` (per-window)** | `scrot` (full/region) |
| **UI Structure** | Accessibility API | **UI Automation** | None |
| **OCR** | None built-in | **`Windows.Media.Ocr`** | None built-in |
| **Keyboard/Mouse** | `CGEvent` + `enigo` | `SendInput` + `keybd_event` | `xdotool` |
| **Window Management** | `NSWorkspace` | **`EnumWindows` + Win32** | `wmctrl` |
| **Clipboard** | `pbcopy`/`pbpaste` | **Direct Clipboard API** | `xclip` |
| **ESC Hotkey** | `CGEventTap` | `RegisterHotKey` | None |
| **App Identification**| `bundleId` | Executable path + Window title | `/proc` + `wmctrl` |

**With these enhancements, the Windows implementation will surpass the macOS solution in UI Automation and OCR capabilities**, neither of which are part of the original macOS implementation (which relies on screenshots and Claude's visual understanding without structured UI data).
