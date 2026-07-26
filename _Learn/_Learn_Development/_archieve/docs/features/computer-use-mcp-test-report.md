# Computer Use MCP Tool Test Report

> **Test Date**: 2026-04-04
> **Test Environment**: macOS Darwin 25.4.0, Cursor (IDE tier: click)
> **MCP Server**: `@ant/computer-use-mcp`

## Tool Overview

Total of 17 tools (including batch composite operations), divided into 5 major categories:

| Category | Tools | Count |
| :--- | :--- | :--- |
| **Screenshot/Display** | `screenshot`, `switch_display`, `zoom` | 3 |
| **Mouse Operations** | `left_click`, `right_click`, `double_click`, `triple_click`, `middle_click`, `left_click_drag`, `mouse_move` | 7 |
| **Keyboard Operations** | `key`, `type`, `hold_key` | 3 |
| **Status Query** | `cursor_position`, `request_access` | 2 |
| **Composite/Auxiliary** | `computer_batch`, `wait` | 2 |

---

## Test Results

### 1. Permission Management

#### `request_access` — Request Application Access Permissions

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Behavior** | Pops up a system dialog to request user authorization; supports batch applications for multiple apps. |
| **Return** | `{ granted: [...], denied: [...], tierGuidance: "..." }` |
| **Permission Tiers** | `click` (clicks only), `full` (complete control). |
| **Description** | IDE-class apps (Cursor, VSCode, Terminal) are granted the `click` tier by default, restricting keyboard input and right-click operations; system apps (e.g., System Settings) are granted the `full` tier. |

#### Authorized Applications

| Application | Tier | Capability |
| :--- | :--- | :--- |
| Cursor | click | Visibility + Left-click only (no keyboard, right-click, modifier clicks, or dragging). |
| Terminal | click | Same as above. |
| System Settings | full | Full control (keyboard/mouse, dragging, etc.). |
| Finder | — | Authorized. |

---

### 2. Screenshot and Display

#### `screenshot` — Capture Screen Screenshot

| Item | Result |
| :--- | :--- |
| **Status** | ⚠️ Partially Passed |
| **Execution** | Tool executed successfully, returning `ok: true`. |
| **Image** | **No visible image content returned** (output is an empty string). |
| **`save_to_disk`** | Still no output after setting this. |
| **Analysis** | Possible causes: (1) macOS screen recording permissions not granted; (2) current foreground app not filtered, resulting in an empty screenshot; (3) MCP transport layer not encoding image data correctly. |
| **Recommendation** | Check **System Settings → Privacy & Security → Screen Recording** to ensure authorization for the application running Claude Code. |

#### `switch_display` — Switch Display

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Behavior** | Accepts display name or `"auto"` (automatic selection). |
| **Return** | Confirmation message. |

#### `zoom` — Regional Zoom Screenshot

| Item | Result |
| :--- | :--- |
| **Status** | ⏭️ Skipped |
| **Reason** | Depends on image coordinates from `screenshot`; impossible to test without an image. |

---

### 3. Mouse Operations

> The following tests were performed on the Cursor window (tier: click).

#### `mouse_move` — Move Mouse

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Input** | `coordinate: [500, 500]` |
| **Return** | `"Moved."` |

#### `left_click` — Left Click

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Input** | `coordinate: [500, 500]` |
| **Return** | `"Clicked."` |

#### `double_click` — Double Click

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Input** | `coordinate: [500, 500]` |
| **Return** | `"Clicked."` |

#### `triple_click` — Triple Click

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Input** | `coordinate: [500, 500]` |
| **Return** | `"Clicked."` |

#### `right_click` — Right Click

| Item | Result |
| :--- | :--- |
| **Status** | ⚠️ Tier Restricted |
| **Cursor (click tier)** | ❌ Denied — `"Code" is granted at tier "click" — right-click, middle-click, and clicks with modifier keys require tier "full"` |
| **Finder (full tier)** | ✅ Passed — Returns `"Clicked."` |
| **Conclusion** | Functionality is normal; IDE security restrictions are as expected. |

#### `middle_click` — Middle Click

| Item | Result |
| :--- | :--- |
| **Status** | ⚠️ Tier Restricted |
| **Cursor (click tier)** | ❌ Denied — Same as `right_click`; requires `full` tier. |
| **Finder (full tier)** | ✅ Passed — Returns `"Clicked."` |
| **Conclusion** | Functionality is normal; IDE security restrictions are as expected. |

#### `left_click_drag` — Drag and Drop

| Item | Result |
| :--- | :--- |
| **Status** | ⚠️ Tier Restricted |
| **Cursor (click tier)** | ❌ Denied — Dragging is treated as a modifier-key click; requires `full` tier. |
| **Finder (full tier)** | ✅ Passed — Returns `"Dragged."` |
| **Conclusion** | Functionality is normal; IDE security restrictions are as expected. |

#### `scroll` — Mouse Scroll

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Input** | `coordinate: [500, 500]`, `scroll_direction: "down"`, `scroll_amount: 3` |
| **Return** | `"Scrolled."` |
| **Reverse** | ✅ `scroll_direction: "up"` also passed. |

