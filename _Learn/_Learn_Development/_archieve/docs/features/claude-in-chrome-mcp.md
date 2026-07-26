# Claude in Chrome — User Operations Guide

## 1. Feature Introduction

"Claude in Chrome" allows Claude Code to directly control your Google Chrome browser. You can use natural language to ask Claude to:

- Open web pages, navigate, and move forward or backward.
- Fill out forms and upload images.
- Take screenshots and record GIFs.
- Read page content (DOM structure, plain text).
- Execute JavaScript.
- Monitor network requests and console logs.
- Manage browser tabs.

## 2. Prerequisites

| Condition | Description |
| :--- | :--- |
| **Claude Code Subscription** | Requires a Claude Pro, Max, or Team subscription; browser extension features are not available to free users. |
| **Chrome Browser** | Google Chrome must be installed. |
| **Claude in Chrome Extension** | Installed from the Chrome Web Store (`claude.ai/chrome`). |
| **Claude Code CLI** | Running via `bun run dev` or a build artifact. |

## 3. Activation Methods

### Dev Mode

```bash
bun run dev -- --chrome
```

Upon startup, Claude will automatically detect if the Chrome extension is installed and register the browser control tools.

### Build Artifacts

```bash
node dist/cli.js --chrome
```

### Disabling

```bash
bun run dev -- --no-chrome
```

Alternatively, toggle the enabled/disabled state using the `/chrome` command within the REPL.

### Default Enablement via Configuration

Set `claudeInChromeDefaultEnabled` to `true` in your Claude Code settings to enable it automatically without needing the `--chrome` parameter.

## 4. Usage Flow

1.  **Start CLI** — Launch Claude Code with the `--chrome` parameter.
2.  **Verify Connection** — Type `/chrome` in the REPL to ensure the extension status shows "Installed / Connected."
3.  **Start Conversation** — Interact with Claude normally. When browser interaction is needed, ask directly, for example:
    - "Open https://example.com and take a screenshot."
    - "Search for the keyword 'xxx' on the current page."
    - "Fill out the login form with username 'admin'."
    - "Record a GIF of the current operation."
4.  **Permission Approval** — Claude will request your confirmation the first time it performs a browser operation.
5.  **Completion** — Claude will return results (screenshots, text, execution outputs, etc.) after finishing the operation.

## 5. Available Operations

### Page Interaction

| Operation | Description |
| :--- | :--- |
| `navigate` | Navigate to a specified URL, or go forward/backward. |
| `computer` | 13 types of actions including mouse clicks, movement, drag-and-drop, keyboard input, and screenshots. |
| `form_input` | Fill out form fields. |
| `upload_image` | Upload an image to a file input or drag-and-drop area. |
| `javascript_tool` | Execute JavaScript within the page context. |

### Page Reading

| Operation | Description |
| :--- | :--- |
| `read_page` | Obtain the accessibility tree (DOM structure) of the page. |
| `get_page_text` | Extract plain text content from the page. |
| `find` | Search for page elements using natural language. |

### Tab Management

| Operation | Description |
| :--- | :--- |
| `tabs_context_mcp` | Obtain information about the current tab group. |
| `tabs_create_mcp` | Create a new tab. |

### Monitoring and Debugging

| Operation | Description |
| :--- | :--- |
| `read_console_messages` | Read browser console logs. |
| `read_network_requests` | Read network request records. |

### Others

| Operation | Description |
| :--- | :--- |
| `resize_window` | Adjust the size of the browser window. |
| `gif_creator` | Record and export a GIF. |
| `shortcuts_list` | List available shortcuts. |
| `shortcuts_execute` | Execute a shortcut. |
| `update_plan` | Submit an operation plan to you for approval. |
| `switch_browser` | Switch to a different Chrome browser (Bridge mode only). |

## 6. Communication Modes

Claude in Chrome supports two methods for communicating with the browser:

### Local Socket (Default)

The Chrome extension establishes a Unix socket connection with the CLI via a Native Messaging Host. This is suitable for local development and requires no additional configuration.

### Bridge WebSocket

Relayed through Anthropic's bridge service, supporting remote control of the browser. This requires a `claude.ai` OAuth login.

## 7. FAQ

### Extension Shows as "Not Installed"

Ensure you have installed the "Claude in Chrome" extension from the Chrome Web Store and restarted your browser afterwards.

### Tools Do Not Appear in the Tool List

Verify that you started the CLI with the `--chrome` parameter or confirm the status via the `/chrome` command.

### Connection Timeout

Ensure that Chrome is running and the extension is enabled. The Native Messaging Host is registered automatically upon extension installation; if you have reinstalled the extension, please restart your browser.

### When Not Using Chrome Features

Simply start the CLI without the `--chrome` parameter. No browser-related modules will be loaded, and other features will remain unaffected.
