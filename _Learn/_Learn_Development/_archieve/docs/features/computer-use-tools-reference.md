# Computer Use Tool Reference Documentation

## Overview

Computer Use provides 38 tools, divided into three categories:

| Category | Platform | Tool Count | Description |
| :--- | :--- | :--- | :--- |
| **General Tools** | All Platforms | 24 | Standard official Computer Use capabilities. |
| **Windows Exclusive Tools** | Win32 | 11 | Enhanced capabilities for bound window mode. |
| **Teaching Tools** | All Platforms | 3 | Step-by-step guidance mode (requires `teachMode` to be enabled). |

---

## I. General Tools (24 Tools)

Available on all platforms. When no window is bound, operations target the entire screen.

### Permissions and Sessions

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `request_access` | `apps[]`, `reason`, `clipboardRead?`, `clipboardWrite?`, `systemKeyCombos?` | Requests permission to operate on applications. A prerequisite for all other tools. |
| `list_granted_applications` | — | Lists applications authorized for the current session. |

### Screenshot and Display

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `screenshot` | `save_to_disk?` | Captures the current screen. When a window is bound, it captures only that window (`PrintWindow`). Returns the image + a list of GUI elements (Windows). |
| `zoom` | `region: [x1,y1,x2,y2]` | Captures a high-resolution image of a specified region. Coordinates are based on the most recent full-screen screenshot. |
| `switch_display` | `display` | Switches the target display for screenshots. |

### Mouse Operations

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `left_click` | `coordinate: [x,y]`, `text?` (Modifier) | Left-click. `text` can be "shift", "ctrl", or "alt" for combined clicks. |
| `double_click` | `coordinate`, `text?` | Double-click. |
| `triple_click` | `coordinate`, `text?` | Triple-click (selects an entire line). |
| `right_click` | `coordinate`, `text?` | Right-click. |
| `middle_click` | `coordinate`, `text?` | Middle-click. |
| `mouse_move` | `coordinate` | Moves the mouse without clicking. |
| `left_click_drag` | `coordinate` (end), `start_coordinate?` (start) | Drag and drop. |
| `left_mouse_down` | — | Presses the left mouse button and holds it. |
| `left_mouse_up` | — | Releases the left mouse button. |
| `cursor_position` | — | Gets the current mouse position. |

### Keyboard Operations

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `type` | `text` | Types text. |
| `key` | `text` (e.g., "ctrl+s"), `repeat?` | Presses a key or key combination. |
| `hold_key` | `text`, `duration` (seconds) | Holds a key for a specified duration. |

### Scrolling

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `scroll` | `coordinate`, `scroll_direction`, `scroll_amount` | Scrolls in a direction: up, down, left, or right. |

### Application Management

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `open_application` | `app` | Opens an application. On Windows, this automatically binds to the window. |

### Clipboard

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `read_clipboard` | — | Reads text from the clipboard. |
| `write_clipboard` | `text` | Writes text to the clipboard. |

### Others

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `wait` | `duration` (seconds) | Waits for a specified duration. |
| `computer_batch` | `actions[]` | Executes multiple actions in batch to reduce API round-trips. |

---

## II. Windows Exclusive Tools (12 Tools)

Visible only on the Windows platform. Core capability: **Independent operations after window binding—no preemption of user mouse and keyboard.**

### Operating Modes

```
┌──────────────────────────────────────────────────┐
│                  Unbound Mode                    │
│  Uses general tools (left_click/type/key/scroll) │
│  Target: Entire screen                           │
│  Input: Global SendInput (moves the real mouse)   │
└──────────────────────────────────────────────────┘
                        │
          bind_window / open_application
                        ▼
┌──────────────────────────────────────────────────┐
│                  Bound Window Mode               │
│  Uses Win32 tools (virtual_mouse/virtual_keyboard)│
│  Target: Bound window                            │
│  Input: SendMessageW (no real mouse/keyboard move)│
│  Visuals: DWM green border + virtual cursor +    │
│            status indicator                      │
└──────────────────────────────────────────────────┘
```

### Window Binding

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `bind_window` | `action`: list/bind/unbind/status | Window binding management. |

**Action Details:**

| action | Parameters | Description |
| :--- | :--- | :--- |
| `list` | — | Lists all visible windows (HWND, PID, title). |
| `bind` | `title?`, `hwnd?`, `pid?` | Binds to a specific window. Sets the DWM green border, starts the virtual cursor, starts the status indicator, and briefly activates the window to ensure it can receive input. |
| `unbind` | — | Releases the binding and restores full-screen mode. |
| `status` | — | Views the current binding status (HWND, title, PID, window rectangle). |