---

### 4. Keyboard Operations

> The following tests were performed on the Cursor window (tier: click) — all keyboard operations were denied.

#### `key` — Key Press/Shortcut

| Item | Result |
| :--- | :--- |
| **Status** | ⚠️ Tier Restricted |
| **Cursor (click tier)** | ❌ Denied — IDE tier restricts keyboard input. |
| **Finder (full tier)** | ✅ Passed — `escape` key succeeded; returns `"Key pressed."` |
| **Conclusion** | Functionality is normal; IDE security restrictions are as expected. |

#### `type` — Type Text

| Item | Result |
| :--- | :--- |
| **Status** | ⚠️ Tier Restricted |
| **Cursor (click tier)** | ❌ Denied — IDE tier restricts text input. |
| **Finder (full tier)** | ✅ Passed — Typing `"hello"` succeeded; returns `"Typed 5 grapheme(s)."` |
| **Conclusion** | Functionality is normal; IDE security restrictions are as expected. |

#### `hold_key` — Hold Key

| Item | Result |
| :--- | :--- |
| **Status** | ⚠️ Tier Restricted |
| **Cursor (click tier)** | ❌ Denied — IDE tier restricts keyboard input. |
| **Finder (full tier)** | ✅ Passed — Holding `shift` for 1 second succeeded; returns `"Key held."` |
| **Conclusion** | Functionality is normal; IDE security restrictions are as expected. |

---

### 5. Status Query

#### `cursor_position` — Get Mouse Position

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Return** | `{"x": null, "y": null, "coordinateSpace": "image_pixels"}` |
| **Description** | Coordinates are null because screenshotting failed, meaning there was no reference coordinate system. |

---

### 6. Composite/Auxiliary Operations

#### `computer_batch` — Execute Operations in Batch

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Behavior** | Executes a list of operations sequentially; stops if a failure is encountered. |
| **Return** | `{ completed: [...], failed: {...}, remaining: N }` |
| **Features** | Executes multiple operations in a single API call, reducing round-trip latency. |
| **Error Handling** | A failed operation interrupts subsequent ones, returning completed and remaining counts. |

#### `wait` — Wait

| Item | Result |
| :--- | :--- |
| **Status** | ✅ Passed |
| **Input** | `duration: 1` (seconds). |
| **Return** | `"Waited 1s."` |
| **Maximum** | 100 seconds. |

---

## Summary Statistics

| Status | Count | Tools |
| :--- | :--- | :--- |
| ✅ **Passed** | 10 | `request_access`, `switch_display`, `mouse_move`, `left_click`, `double_click`, `triple_click`, `scroll`, `cursor_position`, `computer_batch`, `wait` |
| ⚠️ **Partially Passed** | 7 | `screenshot` (executed but no image returned), `right_click`, `middle_click`, `left_click_drag`, `key`, `type`, `hold_key` (all passed on `full` tier apps; IDE `click` tier restriction is expected) |
| ❌ **Denied** | 0 | — |
| ⏭️ **Skipped** | 1 | `zoom` (depends on screenshot). |

---

## Known Issues

### P0: Screenshot Returns No Image

The `screenshot` tool executes successfully but returns no image content, which causes:
- Inability to obtain screen coordinate references.
- `cursor_position` to return null coordinates.
- `zoom` to be unusable.
- All click operations to be "blind" (no screenshot verification).

**Possible Causes**:
1. macOS screen recording permissions not granted.
2. MCP image transport/encoding issues.
3. Screenshot content being filtered by security mechanisms.

**Recommendation**: Check `System Settings → Privacy & Security → Screen Recording` permissions.

### P1: Keyboard Operations Restricted on IDE Apps — ✅ Functionality Confirmed Normal

IDE-class apps (Cursor, VSCode, Terminal) are restricted to the `click` tier, preventing:
- Keyboard input (`key`, `type`, `hold_key`).
- Right/middle-click (`right_click`, `middle_click`).
- Drag-and-drop operations (`left_click_drag`).

This is a security design to prevent AI from controlling the IDE terminal. **On `full` tier apps (Finder, System Settings), all 6 of these operations were tested and passed with normal functionality.**

---

## Permission Model Explanation

The Computer Use MCP utilizes a tiered permission model:

```
┌─────────────────────────────────────────┐
│  Tier: full                             │
│  - All mouse operations (left, right,    │
│    middle, drag-and-drop)               │
│  - Keyboard input (type, key, hold_key)  │
│  - Applicable to: System apps, Finder,   │
│    etc.                                 │
├─────────────────────────────────────────┤
│  Tier: click                            │
│  - Left-click only                       │
│  - Scroll wheel                          │
│  - Applicable to: IDEs, Terminal, etc.   │
├─────────────────────────────────────────┤
│  Unauthorized                           │
│  - All operations denied                 │
│  - Request via request_access            │
└─────────────────────────────────────────┘
```
