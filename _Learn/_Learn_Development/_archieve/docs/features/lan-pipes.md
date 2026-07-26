# LAN Pipes — Local Network Multi-Machine Control Guide

## What is LAN Pipes?

LAN Pipes allows Claude Code instances on multiple machines to automatically discover and collaborate via a local area network (LAN). You can control Claude Code on other machines (subs) from a single machine (main)—sending prompts, viewing execution results, and approving permission requests—all with zero configuration.

This feature extends the local Pipe IPC (`UDS_INBOX`) by adding a TCP transport layer and UDP multicast discovery.

## Prerequisites

- Two or more machines on the same local network.
- Claude Code installed on each machine and able to run via `bun run dev`.
- Feature flag `LAN_PIPES` enabled (on by default for dev/build).
- Firewalls configured to allow UDP 7101 and dynamic TCP ports (see configuration below).

## Quick Start

### Step 1: Configure Firewall

**This must be performed on every machine.**

#### Windows (Administrator PowerShell)
```powershell
New-NetFirewallRule -DisplayName "CCB LAN Beacon (UDP)" -Direction Inbound -Protocol UDP -LocalPort 7101 -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "CCB LAN Pipes (TCP)" -Direction Inbound -Protocol TCP -LocalPort 1024-65535 -Program (Get-Command bun).Source -Action Allow -Profile Private
New-NetFirewallRule -DisplayName "CCB LAN Beacon Out (UDP)" -Direction Outbound -Protocol UDP -RemotePort 7101 -Action Allow -Profile Private
```
Verify that the network profile is "Private" (not Public) using `Get-NetConnectionProfile`.

#### macOS
The first time you run the application, a dialog box will appear asking to "Allow incoming connections." Click **Allow**.

If using the `pf` firewall:
```bash
echo "pass in proto udp from any to any port 7101" | sudo pfctl -ef -
```

#### Linux (firewalld)
```bash
sudo firewall-cmd --zone=trusted --add-port=7101/udp --permanent
sudo firewall-cmd --zone=trusted --add-port=1024-65535/tcp --permanent
sudo firewall-cmd --reload
```

#### Linux (iptables)
```bash
sudo iptables -A INPUT -p udp --dport 7101 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 1024:65535 -m owner --uid-owner $(id -u) -j ACCEPT
```

### Step 2: Start Up

```bash
# Machine A (e.g., 192.168.50.22)
bun run dev

# Machine B (e.g., 192.168.50.27)
bun run dev
```

Wait 3–5 seconds after startup (for the beacon broadcast interval). Both sides will automatically discover and connect to each other.

### Step 3: View and Operate

On any machine, run:
```bash
/pipes
```

Example Output:
```
pipe: cli-a91bad56 (main) 192.168.50.22  2/3 selected

Main machine: 205d6c3a... (this machine)
  [main] cli-a91bad56  XC/192.168.50.22  [alive] (you)
  ☑ [sub-1] cli-da029538  XC/192.168.50.22  [alive] [connected]

LAN Peers:
  ☐ [main] cli-04d67950  vmwin11/192.168.50.27  tcp:192.168.50.27:58853  [LAN]
```

### Step 4: Select Target and Send Task

1. Press `Shift + Down` to expand the selection panel.
2. Use `Up/Down` to move to a LAN peer.
3. Press `Space` to select the peer.
4. Press `Enter` to confirm.
5. Enter a prompt; it will be automatically routed to the remote machine for execution.

Remote execution results will be streamed back to your message list:
```
[main vmwin11/192.168.50.27 / cli-04d67950] checking git status...
[main vmwin11/192.168.50.27 / cli-04d67950] Completed
```

## Command Reference