### Window Management

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `window_management` | `action`, `x?`, `y?`, `width?`, `height?` | Window operations (Win32 API, does not use global shortcuts). |

**Action Details:**

| action | Description |
| :--- | :--- |
| `minimize` | `ShowWindow(SW_MINIMIZE)` |
| `maximize` | `ShowWindow(SW_MAXIMIZE)` |
| `restore` | `ShowWindow(SW_RESTORE)` — Restores from minimized/maximized state. |
| `close` | `SendMessage(WM_CLOSE)` — Graceful closure. |
| `focus` | `SetForegroundWindow` + `BringWindowToTop` — Activates the window. |
| `move_offscreen` | `SetWindowPos(-32000, -32000)` — Moves the window off-screen (still accessible via `SendMessage`/`PrintWindow`). |
| `move_resize` | `SetWindowPos` — Moves or resizes the window to a specified position and size. |
| `get_rect` | `GetWindowRect` — Gets the current position and size. |

### Virtual Mouse

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `virtual_mouse` | `action`, `coordinate: [x,y]`, `start_coordinate?` | Operates a virtual mouse within the bound window. |

**Action Details:**

| action | Description |
| :--- | :--- |
| `click` | Left-click. The virtual cursor moves to the coordinate with a flash animation. |
| `double_click` | Double-click. |
| `right_click` | Right-click. |
| `move` | Moves the virtual cursor (no click). |
| `drag` | Press → Move → Release. Requires `start_coordinate`. |
| `down` | Presses the left mouse button and holds it. |
| `up` | Releases the left mouse button. |

**Difference from General Mouse Tools:**

| | General (`left_click`, etc.) | `virtual_mouse` |
| :--- | :--- | :--- |
| **Input Method** | `SendInput` (Global) | `SendMessageW` (Window-level) |
| **Real Mouse** | Moves. | **Remains stationary.** |
| **User Interference**| Yes. | **None.** |
| **Applicability** | When unbound. | **When bound.** |

### Virtual Keyboard

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `virtual_keyboard` | `action`, `text`, `duration?`, `repeat?` | Operates a virtual keyboard within the bound window. |

**Action Details:**

| action | text Meaning | Description |
| :--- | :--- | :--- |
| `type` | Text to enter. | `SendMessageW(WM_CHAR)`, supports Unicode Chinese/emoji. |
| `combo` | Key combination (e.g., "ctrl+s"). | `WM_KEYDOWN`/`UP` sequence. |
| `press` | Single key name. | Presses and holds (used with `release`). |
| `release` | Single key name. | Releases the key. |
| `hold` | Key or combination. | Holds for specified seconds and then releases. |

**Difference from General Keyboard Tools:**

| | General (`type`/`key`) | `virtual_keyboard` |
| :--- | :--- | :--- |
| **Input Method** | `SendInput` (Global) | `SendMessageW` (Window-level) |
| **Physical Keyboard**| Potential conflicts. | **No conflicts.** |
| **Applicability** | When unbound. | **When bound.** |

**Note**: `SendMessageW` is ineffective for modern applications like Windows Terminal (ConPTY). These applications require general tools and window activation.

### Mouse Wheel

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `mouse_wheel` | `coordinate: [x,y]`, `delta`, `direction?` | `WM_MOUSEWHEEL` mouse wheel scrolling. |

**Parameter Description:**
- `delta`: Positive = Up, Negative = Down. 1 unit ≈ 3 lines.
- `direction`: "vertical" (default) or "horizontal".
- `coordinate`: Point of action—determines which panel or region receives the scroll.

**Difference from General `scroll`:**

| | `scroll` | `mouse_wheel` |
| :--- | :--- | :--- |
| **Principle** | `WM_VSCROLL`/`WM_HSCROLL` | **`WM_MOUSEWHEEL`** |
| **Excel** | ❌ | ✅ |
| **Browser** | ❌ | ✅ |
| **Code Editor** | ❌ | ✅ |

### Element-level Operations

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `click_element` | `name?`, `role?`, `automationId?` | Clicks a GUI element based on its accessibility name or role. |
| `type_into_element` | `name?`, `role?`, `automationId?`, `text` | Types text into an element by name. |

