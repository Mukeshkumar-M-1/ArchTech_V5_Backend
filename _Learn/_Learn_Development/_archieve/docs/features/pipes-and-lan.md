# Pipes + LAN Pipes — Complete Functional Guide

## Overview

The Pipes system provides communication capabilities between Claude Code CLI instances, divided into two layers:

1.  **Pipes (Local)**: Multiple CLI instances on the same machine collaborate via UDS (Unix Domain Socket / Windows Named Pipe).
2.  **LAN Pipes (Local Network)**: CLI instances on different machines collaborate via TCP + UDP Multicast.

Both layers utilize the same protocol (NDJSON) and the same commands (`/pipes`, `/attach`, `/send`, etc.), ensuring a transparent experience for the user.

## Feature Flags

| Flag | Control | Default |
| :--- | :--- | :--- |
| `UDS_INBOX` | All local Pipe IPC features. | Enabled in dev/build. |
| `LAN_PIPES` | Local network TCP + beacon extensions. | Enabled in dev/build. |

Manual enablement: `FEATURE_UDS_INBOX=1 FEATURE_LAN_PIPES=1 bun run dev`

## Quick Start

### Local Multi-Instance

```bash
# Terminal 1
bun run dev
# Automatically registered as 'main' upon startup.

# Terminal 2
bun run dev
# Automatically registered as 'sub-1' and attached by 'main'.
```

Type `/pipes` in Terminal 1 to see both instances. Once `sub-1` is selected, any input message will be automatically forwarded to `sub-1` for execution.

### Local Network Multi-Machine

```bash
# Machine A (192.168.50.22)
bun run dev

# Machine B (192.168.50.27)
bun run dev
```

Wait 3–5 seconds after startup (for the beacon broadcast interval). LAN peers will be automatically discovered and attached. Type `/pipes` to see remote instances labeled with `[LAN]`.

### Firewall Configuration (Required on both machines)

#### Windows (Administrator PowerShell)
```powershell
New-NetFirewallRule -DisplayName "Claude Code LAN Beacon (UDP)" -Direction Inbound -Protocol UDP -LocalPort 7101 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Claude Code LAN Pipes (TCP)" -Direction Inbound -Protocol TCP -LocalPort 1024-65535 -Program (Get-Command bun).Source -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "Claude Code LAN Beacon Out (UDP)" -Direction Outbound -Protocol UDP -RemotePort 7101 -Action Allow -Profile Private
# Verify network profile is "Private": Get-NetConnectionProfile
```

#### macOS (Allow the dialog prompt on first run)
```bash
# To manually allow traffic via pf:
echo "pass in proto udp from any to any port 7101" | sudo pfctl -ef -
```

#### Linux (firewalld / iptables)
```bash
# firewalld
sudo firewall-cmd --zone=trusted --add-port=7101/udp --permanent
sudo firewall-cmd --zone=trusted --add-port=1024-65535/tcp --permanent
sudo firewall-cmd --reload

# iptables
sudo iptables -A INPUT -p udp --dport 7101 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 1024:65535 -m owner --uid-owner $(id -u) -j ACCEPT
```

> [!NOTE]
> Ensure you are on a private LAN (not public WiFi) and that the router does not have "AP Isolation" enabled.

## Interaction Panel and Shortcuts

### Status Bar

After executing `/pipes`, a single-line pipe status bar appears at the bottom of the input field:

```
pipe: cli-a91bad56 (main) 192.168.50.22  2/3 selected  selected pipes only · ←/→ or m switch · Shift+↓ edit
```

This bar remains visible (until the session ends) and displays: current pipe name, role, IP, number selected/total, and the routing mode.

### Expanded Selection Panel

Press **Shift + Down Arrow** to expand the selection panel:

```
pipe: cli-a91bad56 (main) 192.168.50.22  ↑↓ move Space select ←/→ or m route Enter/Esc close Shift+↓ toggle
  Standard prompts follow the selected sub; switching will not clear selections.
  ☑ cli-da029538 (sub-1 XC/192.168.50.22)
  ☐ cli-04d67950 (main vmwin11/192.168.50.27)
  ☑ cli-893747d3 [offline] (sub-2 vmwin11/192.168.50.27)
```

### In-Panel Shortcuts

| Shortcut | Scenario | Action |
| :--- | :--- | :--- |
| **Shift + Down** | Status bar visible | Expand/Collapse selection panel. |
| **Up / Down** | Panel expanded | Move cursor up/down. |
| **Space** | Panel expanded | Toggle selection state of the highlighted pipe (☑ ↔ ☐). |
| **Enter** | Panel expanded | Confirm and close the panel. |
| **Esc** | Panel expanded | Cancel and close the panel. |
| **Left / Right / M**| Status bar visible & pipe selected | Toggle routing mode (`selected pipes only` ↔ `local main`). |

