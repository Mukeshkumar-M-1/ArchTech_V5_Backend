# Claude Code Best (CCB) — All-Features Guide

This document covers **all features** restored or newly added to CCB across 13 PRs. It is organized by category, with each feature including a description, usage instructions, and examples.

---

## Table of Contents

1. [Buddy System](#1-buddy-system)
2. [Remote Control](#2-remote-control)
3. [Scheduled Tasks /schedule](#3-scheduled-tasks-schedule)
4. [Voice Mode](#4-voice-mode)
5. [Chrome Browser Control](#5-chrome-browser-control)
6. [Computer Use (Screen Control)](#6-computer-use-screen-control)
7. [Feature Flags and GrowthBook](#7-feature-flags-and-growthbook)
8. [/ultraplan (Advanced Planning)](#8-ultraplan-advanced-planning)
9. [Daemon Mode](#9-daemon-mode)
10. [Pipe IPC (Multi-instance Collaboration)](#10-pipe-ipc-multi-instance-collaboration)
11. [LAN Pipes (Local Area Network Group Control)](#11-lan-pipes-local-area-network-group-control)
12. [Monitor (Background Monitoring)](#12-monitor-background-monitoring)
13. [Workflow Scripts](#13-workflow-scripts)
14. [Coordinator Mode (Multi-worker Coordination)](#14-coordinator-mode-multi-worker-coordination)
15. [Proactive Mode](#15-proactive-mode)
16. [History / Snip Management](#16-history--snip-management)
17. [Fork Subagent](#17-fork-subagent)
18. [Other Restored Tools](#18-other-restored-tools)

---

## 1. Buddy System

**PR**: #82 `refactor(buddy): align companion system with official CLI`
**Feature Flag**: `BUDDY`

### Description
Buddy is a companion AI that runs in the background. While you engage in the main conversation, it asynchronously observes the session content and provides suggestions.

### Usage
```bash
# Automatically loaded at startup (feature enabled by default)
bun run dev

# During a conversation, Buddy will automatically provide suggestions at appropriate times.
# For example, while you are debugging, Buddy might suggest checking logs.
```

---

## 2. Remote Control

**PR**: #60 `feat: enable Remote Control (BRIDGE_MODE)` + #170 `feat: restore daemon supervisor`
**Feature Flag**: `BRIDGE_MODE`

### Description
Remotely control Claude Code sessions via WebSocket. Supports self-hosted private deployments.

### Usage
```bash
# Start in remote control mode
bun run dev -- remote-control

# Use a self-hosted server
CLAUDE_BRIDGE_BASE_URL=https://your-server.com CLAUDE_BRIDGE_OAUTH_TOKEN=your-token bun run dev --remote-control

# Or start within a session via the /remote-control command
/remote-control
```

### Commands
- `claude remote-control` / `claude rc` — Starts the remote control client.
- `claude bridge` — Same as above (alias).

---

## 3. Scheduled Tasks /schedule

**PR**: #88 `feat: enable /schedule by adding AGENT_TRIGGERS_REMOTE`
**Feature Flag**: `AGENT_TRIGGERS_REMOTE`

### Description
Create remote agent tasks scheduled for periodic execution, supporting cron expressions.

### Usage
```
/schedule create "Daily dependency update check" --cron "0 9 * * *" --prompt "Check for outdated dependencies in package.json and create update PRs"
/schedule list          — List all scheduled tasks
/schedule delete <id>   — Delete a specific task
```

---

## 4. Voice Mode

**PR**: #92 `feat: enable /voice mode with native audio binaries`
**Feature Flag**: `VOICE_MODE`

### Description
Push-to-Talk voice input where audio is streamed via WebSocket to Anthropic STT (Nova 3). Requires Anthropic OAuth authentication (not an API key).

### Usage
```bash
# Ensure you are logged in via OAuth
claude auth login

# Press and hold the designated key during a session to speak
# Transcription into text occurs automatically upon release
```

### Prerequisites
- Anthropic OAuth authentication (API key mode is not supported).
- System microphone permissions.

---

## 5. Chrome Browser Control

**PR**: #93 `feat: enable Claude in Chrome MCP with full browser control`
**Feature Flag**: `CHICAGO_MCP`

### Description
Control the browser via a Chrome extension: navigation, clicking, form filling, screenshots, and executing JS.

### Usage
```bash
# Start in a mode with Chrome control enabled
bun run dev -- --chrome

# Once the Chrome extension is installed, the AI can:
# - Open web pages and click buttons
# - Fill out forms
# - Capture page content screenshots
# - Execute JavaScript
```

### Available AI Tools
- `navigate` — Navigate to a URL.
- `click` / `find` / `form_input` — Page interaction.
- `get_page_text` / `read_page` — Read content.
- `javascript_tool` — Execute JavaScript.
- `gif_creator` — Record operation GIFs.

---

## 6. Computer Use (Screen Control)

**PR**: #98 + #137 `feat: Computer Use — Cross-platform Executor + Python Bridge + GUI Accessibility`
**Feature Flag**: `CHICAGO_MCP`

### Description
Cross-platform screen control: screenshots, mouse/keyboard simulation, and application management. Supports macOS and Windows; Linux backend is pending.

### Usage
```bash
# After startup, the AI can automatically invoke screen control tools
bun run dev

# The AI can:
# - Capture screen or window screenshots
# - Simulate keyboard input and mouse actions
# - List running applications
# - Use the clipboard
```

### Platform Support
| Platform | Screenshot | Keyboard/Mouse | App Management |
| :--- | :--- | :--- | :--- |
| macOS | ✅ | ✅ | ✅ |
| Windows | ✅ | ✅ | ✅ |
| Linux | ⏳ | ⏳ | ⏳ |

---

## 7. Feature Flags and GrowthBook

**PR**: #140 + #153 `feat: enable GrowthBook local gate defaults`
**Feature Flags**: `SHOT_STATS`, `PROMPT_CACHE_BREAK_DETECTION`, `TOKEN_BUDGET`

### Description
Local GrowthBook gate defaults mechanism to bypass remote feature flag services, ensuring functionality is available even without an internet connection.

### Usage
```bash
# Enable any feature via environment variables
FEATURE_PROACTIVE=1 bun run dev

# dev/build modes have their own default enablement lists
# See DEFAULT_FEATURES in scripts/dev.ts
```

### Key Feature Flags
| Flag | Description |
| :--- | :--- |
| `SHOT_STATS` | API call statistics. |
| `TOKEN_BUDGET` | Token budget control. |
| `PROMPT_CACHE_BREAK_DETECTION` | Prompt cache hit detection. |

---

## 8. /ultraplan (Advanced Planning)

**PR**: #156 `feat: enable /ultraplan and harden GrowthBook fallback chain`
**Feature Flag**: `ULTRAPLAN`

### Description
Advanced multi-agent planning mode. Breaks complex tasks into multiple stages, each assignable to different agents for parallel execution.

### Usage
```
/ultraplan Implement a complete user authentication system including registration, login, password reset, and OAuth integration.
```

The AI will generate:
1. Task breakdown (multiple stages).
2. Agent allocation per stage.
3. Dependency graph.
4. Parallel execution plan.

---

## 9. Daemon Mode

**PR**: #170 `feat: restore daemon supervisor and remoteControlServer command`
**Feature Flag**: `DAEMON`

### Description
Daemon mode allows Claude Code to run as a persistent background process, managing multiple workers.

### Usage
```bash
# Start the daemon
claude daemon start

# Check status
claude daemon status

# Stop the daemon
claude daemon stop

# Start the remote control server
bun run rcs
```

---

## 10. Pipe IPC (Multi-instance Collaboration)

**PR**: #241 `feat: restore pipe IPC, LAN pipes, monitor tool`
**Feature Flag**: `UDS_INBOX`

### Description
Multiple Claude Code instances on the same machine automatically discover and collaborate via UDS (Unix Domain Socket / Windows Named Pipe). The first instance to start becomes the `main`, and subsequent ones register as `sub`.

### Usage

**Starting multiple instances**:
```bash
# Terminal 1
bun run dev
# → Automatically becomes main

# Terminal 2
bun run dev
# → Automatically becomes sub-1, attached by main
```

**Managing instances**:
```
/pipes                — Display all instances; press Shift+↓ to expand the selection panel
/pipes select <name>  — Select an instance
/pipes all            — Select all instances
/pipes none           — Deselect all
/attach <name>        — Manually attach an instance
/detach <name>        — Disconnect
/send <name> <msg>    — Send a message to a specific instance
/claim-main           — Forcefully claim main status
/pipe-status          — Show detailed status
/peers                — List all discovered peers
```

**Selection Panel Operations**:
1. Press `Shift+↓` to expand the panel.
2. `↑/↓` to move the cursor.
3. `Space` to select/deselect a pipe.
4. `Enter` to confirm and close.
5. `←/→` to toggle routing modes (selected pipes ↔ local main).

**Message Broadcasting**:
Once a pipe is selected, input messages are automatically routed to all selected slaves for execution, with results streamed back to the main.

**Permission Forwarding**:
When a slave executes a tool requiring permission (e.g., `BashTool`), the request is automatically forwarded to the main instance's confirmation queue.

---

## 11. LAN Pipes (Local Area Network Group Control)

**PR**: #241 (as above)
**Feature Flag**: `LAN_PIPES`

### Description
Adds a TCP transport layer and UDP Multicast discovery on top of Pipe IPC for zero-configuration collaboration across different machines.

### Usage

**Multiple machines on the LAN**:
```bash
# Machine A (192.168.50.22)
bun run dev

# Machine B (192.168.50.27)
bun run dev

# Discovery and attachment happen automatically within 3-5 seconds
# /pipes will show remote instances marked as [LAN]
```

**Firewall Configuration** (Required on each machine):

Windows (Administrator PowerShell):
```powershell
New-NetFirewallRule -DisplayName "CCB LAN Beacon (UDP)" -Direction Inbound -Protocol UDP -LocalPort 7101 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "CCB LAN Pipes (TCP)" -Direction Inbound -Protocol TCP -LocalPort 1024-65535 -Program (Get-Command bun).Source -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "CCB LAN Beacon Out (UDP)" -Direction Outbound -Protocol UDP -RemotePort 7101 -Action Allow -Profile Private
```

macOS:
```bash
# Click "Allow" when the system prompt appears on first run
```

Linux:
```bash
sudo firewall-cmd --zone=trusted --add-port=7101/udp --permanent
sudo firewall-cmd --zone=trusted --add-port=1024-65535/tcp --permanent
sudo firewall-cmd --reload
```

**Notification Display Format**:
```
# Local sub
Routed to [sub-1]; main can continue other tasks

# LAN peer
Routed to [main] vmwin11/192.168.50.27; main can continue other tasks
```

---

## 12. Monitor (Background Monitoring)

**PR**: #241 (as above)
**Feature Flag**: `MONITOR_TOOL`

### Description
Runs shell commands in the background to continuously monitor output (similar to the `watch` command). The AI can also autonomously invoke the `MonitorTool`.

### Usage

**User Commands**:
```
/monitor tail -f /var/log/syslog
/monitor watch -n 5 docker ps
/monitor "while true; do curl -s localhost:3000/health; sleep 10; done"
```

**Viewing Monitors**:
- Press `Shift+Down` to expand the background task panel.
- View monitor output and status.

**Windows Compatibility**:
`watch -n <sec> <cmd>` is automatically converted into a PowerShell loop:
```powershell
while($true){ <cmd>; Start-Sleep -Seconds <sec> }
```

**AI Invocation**:
The AI can automatically invoke `MonitorTool` during a conversation to monitor logs, build output, etc.

---

## 13. Workflow Scripts

**PR**: #241 (as above)
**Feature Flag**: `WORKFLOW_SCRIPTS`

### Description
Executes user-defined workflow scripts in the `.claude/workflows/` directory.

### Usage

**Creating a Workflow**:
```bash
mkdir -p .claude/workflows
cat > .claude/workflows/deploy.sh << 'EOF'
#!/bin/bash
echo "Running tests..."
bun test
echo "Building..."
bun run build
echo "Deploying..."
EOF
chmod +x .claude/workflows/deploy.sh
```

**Listing Available Workflows**:
```
/workflows
```

**AI Invocation**:
The AI can automatically execute workflows via `WorkflowTool`:
```
Please execute the deploy workflow.
```

---

## 14. Coordinator Mode (Multi-worker Coordination)

**PR**: #241 (as above)
**Feature Flag**: `COORDINATOR_MODE`

### Description
When Coordinator Mode is enabled, the AI can automatically assign tasks to multiple workers for parallel execution.

### Usage
```
/coordinator       — Toggle Coordinator Mode on/off
```

When enabled, the AI will:
1. Analyze the task for parallelizable parts.
2. Automatically create worker branches.
3. Assign sub-tasks.
4. Consolidate results.

---

## 15. Proactive Mode

**PR**: #241 (as above)
**Feature Flag**: `PROACTIVE` / `KAIROS`

### Description
When enabled, the AI will proactively initiate actions (rather than just responding to user input), such as automatically detecting file changes or offering optimization suggestions.

### Usage
```
/proactive         — Toggle Proactive Mode on/off
```

---

## 16. History / Snip Management

**PR**: #241 (as above)
**Feature Flag**: `HISTORY_SNIP`

### Description
View and manage conversation history, with support for manual truncation to free up context window space.

### Usage
```
/history           — Show conversation history summary
/force-snip        — Force history truncation at the current position
```

The AI can also automatically truncate long conversations via `SnipTool`:
```
The conversation is too long; please help me truncate the history.
```

---

## 17. Fork Subagent

**PR**: #241 (as above)
**Feature Flag**: `FORK_SUBAGENT`

### Description
Forks an independent sub-agent within the current conversation context, inheriting the full session state for independent execution.

### Usage
```
/fork              — Fork a sub-agent based on the current context
```

The sub-agent will:
- Inherit all current conversation history.
- Run in an independent execution environment.
- Not affect the main session state.

---

## 18. Other Restored Tools

The following tools have been restored from stubs to full implementations:

| Tool | Description | Usage |
| :--- | :--- | :--- |
| `SleepTool` | Pauses execution for a specified duration. | Automatically invoked by AI in polling scenarios. |
| `WebBrowserTool` | In-terminal web interaction. | Invoked when AI needs to view web pages. |
| `SubscribePRTool` | Subscribe to GitHub PR changes. | `/subscribe-pr` or AI invocation. |
| `PushNotificationTool` | Push desktop notifications. | Invoked by AI upon completion of long tasks. |
| `CtxInspectTool` | Inspect context window usage. | Used by AI to determine remaining context space. |
| `TerminalCaptureTool` | Capture terminal screen. | Invoked when AI needs to see terminal output. |
| `SendUserFileTool` | Send a file to the user. | Invoked when AI exports files. |
| `REPLTool` | Start a sub-REPL session. | Invoked when AI needs an independent interactive environment. |
| `VerifyPlanExecutionTool` | Verify completion of an execution plan. | Automatically verifies after AI completes a plan. |
| `SuggestBackgroundPRTool` | Suggest creating a background PR. | Proposed by AI upon discovering independent changes. |
| `ListPeersTool` | List discovered peers. | Invoked when AI queries multi-instance status. |

---

## Appendix: All Feature Flags

| Flag | Default | Description |
| :--- | :--- | :--- |
| `BUDDY` | ✅ dev only | Companion system. |
| `BRIDGE_MODE` | ✅ dev only | Remote control. |
| `VOICE_MODE` | ✅ dev+build | Voice mode. |
| `CHICAGO_MCP` | ✅ dev+build | Computer Use + Chrome. |
| `AGENT_TRIGGERS_REMOTE` | ✅ dev+build | Scheduled tasks. |
| `SHOT_STATS` | ✅ dev+build | API statistics. |
| `TOKEN_BUDGET` | ✅ dev+build | Token budget. |
| `PROMPT_CACHE_BREAK_DETECTION` | ✅ dev+build | Cache detection. |
| `ULTRAPLAN` | ✅ dev+build | Advanced planning. |
| `DAEMON` | ✅ dev+build | Background daemon. |
| `UDS_INBOX` | ✅ dev only | Pipe IPC. |
| `LAN_PIPES` | ✅ dev only | LAN group control. |
| `MONITOR_TOOL` | ✅ dev+build | Background monitoring. |
| `WORKFLOW_SCRIPTS` | ✅ dev+build | Workflow scripts. |
| `FORK_SUBAGENT` | ✅ dev+build | Sub-agent. |
| `KAIROS` | ✅ dev+build | Kairos scheduling. |
| `COORDINATOR_MODE` | ✅ dev+build | Multi-worker. |
| `HISTORY_SNIP` | ✅ dev+build | History management. |
| `CONTEXT_COLLAPSE` | ✅ dev+build | Context collapsing. |
| `ULTRATHINK` | ✅ dev+build | Extended thinking. |
| `EXTRACT_MEMORIES` | ✅ dev+build | Auto memory extraction. |
| `VERIFICATION_AGENT` | ✅ dev+build | Verification Agent. |
| `KAIROS_BRIEF` | ✅ dev+build | Brief mode. |
| `AWAY_SUMMARY` | ✅ dev+build | Away summary. |
| `ACP` | ✅ dev+build | ACP protocol. |
| `LODESTONE` | ✅ dev+build | Deep linking. |
| `BUILTIN_EXPLORE_PLAN_AGENTS` | ✅ dev+build | Built-in Explore/Plan agents. |
| `AGENT_TRIGGERS` | ✅ dev+build | Local scheduled tasks. |
| `BG_SESSIONS` | ✅ dev only | Background sessions. |
| `TEMPLATES` | ✅ dev only | Template system. |
| `TRANSCRIPT_CLASSIFIER` | ✅ dev only | Conversation classification. |

Manually enable any flag:
```bash
FEATURE_FLAG_NAME=1 bun run dev
```

---

## Appendix: PR List

| PR | Date | Title |
| :--- | :--- | :--- |
| #60 | 2026-04-02 | feat: enable Remote Control (BRIDGE_MODE) |
| #82 | 2026-04-03 | refactor(buddy): align companion system |
| #88 | 2026-04-03 | feat: enable /schedule (AGENT_TRIGGERS_REMOTE) |
| #89 | 2026-04-03 | feat: built-in status line |
| #92 | 2026-04-03 | feat: enable /voice mode |
| #93 | 2026-04-03 | feat: enable Chrome MCP |
| #98 | 2026-04-03 | feat: enable Computer Use (macOS + Windows + Linux) |
| #137 | 2026-04-05 | feat: Computer Use v2 — Cross-platform Executor |
| #140 | 2026-04-05 | feat: enable SHOT_STATS, TOKEN_BUDGET |
| #153 | 2026-04-06 | feat: enable GrowthBook local gate defaults |
| #156 | 2026-04-06 | feat: enable /ultraplan |
| #170 | 2026-04-07 | feat: restore daemon supervisor |
| #241 | 2026-04-11 | feat: restore pipe IPC, LAN pipes, monitor tool |