**Working Principle:**
1. Uses UI Automation to find matching elements in the bound window.
2. `click_element`: Attempts `InvokePattern` (buttons/menus) first; falls back to `SendMessage` click at the center of the `BoundingRect`.
3. `type_into_element`: Attempts `ValuePattern` to set the value directly; falls back to clicking for focus followed by `WM_CHAR` input.

**Use Cases:**
- When an element name is visible in a screenshot but coordinates are imprecise.
- When an Accessibility Snapshot lists the name or `automationId` of an element.
- More reliable than coordinate clicking (unaffected by window scaling or DPI).

### Terminal Interaction

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `open_terminal` | `agent`, `command?` | Opens a new terminal window and starts an AI agent (`claude`/`codex`/`gemini`/`custom`). Automatically binds to the window and verifies via screenshot. |
| `activate_window` | `click_x?`, `click_y?` | Activates the bound window: `SetForegroundWindow` + `BringWindowToTop` + click to ensure focus. |
| `prompt_respond` | `response_type`, `arrow_direction?`, `arrow_count?`, `text?` | Handles terminal Yes/No/Selection prompts. |

**`open_terminal` Agent Types:**

| agent | Command | Description |
| :--- | :--- | :--- |
| `claude` | `claude` | Starts Claude Code. |
| `codex` | `codex` | Starts Codex. |
| `gemini` | `gemini` | Starts Gemini. |
| `custom` | User specified. | Custom command. |

**`response_type` Details:**

| response_type | Action | Scenario |
| :--- | :--- | :--- |
| `yes` | Sends 'y' + Enter. | npm "Continue? (y/n)" |
| `no` | Sends 'n' + Enter. | Denying confirmation. |
| `enter` | Sends Enter. | Accepting default options. |
| `escape` | Sends Escape. | Canceling an operation. |
| `select` | ↑/↓ arrow × N + Enter. | `inquirer` selection menu. |
| `type` | Types text + Enter. | Text input prompt. |

### Status Indicator

| Tool | Parameters | Description |
| :--- | :--- | :--- |
| `status_indicator` | `action`: show/hide/status, `message?` | Controls a floating status label at the bottom of the bound window. |

---

## III. Teaching Tools (3 Tools)

Requires `teachMode` to be enabled.

| Tool | Description |
| :--- | :--- |
| `request_teach_access` | Requests permission for teaching guidance mode. |
| `teach_step` | Displays a single-step guidance hint and waits for the user to click Next. |
| `teach_batch` | Enqueues multiple steps of guidance in batch. |

---

## Operation Flows

### Flow 1: Full-screen Operations (Unbound)

```
request_access(apps=["Notepad"])
open_application(app="Notepad")          ← Automatically binds window
screenshot                               ← PrintWindow screenshot + GUI element list
left_click(coordinate=[500, 300])        ← Global SendInput
type(text="hello world")                 ← Global SendInput
key(text="ctrl+s")                       ← Global SendInput
```

### Flow 2: Bound Window Operations (Recommended, No User Interference)

```
request_access(apps=["Notepad"])
bind_window(action="list")               ← List all windows
bind_window(action="bind", title="Notepad") ← Bind + Green border + Virtual cursor
screenshot                               ← PrintWindow of the bound window
virtual_mouse(action="click", coordinate=[500, 300])   ← SendMessageW, no real mouse move
virtual_keyboard(action="type", text="hello world")    ← SendMessageW, no physical keyboard use
virtual_keyboard(action="combo", text="ctrl+s")        ← Save
mouse_wheel(coordinate=[500, 400], delta=-5)           ← Scroll down
bind_window(action="unbind")             ← Release binding
```

### Flow 3: Operations by Element Name

```
bind_window(action="bind", title="Notepad")
screenshot                               ← Returns screenshot + GUI elements list
click_element(name="Save", role="Button") ← UI Automation find and click
type_into_element(role="Edit", text="new content")
```

### Flow 4: Terminal Interaction

```
bind_window(action="bind", title="PowerShell")
screenshot
prompt_respond(response_type="yes")      ← Answers y + Enter
prompt_respond(response_type="select", arrow_direction="down", arrow_count=2)  ← Selects 3rd item
```

### Flow 5: Excel/Browser Scrolling

```
bind_window(action="bind", title="Excel")
screenshot
mouse_wheel(coordinate=[600, 400], delta=-10)            ← Scrolls down 10 units
mouse_wheel(coordinate=[600, 400], delta=5, direction="horizontal")  ← Scrolls right
```