| Command | Description |
| :--- | :--- |
| `/pipes` | Display all instances (local + LAN); `Shift + Down` to expand selection panel. |
| `/pipes select <name>` | Select a specific instance. |
| `/pipes all` | Select all instances. |
| `/pipes none` | Deselect all instances. |
| `/attach <name>` | Manually attach (automatically identifies LAN peers and connects via TCP). |
| `/detach <name>` | Disconnect from an instance. |
| `/send <name> <msg>` | Send a message to a specific pipe. |
| `/send tcp:host:port <msg>`| Send a message directly via TCP address. |
| `/claim-main` | Forcefully declare the current instance as `main`. |
| `/pipe-status` | Display detailed status information. |
| `/peers` | List all discovered peers. |

## Keyboard Shortcuts

| Shortcut | Scenario | Action |
| :--- | :--- | :--- |
| `Shift + Down` | Status bar visible | Expand/Collapse selection panel. |
| `Up / Down` | Panel expanded | Move cursor. |
| `Space` | Panel expanded | Select/Deselect instance. |
| `Enter` | Panel expanded | Confirm and close. |
| `Esc` | Panel expanded | Cancel and close. |
| `Left / Right` | Pipe(s) selected | Toggle routing mode. |
| `M` | Panel expanded | Toggle routing mode (same as Left/Right). |

## Routing Modes

| Mode | Indicator | Behavior |
| :--- | :--- | :--- |
| **Selected pipes only**| Green | Prompt sent only to selected pipes; local execution is skipped. |
| **Local main** | Gray | Prompt executed only locally; forwarding is skipped. |

Toggling routing modes does not clear your selections.

## Permission Forwarding

When a remote slave executes a tool requiring permission (e.g., `BashTool`):
1. The slave sends a `permission_request` to the main instance.
2. The main instance displays a confirmation dialog showing `[role hostname/ip / pipeName]`.
3. The user confirms or rejects the request.
4. The result is sent back to the slave to continue or abort.

## How It Works

### Discovery Mechanism
- Each machine creates a UDP multicast beacon upon startup.
- **Group Address**: `224.0.71.67`, **Port**: `7101`, **TTL**: `1` (does not cross routers).
- Broadcasts its information (pipe name, IP, TCP port, role) every 3 seconds.
- Peers are marked as lost if no broadcast is received for 15 seconds.

### Communication Mechanism
- **Local Instances**: UDS (Unix Domain Socket / Named Pipe).
- **Cross-Machine**: TCP (dynamic ports discovered via beacon).
- **Protocol**: NDJSON (one JSON object per line).
- **Message Types**: `ping`/`pong`, `attach`/`detach`, `prompt`/`stream`/`done`/`error`, and `permission`.

### Role Model

| Role | Description |
| :--- | :--- |
| **main** | The first instance started on a machine. |
| **sub** | Subsequent instances started on the same machine. |
| **master** | An instance that has attached at least one slave. |
| **slave** | An instance that has been attached by a master. |

In cross-machine attachment, both sides can be in the `main` role—it is not required for the target to be a `sub`.

## Troubleshooting

### Cannot See LAN Peers
1. Ensure the firewall allows UDP traffic on port 7101.
2. Verify that the network profile is set to "Private" (on Windows, use `Get-NetConnectionProfile`).
3. Confirm that both machines are on the same subnet (use `ping` to test).
4. Ensure the router does not have "AP Isolation" enabled.

### Connection Timeout
1. Check inbound TCP firewall rules.
2. Ensure no VPN is hijacking traffic.
3. Use `/send tcp:ip:port hello` to test connectivity directly.

### Beacon Bound to Wrong Interface
On Windows, WSL or Docker virtual adapters might hijack multicast traffic. The beacon automatically selects non-internal IPv4 interfaces. If it selects the wrong one, check the value returned by `getLocalIp()`.

## Security Notes

- TCP connections currently **do not use authentication**—anyone on the LAN who knows the port can connect.
- Multicast TTL is set to 1, meaning it does not cross routers.
- AI sending `tcp:` messages via `SendMessageTool` requires **explicit user confirmation**.
- It is recommended to use LAN Pipes only on trusted local networks.