### The M Key — Routing Mode Toggle

The **M key** (or **Left/Right arrows**) toggles between the two routing modes **without needing to expand the panel**:

| Mode | Status Bar Display | Behavior |
| :--- | :--- | :--- |
| **selected pipes only** | Green Highlight | Input prompts are sent **only** to selected pipes; local execution is skipped. |
| **local main** | Gray | Input prompts are executed only on the **local main** instance; forwarding is skipped. |

Toggling the routing mode **does not clear your selection**. You can remain in `local main` mode with pipes selected and press **M** at any time to switch back to `selected pipes only` and resume remote forwarding.

### Example Operational Flow

```
1. Type /pipes                     → Status bar appears, showing discovered instances.
2. Press Shift + Down              → Selection panel expands.
3. Use Down Arrow to highlight     → Move cursor to 'cli-04d67950'.
4. Press Space                     → Select ☑ 'cli-04d67950'.
5. Press Enter                     → Confirm and collapse the panel.
6. Type "check git status"         → Prompt is automatically sent to 'cli-04d67950'.
7. Press M                         → Switch to 'local main' mode.
8. Type "do something locally"     → Prompt executes only locally.
9. Press M                         → Switch back to 'selected pipes only'.
10. Type "continue remote task"    → Prompt is sent back to 'cli-04d67950'.
```

## Command Reference

### `/pipes`
Displays all discovered instances and manages selection states. Executing `/pipes` again toggles the panel expansion.

```bash
/pipes                    — Display all instances + toggle selection panel.
/pipes select <name>      — Select an instance (messages will broadcast to it).
/pipes deselect <name>    — Deselect an instance.
/pipes all                — Select all discovered instances.
/pipes none               — Deselect all instances.
```

### `/attach <name>`
Manually attach to an instance, making it your slave.

```bash
/attach cli-04d67950      — Connect to a specific pipe (auto-resolves LAN TCP endpoints).
```
Upon attachment, the target becomes a `slave` and you become the `master`. You can then send prompts to it. Note that manual attachment is usually unnecessary as the heartbeat automatically discovers and connects to peers.

### `/detach <name>`
Disconnect from a slave instance.

```bash
/detach cli-04d67950
```

### `/send <name> <message>`
Send a message to a specific pipe (ignores selection state; targets the specified name directly).

```bash
/send cli-04d67950 "Check the logs please"
/send tcp:192.168.50.27:58853 hello    — Send directly to a TCP address.
```

### `/claim-main`
Forcefully declares the current machine as the `main` instance (useful for recovery if `main` crashes).

## Message Routing

### Automatic Routing for Selected Pipes
1. Select one or more pipes via `/pipes select` or the **Shift + Down** panel.
2. Type a message normally in the input box.
3. The message is automatically sent to all selected and connected pipes.
4. Each pipe executes independently, and results are streamed back to the main instance's message list.

### Routing Modes

| Mode | Behavior |
| :--- | :--- |
| **selected** (Default) | Messages are sent to selected pipes. |
| **local** | Messages are executed locally only; forwarding is skipped. |

## Architecture

### Communication Protocol
All communication uses NDJSON (Newline-Delimited JSON), with one message per line:

```json
{"type":"ping","from":"cli-abc","ts":"2026-04-11T00:00:00.000Z"}
{"type":"prompt","data":"check git status","from":"cli-abc","ts":"..."}
{"type":"stream","data":"Executing...","from":"cli-def","ts":"..."}
{"type":"done","data":"","from":"cli-def","ts":"..."}
```

### Message Types

| Type | Direction | Description |
| :--- | :--- | :--- |
| `ping`/`pong` | Bidirectional | Health checks. |
| `attach_request`/`accept`/`reject`| M→S / S→M | Connection control. |
| `detach` | M→S | Disconnect signal. |
| `prompt` | M→S | Master sending a prompt to a slave. |
| `prompt_ack` | S→M | Slave confirming receipt. |
| `stream` | S→M | Slave streaming AI output back to master. |
| `tool_start`/`tool_result` | S→M | Tool execution notifications. |
| `done` | S→M | Round completion. |
| `error` | Bidirectional | Error notifications. |
| `permission_request`/`response`/`cancel` | Bidirectional | Permission approval forwarding. |

### Transport Layer

```
                   Local                          LAN
            ┌──────────────┐            ┌──────────────┐
            │  PipeServer  │            │  PipeServer  │
            │   UDS sock   │            │   UDS sock   │
            │   TCP :rand  │◄───TCP───►│   TCP :rand  │
            ├──────────────┤            ├──────────────┤
            │  LanBeacon   │◄──UDP────►│  LanBeacon   │
            │  224.0.71.67 │  mcast     │  224.0.71.67 │
            └──────────────┘            └──────────────┘
```