---

## Application Compatibility

| Application Type | SendMessageW (virtual_*) | Element Ops (click_element) | Note |
| :--- | :--- | :--- | :--- |
| **Traditional Win32** | ✅ | ✅ | Perfect support (Notepad, WordPad). |
| **Office (Excel/Word)**| ✅ (COM Automation) | ✅ | Via COM API. |
| **WPF Applications** | ✅ | ✅ | Standard UIA support. |
| **Electron/Chrome** | ⚠️ Partial | ⚠️ Partial | Internal rendering doesn't use Win32 messages. |
| **UWP/WinUI** | ❌ | ❌ | ConPTY doesn't accept SendMessageW. |
| **Browser Web Content**| ❌ | ❌ | Requires global SendInput. |

**For applications that do not support SendMessageW**, use general tools (`left_click`/`type`/`key`) along with `window_management(action="focus")` to activate the window first.

---

## Visualization during Window Binding

Three layers of visualization are automatically started upon binding a window:

1.  **DWM Green Border**: The window's border turns green with zero offset.
2.  **Virtual Mouse Cursor**: A red arrow icon follows `virtual_mouse` operations and flashes upon clicking.
3.  **Status Indicator**: A floating label at the bottom of the window displays current operations (controlled via `status_indicator`).

---

## Accessibility Snapshot

Each time a `screenshot` is taken while a window is bound, a list of GUI elements is automatically attached:

```
GUI elements in this window:
[Button] "Save" (120,50 80x30) enabled
[Edit] "" (200,80 400x25) enabled value="hello" id=textBox1
[MenuItem] "File" (10,0 40x25) enabled
[MenuItem] "Edit" (50,0 40x25) enabled
[CheckBox] "Auto-save" (300,50 100x20) enabled id=chkAutoSave
```

The model receives **both the screenshot image and the structured element list**, allowing it to choose:
- Coordinate-based: `virtual_mouse(action="click", coordinate=[120, 50])`
- Name-based: `click_element(name="Save")`

---

## UI Automation Control Patterns Reference

`click_element` / `type_into_element` use UI Automation Control Patterns internally. Currently implemented and planned:

| Pattern | Purpose | Current Status | Can be used for |
| :--- | :--- | :--- | :--- |
| `InvokePattern` | Triggers a click. | ✅ Implemented (`click_element`) | Buttons, Menu Items, Links. |
| `ValuePattern` | Reads/writes text. | ✅ Implemented (`type_into_element`) | Textboxes, ComboBoxes. |
| `TogglePattern` | Toggles state. | ❌ Planned | Checkboxes, Toggles. |
| `SelectionPattern` | Selects items. | ❌ Planned | Dropdowns, Lists. |
| `ScrollPattern` | Programmatic scroll. | ❌ Planned (use `mouse_wheel`) | Lists, Trees, Panels. |
| `ExpandCollapsePattern`| Expands/Collapses. | ❌ Planned | Tree nodes, Accordions. |
| `WindowPattern` | Window operations. | ❌ Planned (use `window_management`) | Maximize, Close. |
| `TextPattern` | Reads document text. | ❌ Planned | Documents, Rich Text. |
| `GridPattern` | Table operations. | ❌ Planned | Excel cells, Data Grids. |
| `TablePattern` | Table structure. | ❌ Planned | Headers, Row/Column relationships. |
| `RangeValuePattern` | Range value ops. | ❌ Planned | Sliders, Progress bars. |
| `TransformPattern` | Move/Scale. | ❌ Planned | Draggable elements. |

**Roadmap**: Prioritize `TogglePattern` (checkboxes) and `SelectionPattern` (dropdowns), as these are most common in form automation.

---

## Screen Capture Technical Comparison

Currently using Python Bridge (mss) for screenshots, which uses GDI BitBlt under the hood.

| Method | API | Current Status | Performance | Advantages | Limitations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **GDI BitBlt** | `BitBlt` / `PrintWindow` | ✅ Current (mss/bridge.py) | ~300ms | Simple, stable, supports background windows. | No hardware acceleration; complex DPI handling. |
| **DXGI Desktop Duplication**| `IDXGIOutputDuplication` | ❌ Planned | ~16ms (60fps) | Hardware accelerated, HDR support, direct GPU read. | No single-window capture; requires D3D11. |
| **Windows.Graphics.Capture**| `GraphicsCaptureItem` | ❌ Planned | ~16ms | Latest API; supports single window/display; system-level permission. | Win10 1903+; requires initial user confirmation. |

