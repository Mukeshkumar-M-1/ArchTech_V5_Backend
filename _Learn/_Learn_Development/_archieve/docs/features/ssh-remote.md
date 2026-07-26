# SSH Remote — Running Claude Code on a Remote Host

## Overview

SSH Remote provides two ways to run Claude Code on a remote Linux host:

1.  **SSH Remote Module** (`ccb ssh <host>`): Local REPL with remote tool execution, featuring automatic binary deployment and an authentication tunnel.
2.  **Direct SSH Execution** (`ssh <host> -t ccb`): Directly start an interactive session if Claude Code is already installed on the remote host.

## Architecture

### Method 1: SSH Remote Module (Full Mode)

**Use Case**: When the remote host lacks API credentials or does not have Claude Code installed.

```
┌──────────────── Local Windows/Mac/Linux ──────────┐
│                                                    │
│  ccb ssh <host> [dir]                              │
│     │                                              │
│     ├── 1. SSHProbe: Probe remote platform/arch/bin  │
│     ├── 2. SSHDeploy: Deploy dist/ to remote         │
│     ├── 3. SSHAuthProxy: Start local auth proxy      │
│     │      ├─ Unix Socket (Linux/Mac)              │
│     │      └─ TCP 127.0.0.1:<port> (Windows)       │
│     │                                              │
│     └── 4. SSH -R Reverse Tunnel + Start Remote CLI  │
│            ssh -R <remote>:<local> <host> \         │
│                ANTHROPIC_BASE_URL=... \             │
│                ANTHROPIC_AUTH_NONCE=... \            │
│                ccb --output-format stream-json      │
│                                                    │
│  ┌─────── Local REPL (Ink TUI) ───────┐             │
│  │ User Input → NDJSON → SSH stdin    │             │
│  │ SSH stdout → NDJSON → Render Msgs  │             │
│  │ Tool Permission → Local Approval   │             │
│  └────────────────────────────────────┘             │
└────────────────────────────────────────────────────┘
                        │
                        │ SSH Connection (Encrypted Channel)
                        │
┌───────────────── Remote Linux ────────────────────────┐
│                                                    │
│  ccb (Auto-deployed or pre-existing)                │
│     ├── --output-format stream-json                │
│     ├── --input-format stream-json                 │
│     ├── --verbose -p                               │
│     │                                              │
│     ├── API Request → ANTHROPIC_BASE_URL           │
│     │   → SSH Reverse Tunnel → Local AuthProxy      │
│     │   → Inject Credentials → api.anthropic.com    │
│     │                                              │
│     └── Tool Execution (Bash/Read/Write/...)        │
│         Operates directly on the remote filesystem   │
└────────────────────────────────────────────────────┘
```

### Method 2: Direct SSH Execution (Simple Mode)

**Use Case**: When the remote host has Claude Code installed and active API credentials (subscription or API Key).

```
┌─────── Local Terminal ───────┐          ┌──────── Remote Linux ────────┐
│                               │   SSH    │                             │
│  ssh <host> -t ccb            │ ──────→  │  ccb (Globally installed)    │
│                               │          │    ├── Uses remote creds    │
│  Terminal displays remote TUI │  ←────── │    ├── Remote file ops      │
│                               │   TTY    │    └── API direct to Ant    │
└───────────────────────────────┘          └─────────────────────────────┘
```

### Comparison

| Feature | SSH Remote Module | Direct SSH Execution |
| :--- | :--- | :--- |
| **Remote Install Required** | No (Auto-deployed) | Yes |
| **Remote API Creds Required**| No (Local tunnel) | Yes |
| **Local Install Required** | Yes | No (Any terminal) |
| **Slash Commands** | Handled locally | Handled remotely |
| **Network Latency** | High (NDJSON overhead) | Low (TTY only) |
| **Best Scenario** | Remote lacks creds/CCB | Remote is fully configured |

---

## Preparation: SSH Key Configuration

Both methods rely on passwordless SSH connections. Follow these steps to configure your keys.

### 1. Generate SSH Key Pair (Local)

```bash
# Generate Ed25519 key (Recommended)
ssh-keygen -t ed25519 -C "your-email@example.com" -f ~/.ssh/id_remote

# Or RSA 4096-bit
ssh-keygen -t rsa -b 4096 -C "your-email@example.com" -f ~/.ssh/id_remote
```

This generates two files:
- `~/.ssh/id_remote` — Private key (Keep this secure).
- `~/.ssh/id_remote.pub` — Public key (Deploy this to the remote host).