- **UDS**: Communication between local instances, addressed via filesystem paths (`~/.claude/pipes/cli-xxx.sock`).
- **TCP**: Communication between LAN instances using dynamic ports discovered via beacons.
- **UDP Multicast**: Peer discovery; broadcasts an announcement packet every 3 seconds.

### Role Model

| Role | Description |
| :--- | :--- |
| **main** | The first instance started on a machine; manages the registry. |
| **sub** | Subsequent local instances (or attached LAN instances). |
| **master** | An instance that has attached at least one slave. |
| **slave** | An instance controlled by an attached master. |

**Role Transitions:**
- First startup → **main**.
- Subsequent local startups → **sub** (automatically attached by main → **slave**).
- LAN discovery → both sides remain **main**; heartbeat automatically attaches them to each other.
- Upon attachment → becomes a **slave** (can be restored via `/detach`).

### Discovery Mechanism

**Local**: Managed via the `~/.claude/pipes/registry.json` file (using file locking); `machineId` binds the host identity.

**LAN**: Managed via a UDP multicast beacon:
1. Broadcasts `{ proto, pipeName, machineId, ip, tcpPort, role }` every 3 seconds.
2. Other instances record these announcements in a peers Map.
3. A peer is marked as lost if no announcement is received for 15 seconds.
4. Heartbeat merges the local registry and beacon peers into a unified attachment target list.

### Heartbeat Loop (5-second intervals)

**main/master Role**:
1. `cleanupStaleEntries()`: Prunes dead entries from the registry.
2. `getAliveSubs()`: Retrieves active local sub-instances.
3. `refreshDiscoveredPipes()`: Refreshes discovered pipes (including LAN peers).
4. Merges LAN peers into state.
5. Constructs a unified attachment target list (local subs + LAN peers).
6. Iterates through unconnected targets and initiates automatic attachment.
7. Prunes disconnected slave connections by checking both the local registry and beacons.

**sub Role**:
1. Monitors `main` health.
2. If `main` dies: takes over the `main` role if on the same machine, or remains independent if on a different machine.

## Key Files

| File | Responsibility |
| :--- | :--- |
| `src/utils/pipeTransport.ts` | `PipeServer` (Dual-mode UDS+TCP), `PipeClient`, and type definitions. |
| `src/utils/lanBeacon.ts` | UDP multicast beacon and singleton management. |
| `src/utils/pipeRegistry.ts` | Registry CRUD, role determination, `machineId`, and LAN merging. |
| `src/utils/peerAddress.ts` | Address resolution (UDS/bridge/TCP schemes). |
| `src/screens/REPL.tsx` | Bootstrap, heartbeat, cleanup, and prompt routing. |
| `src/hooks/useMasterMonitor.ts` | Slave client registry and message subscription. |
| `src/hooks/useSlaveNotifications.ts` | Slave-side notification handling. |
| `src/commands/pipes/pipes.ts` | Implementation of the `/pipes` command. |
| `src/commands/attach/attach.ts`| Implementation of the `/attach` command. |
| `src/commands/send/send.ts` | Implementation of the `/send` command. |
| `packages/builtin-tools/src/tools/SendMessageTool/SendMessageTool.ts`| AI messaging tool (includes TCP support). |

## Future Optimizations

### Security (P0)
1. **TCP Authentication**: Exchange HMAC-SHA256 tokens (based on machine ID and session secret) upon initial connection to prevent unauthorized access.
2. **JSON Schema Validation**: Implement Zod validation at all `JSON.parse` entry points to prevent prototype pollution.
3. **Beacon Information Sanitization**: Hash `machineId` before broadcasting to avoid exposing hardware serial numbers.

### Reliability (P1)
4. **Multi-Interface Selection**: Update `getLocalIp()` to prioritize RFC 1918 addresses and exclude VPN/Docker interfaces.
5. **TCP Target Validation**: `parseTcpTarget()` should restrict targets to known beacon peers or RFC 1918 ranges.
6. **PipeServer close()**: Use `Promise.allSettled` to parallelize UDS and TCP shutdowns, guarded by a `_closing` flag.

### Functionality (P2)
7. **mDNS/DNS-SD**: Implement as a fallback beacon for multicast-restricted environments.
8. **Fixed Port Configuration**: Allow users to specify a TCP port range for easier firewall configuration.
9. **TLS Encryption**: Encrypt TCP transport to prevent man-in-the-middle eavesdropping.
10. **Bidirectional Prompts**: Allow slaves to actively send requests or results back to the master (currently only master → slave).