### Recommended Upgrade Path

```
Current: GDI BitBlt (mss) ─── Full-screen ~300ms, Window ~300ms (PrintWindow)
  │
  ├─ Near-term: DXGI Desktop Duplication ─── Full-screen ~16ms, but no single-window support
  │
  └─ Long-term: Windows.Graphics.Capture ─── Both full-screen + single-window ~16ms
```

---

## Input Method Technical Matrix

Different application types require different input methods:

| Method | API | Advantages | Limitations | Applicable Apps |
| :--- | :--- | :--- | :--- | :--- |
| **SendMessageW** | `WM_CHAR` / `WM_KEYDOWN` | No focus grab, no real mouse/key move. | Not supported by modern apps. | Traditional Win32 (Notepad/Office/WPF). |
| **SendInput** | `INPUT` structure | Supported by all apps. | **Requires foreground focus**, interferes with user. | All apps (General fallback). |
| **WriteConsoleInput**| Console API | Direct write to console buffer. | Requires `AttachConsole` (may be denied). | cmd/PowerShell (not Windows Terminal). |
| **UI Automation** | `InvokePattern` / `ValuePattern` | Semantic operations, most reliable. | Some apps don't expose UIA interfaces. | Apps with UIA support. |
| **COM Automation** | Excel/Word COM | Full programmatic control. | Office apps only. | Excel / Word. |
| **Clipboard + Paste**| `SetClipboardData` + `Ctrl+V` | Bypasses input limits. | Overwrites user clipboard. | General fallback. |

### Recommended Input Strategy by App Type

| App Type | Preferred | Fallback | Note |
| :--- | :--- | :--- | :--- |
| **Traditional Win32** | `SendMessageW` | UIA `ValuePattern` | Virtual input works perfectly. |
| **Office (Excel/Word)**| COM Automation | `SendMessageW` | COM provides structured operations. |
| **WPF Applications** | `SendMessageW` | UIA | Standard Win32 message loop. |
| **Electron/Chrome** | UIA | Clipboard Paste | Internal rendering doesn't use Win32. |
| **Windows Terminal** | `SendInput` (req. focus) | Clipboard Paste | ConPTY doesn't accept external messages. |
| **UWP/WinUI Apps** | `SendInput` (req. focus) | UIA | XAML rendering doesn't use Win32 messages. |

---

## Known Limitations and To-Do

| Limitation | Impact | Plan |
| :--- | :--- | :--- |
| Windows Terminal ignores `SendMessageW`. | Virtual keyboard/mouse ineffective. | Auto-detect app type; switch to `SendInput` + brief activation for terminals. |
| `PrintWindow` doesn't capture alternate screen buffers. | Ink REPL screens missed. | Switch to `Windows.Graphics.Capture`. |
| Accessibility Snapshot is slow for large apps (>30s). | Timeouts for complex apps like Excel. | Limit traversal depth + add timeout protection. |
| DWM border may not work for custom title bars. | Invisible border on some Electron apps. | Detect and fallback to overlay window solution. |

---

## Technical Roadmap

### Phase 1 (Current) — Basic Functionality
- ✅ `SendMessageW` Virtual Input.
- ✅ `PrintWindow`/`mss` Screenshotting.
- ✅ UI Automation (`InvokePattern` + `ValuePattern`).
- ✅ Accessibility Snapshot.
- ✅ DWM Border Indication.
- ✅ Python Bridge.

### Phase 2 (Near-term) — Compatibility Enhancement
- ⬜ Application type auto-detection (Win32 vs Terminal vs UWP).
- ⬜ Auto-switch to `SendInput` + brief activation for terminals.
- ⬜ `TogglePattern` / `SelectionPattern` support.
- ⬜ DXGI Desktop Duplication high-speed screenshotting.
- ⬜ Accessibility Snapshot timeout protection.

### Phase 3 (Long-term) — Advanced Capabilities
- ⬜ `Windows.Graphics.Capture` (Real-time single window capture).
- ⬜ Screenshot element annotation (Mark IDs on images).
- ⬜ Browser DOM extraction (Extract web structure when bound).
- ⬜ `GridPattern` / `TablePattern` (Excel cell-level operations).
- ⬜ `TextPattern` (Document content reading).
- ⬜ Multi-window coordinated operations.