### 2. Deploy Public Key to Remote

```bash
# Method A: ssh-copy-id (Recommended)
ssh-copy-id -i ~/.ssh/id_remote.pub user@remote-host

# Method B: Manual Copy
cat ~/.ssh/id_remote.pub | ssh user@remote-host "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
```

### 3. Configure SSH Config (Local)

Edit `~/.ssh/config` (create it if it doesn't exist):

```
Host my-server
    HostName 192.168.1.100       # Remote IP or domain
    User root                     # Remote username
    IdentityFile ~/.ssh/id_remote # Path to private key
    ServerAliveInterval 60        # Prevent timeout disconnection
    ServerAliveCountMax 3
```

You can now connect using the alias:

```bash
ssh my-server          # Equivalent to ssh -i ~/.ssh/id_remote root@192.168.1.100
```

### 4. File Permission Settings

#### Linux / macOS
```bash
chmod 700 ~/.ssh
chmod 600 ~/.ssh/config
chmod 600 ~/.ssh/id_remote
chmod 644 ~/.ssh/id_remote.pub
```

#### Windows (OpenSSH Mandatory ACL Check)
```powershell
# Reset .ssh directory permissions: Only current user + SYSTEM
icacls "$env:USERPROFILE\.ssh" /inheritance:r /grant:r "$($env:USERNAME):(OI)(CI)F" /grant "SYSTEM:(OI)(CI)F"

# Fix config file permissions
icacls "$env:USERPROFILE\.ssh\config" /inheritance:r /grant:r "$($env:USERNAME):F" /grant "SYSTEM:F"

# Fix private key permissions
icacls "$env:USERPROFILE\.ssh\id_remote" /inheritance:r /grant:r "$($env:USERNAME):F" /grant "SYSTEM:F"
```

> [!WARNING]
> If `icacls` displays `UNKNOWN\UNKNOWN` ACL entries, remove them before re-authorizing. Permission errors will cause SSH to reject the key.

### 5. Verify Passwordless Connection

```bash
ssh my-server "echo 'SSH connection OK'"
# Should output "SSH connection OK" without asking for a password.
```

---

## Usage

### Method 1: SSH Remote Module

```bash
# Basic usage: Auto-probe, deploy, and start
ccb ssh user@remote-host

# Using SSH Config alias
ccb ssh my-server

# Specify remote working directory
ccb ssh my-server /home/user/project

# Use custom remote binary (skips probe/deploy)
ccb ssh my-server --remote-bin "bun /opt/ccb/dist/cli.js"

# Permission control
ccb ssh my-server --permission-mode auto
ccb ssh my-server --dangerously-skip-permissions

# Resume remote session
ccb ssh my-server --continue
ccb ssh my-server --resume <session-uuid>

# Select model
ccb ssh my-server --model claude-sonnet-4-6-20250514

# Local test mode (Test auth proxy pipeline without remote connection)
ccb ssh localhost --local
```

### Method 2: Direct SSH Execution

```bash
# Start interactive session
ssh my-server -t ccb

# Specify working directory
ssh my-server -t "ccb --cwd /home/user/project"

# Use specific model
ssh my-server -t "ccb --model claude-sonnet-4-6-20250514"
```

---

## Build and Deployment

### Build Artifacts

```bash
# Install dependencies
bun install

# Build (Output to dist/)
bun run build
```

| File | Description |
| :--- | :--- |
| `dist/cli.js` | Bun entry point (`#!/usr/bin/env bun`). |
| `dist/cli-node.js` | Node.js entry point (`#!/usr/bin/env node` → imports `cli.js`). |
| `dist/cli-bun.js` | Bun-specific entry point. |
| `dist/chunk-*.js` | Code-split chunk files (~668 files). |

### Execution Methods

- **Option A**: Run directly via Bun (Dev/Debug) -> `bun run dev`.
- **Option B**: Run build output via Bun runtime -> `bun dist/cli.js`.
- **Option C**: Run build output via Node runtime -> `node dist/cli-node.js`.
- **Option D**: Use global command name after installation -> `ccb`.

### Global Installation

Execute in the project root:

```bash
# Bun global install (Recommended)
bun install -g .

# Commands created:
#   ccb            → dist/cli-node.js
#   ccb-bun        → dist/cli-bun.js
#   claude-code-best → dist/cli-node.js

# Location: ~/.bun/bin/ccb
```

Alternatively, use npm: `npm install -g .`

Verify: `ccb --version`

### Remote Deployment (Full Walkthrough)

1.  Log in to remote: `ssh my-server`.
2.  Clone or sync project: `git clone <repo-url> ~/ccb-project && cd ~/ccb-project`.
3.  Install runtime (if Bun is missing): `curl -fsSL https://bun.sh/install | bash && source ~/.bashrc`.
4.  Install dependencies and build: `bun install && bun run build`.
5.  Global install: `bun install -g .`.
6.  **Fix PATH for non-interactive SSH**: `bun install -g` installs to `~/.bun/bin/`, which isn't loaded by non-interactive SSH.
    - **Fix (Recommended)**: Create symbolic link -> `ln -sf ~/.bun/bin/ccb /usr/local/bin/ccb`.
7.  Verify: `ccb --version`.
8.  Test from local terminal: `ssh my-server -t ccb`.

### SSH Remote Auto-Deployment

When using `ccb ssh <host>`, the module automatically handles:
1.  **SSHProbe**: Checks for `~/.local/bin/claude` or `command -v claude`.
2.  **SSHDeploy**: Transfers the `dist/` directory via `scp` if the binary is missing or mismatched.
3.  Creates a wrapper script (`~/.local/bin/claude`) on the remote host.

---

## Module Structure

```
src/ssh/
├── createSSHSession.ts     — Session factory: Orchestrates probe → deploy → proxy → spawn.
├── SSHSessionManager.ts    — Bidirectional NDJSON communication, permission forwarding, and reconnection.
├── SSHAuthProxy.ts         — Local authentication proxy (API credential tunnel).
├── SSHProbe.ts             — Remote host probing (platform/arch/binaries).
├── SSHDeploy.ts            — Remote binary deployment (scp + wrapper script).
└── __tests__/
    └── SSHSessionManager.test.ts  — 17 unit tests.
```

## Key Technical Details

### Authentication Tunneling
- **AuthProxy** listens locally (Unix socket or TCP) and receives API requests from the remote CLI.
- Traffic is tunneled back to the local machine via SSH reverse port forwarding (`-R`).
- AuthProxy injects local credentials (API key or OAuth token) and forwards them to `api.anthropic.com`.
- The `ANTHROPIC_AUTH_NONCE` header prevents unauthorized access; the nonce is passed to the remote CLI via environment variables and included in every request.

### `waitForInit` vs. Survival Checks
- **Standard Mode**: `waitForInit` waits for the `{type:'system', subtype:'init'}` NDJSON message from the remote CLI.
- **`--remote-bin` Mode**: Skips `waitForInit` (as `init` only sends after the first query in `print+stream-json` mode), using a 3-second process survival check instead.

### Reconnection Mechanism
- `SSHSessionManager` automatically reconnects if the SSH connection is lost.
- Resumes the session by appending `--continue` to the remote command.
- Implements exponential backoff: up to 5 attempts (1s → 2s → 4s → 8s → 16s).

## Feature Flag

Controlled by `SSH_REMOTE`:
- **Dev Mode**: Enabled by default.
- **Build Mode**: Add `'SSH_REMOTE'` to `DEFAULT_BUILD_FEATURES` in `build.ts`.
- **Runtime**: `FEATURE_SSH_REMOTE=1`.

---

## FAQ

### `ccb: command not found` (on remote)
Non-interactive SSH does not load `.bashrc`, so `~/.bun/bin` is not in the PATH.
- **Fix**: `ln -sf ~/.bun/bin/ccb /usr/local/bin/ccb`.

### SSH Publickey Denied
- Ensure the public key is in `~/.ssh/authorized_keys` on the remote.
- Verify local private key permissions (`chmod 600`).
- Check the `IdentityFile` path in `~/.ssh/config`.

### SSH Connection Timeout
- Ensure `sshd` is running on the remote: `systemctl status sshd`.
- Verify the firewall allows port 22.
- Add `ConnectTimeout 10` to `~/.ssh/config`.

### 403 Forbidden (SSH Remote Module)
Nonce verification failed in AuthProxy.
- Ensure the remote CLI version includes the nonce header injection fix.
- Verify `ANTHROPIC_AUTH_NONCE` is correctly passed to the remote.

### Remote CLI Exits Immediately
- Confirm `bun` or `node` runtime is available on the remote.
- Manually run `ccb --version` on the remote to verify installation.
- Check if the `--remote-bin` path is correct.
