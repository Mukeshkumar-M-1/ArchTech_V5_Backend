#DEV-LOG 

## /poor saving mode (2026-04-11) 

Added `/poor` command, toggle off `extract_memories` and `prompt_suggestion`, save token. 

- Added `POOR` feature flag (build.ts + dev.ts) 
- `src/commands/poor/` — command definition + toggle implementation + status management 
- `src/query/stopHooks.ts` — skip extract_memories and prompt_suggestion when POOR mode is activated 

--- 

## Pipe IPC + LAN Pipes + Monitor Tool + Tool Recovery (2026-04-08 ~ 2026-04-11) 

**branch**: `feat/pr-package-adapt` 

### Background 

Restored a large number of stubs from decompiled code to complete implementation, and added LAN cross-machine communication capabilities. This PR covers: Pipe IPC system, LAN Pipes, Monitor Tool, 20+ tool/component replication, REPL hook architecture reconstruction. 

### Implementation 

#### 1. PipeServer TCP dual mode (`src/utils/pipeTransport.ts`) 

Expanded from the original pure UDS server to UDS + TCP dual mode: 

- Extract the `setupSocket()` shared method, the socket processing logic of UDS and TCP is exactly the same 
- `start(options?: PipeServerOptions)` added optional parameter `{ enableTcp, tcpPort }` 
- Maintain two `net.Server` (UDS + TCP) internally, sharing the same set of `clients: Set<Socket>` and `handlers` 
- TCP server binding `0.0.0.0` + dynamic port (port=0 assigned by OS) 
- `tcpAddress` getter exposes TCP port information 
- `close()` closes two servers at the same time 
- New types: `PipeTransportMode`, `TcpEndpoint`, `PipeServerOptions` 

PipeClient corresponding extension: 
- Added optional `TcpEndpoint` parameter to constructor 
- `connect()` dispatches to `connectTcp()` or `connectUds()` depending on whether there is a TCP endpoint 
- TCP connection does not require file existence polling, and the connection is established directly 

#### 2. LAN Beacon — UDP Multicast Discovery (`src/utils/lanBeacon.ts`, new file) 

Zero-configuration LAN peer discovery: 

- **Protocol**: UDP multicast group `224.0.71.67` ("CC" ASCII), port `7101`, TTL=1 
- **Announce package**: JSON `{ proto, pipeName, machineId, hostname, ip, tcpPort, role, ts }` 
- **Broadcast interval**: 3 seconds, first sent immediately after socket bind is completed 
- **Peer timeout**: No announce for 15 seconds is considered lost. 
- **Events**: `peer-discovered`, `peer-lost` 
- **Storage**: module-level singleton `getLanBeacon()`/`setLanBeacon()`, not hung on Zustand state 

Key fixes: 
- `addMembership(group, localIp)` + `setMulticastInterface(localIp)` specifies the LAN network card to solve the problem of WSL/Docker virtual network card hijacking multicast on Windows 
- The announce/cleanup timer is moved into the `bind()` callback to fix the race condition sent when the socket is not ready. 

#### 3. Registry extension (`src/utils/pipeRegistry.ts`) 

- `PipeRegistryEntry` added `tcpPort?` and `lanVisible?` fields 
- `mergeWithLanPeers(registry, lanPeers)` merges local registry and LAN beacon peers, local first 

#### 4. Peer Address extension (`src/utils/peerAddress.ts`) 

- `parseAddress()` added `tcp` scheme: `tcp:192.168.1.20:7100` 
- Added `parseTcpTarget()` to parse `host:port` string 

#### 5. REPL integration (`src/screens/REPL.tsx`) 

Three stages of changes: 

**Bootstrap**: `createPipeServer()` passes in TCP options according to `feature('LAN_PIPES')` → Start `LanBeacon` → Register entry carrying tcpPort 

**Heartbeat** (every 5 seconds): 
- `refreshDiscoveredPipes()` includes both local subs and LAN beacon peers to prevent LAN peer status from being overwritten 
- auto-attach loop uniformly traverses local subs + LAN peers, LAN peers are connected through TCP endpoint 
- cleanup checks the LAN beacon peers list to avoid accidentally deleting live LAN connections 
- The attach request carries `machineId`, and the receiver identifies the LAN peer (sub role is not required) 

**Cleanup**: Obtained through `getLanBeacon()` and cleared through `stop()`, `setLanBeacon(null)` 

#### 6. Command update 

- `/pipes` (`src/commands/pipes/pipes.ts`): Display remote instances of the `[LAN]` tag 
- `/attach` (`src/commands/attach/attach.ts`): Automatically find LAN beacon to obtain TCP endpoint 
- `SendMessageTool` (`src/tools/SendMessageTool/SendMessageTool.ts`): supports `tcp:` scheme, permission check requires user confirmation 

#### 7. Feature Flag 

`LAN_PIPES` — Enabled in the default features list of `scripts/dev.ts` and `build.ts`. All LAN code paths are gated via `feature('LAN_PIPES')`. 

#### 8. Pipe IPC basic system (`UDS_INBOX` feature) 

- `PipeServer`/`PipeClient`: UDS transport, NDJSON protocol (shared `ndjsonFramer.ts`) 
- `PipeRegistry`: role assignment bound to machineId (main/sub), file lock, parallel detection 
- Master/slave attach process, prompt forwarding, permission forwarding 
- Heartbeat life cycle (5s interval, stale entry cleaning, busy flag to prevent overlap) 
- Commands: `/pipes`, `/attach`, `/detach`, `/send`, `/claim-main`, `/pipe-status` 

#### 9. Monitor Tool（`MONITOR_TOOL` feature) 

- `MonitorTool`: AI callable background shell monitoring tool 
- `/monitor` command: user shortcut entry, Windows compatible (watch → PowerShell loop) 
- `MonitorMcpTask`: restore full life cycle from stub (register/complete/fail/kill) 
- `MonitorPermissionRequest`: React permission confirmation UI 
- `MonitorMcpDetailDialog`: Shift+Down details panel

#### 10. Tool recovery (stub → implementation) 

- SnipTool, SleepTool, ListPeersTool, SendUserFileTool 
- WebBrowserTool, SubscribePRTool, PushNotificationTool 
- CtxInspectTool, TerminalCaptureTool, WorkflowTool 
- REPLTool (.js → .ts), VerifyPlanExecutionTool (.js → .ts), SuggestBackgroundPRTool (.js → .ts) 
- Component .ts → .tsx rewrite: MonitorPermissionRequest, ReviewArtifactPermissionRequest, MonitorMcpDetailDialog, WorkflowDetailDialog, WorkflowPermissionRequest 

#### 11. REPL Hook architecture reconstruction 

Extract ~830 lines of Pipe IPC inline code from REPL.tsx into 4 independent hooks: 

| Hook | Number of lines | Responsibilities | 
|------|------|------| 
| `usePipeIpc` | 623 | Life cycle: bootstrap, handlers, heartbeat, cleanup | 
| `usePipeRelay` | 38 | slave→master message return (through `setPipeRelay` singleton) | 
| `usePipePermissionForward` | 159 | Permission request forwarding + streaming notification display | 
| `usePipeRouter` | 130 | selected pipe input route + role/IP label display | 

Shared Tools: `ndjsonFramer.ts` Replaces 3 duplicates of NDJSON parsing. 

#### 12. Feature Flags newly enabled 

UDS_INBOX, LAN_PIPES, MONITOR_TOOL, FORK_SUBAGENT, KAIROS, COORDINATOR_MODE, WORKFLOW_SCRIPTS, HISTORY_SNIP, CONTEXT_COLLAPSE 

### Trampling on pit records 

1. **Multicast is bound to the wrong network card**: When `addMembership(group)` does not specify a local interface on Windows, it is bound to the WSL/Docker virtual network card (`172.19.112.1`) by default, and real machines on the LAN cannot receive it. Must `addMembership(group, localIp)` + `setMulticastInterface(localIp)`. 

2. **Beacon ref lost**: Initially, `(store.getState() as any)._lanBeacon` is used to mount the beacon reference, but when Zustand `setState` expands `prev`, it does not contain the `_lanBeacon` attribute, and the next time it is read, it is `undefined`. Change to module-level singleton to solve the problem. 

3. **Heartbeat cleans LAN connections**: `refreshDiscoveredPipes()` completely overwrites `discoveredPipes` + `selectedPipes` with a list of only local registry subs every 5 seconds, and the discovery and selection status of the LAN peer is continuously cleared. Beacon peers must also be included in the refresh. 

4. **Heartbeat cleanup accidentally deleted**: `!aliveSubNames.has(slaveName)` causes the LAN peer (not in the local registry) to be judged as a dead connection and is cleared every 5 seconds. The list of beacon peers needs to be checked as well. 

5. **Cross-machine attach is rejected**: Each of the two machines is `main`, and the attach handler is hard-coded `role !== 'sub'` and is rejected. By carrying attach_request with `machineId`, the receiver can release requests with different machineIds. 

6. **`feature()` usage constraints**: Bun's `feature()` is a compile-time constant and can only be used directly in an `if` statement or a ternary condition. It cannot be assigned to a variable (such as `const x = feature('...')`), otherwise the build will report an error. 

### Known limitations 

- TCP without authentication: Any device in the same LAN can connect if it knows the port number 
- JSON.parse without schema verification: code review recommends adding Zod verification 
- Beacon clear text broadcast IP/hostname/machineId: subsequent hash processing is recommended 
- `getLocalIp()` may return VPN address: multi-network card environment requires more precise interface selection
### Test 

- `src/utils/__tests__/lanBeacon.test.ts`: 7 tests (mock dgram) 
- `src/utils/__tests__/peerAddress.test.ts`: 8 tests (pure functions) 
- Full capacity: 2190 pass / 0 fail 

### Firewall configuration 

**Windows** (Admin PowerShell): 
```powershell 
New-NetFirewallRule -DisplayName "Claude Code LAN Beacon (UDP)" -Direction Inbound -Protocol UDP -LocalPort 7101 -Action Allow -Profile Private 
New-NetFirewallRule -DisplayName "Claude Code LAN Pipes (TCP)" -Direction Inbound -Protocol TCP -LocalPort 1024-65535 -Program (Get-Command bun).Source -Action Allow -Profile Private 
New-NetFirewallRule -DisplayName "Claude Code LAN Beacon Out (UDP)" -Direction Outbound -Protocol UDP -RemotePort 7101 -Action Allow -Profile Private 
``` 

**macOS** (When running for the first time, the system will pop up the "Allow to accept incoming connections" dialog box, click Allow. Manually allow): 
```bash 
# If using pf ���firewall, add rules: 
echo "pass in proto udp from any to any port 7101" | sudo pfctl -ef - 
# Or connect to allow bun process in System Settings → Network → Firewall 
``` 

**Linux** (firewalld): 
```bash 
sudo firewall-cmd --zone=trusted --add-port=7101/udp --permanent 
sudo firewall-cmd --zone=trusted --add-port=1024-65535/tcp --permanent 
sudo firewall-cmd --reload 
``` 

**Linux** (iptables): 
```bash 
sudo iptables -A INPUT -p udp --dport 7101 -j ACCEPT 
sudo iptables -A INPUT -p tcp --dport 1024:65535 -m owner --uid-owner $(id -u) -j ACCEPT 
sudo iptables-save | sudo tee /etc/iptables/rules.v4 
``` 

**Universal Verification**: Confirm that the network is a LAN (not public WiFi) and AP isolation is not enabled on the router. 

---

## Daemon + Remote Control Server Restore (2026-04-07) 

**Branch**: `feat/daemon-remote-control-server` 

### Background 

`src/commands.ts` registers the `remoteControlServer` command (double gated `feature('DAEMON') && feature('BRIDGE_MODE')`), but the `src/commands/remoteControlServer/` directory is missing, `src/daemon/main.ts` and `src/daemon/workerRegistry.ts` All are stubs. The situation is consistent in the official CLI 2.1.92 - Anthropic has reserved the registration point and the underlying `runBridgeHeadless()` implementation, but the middle layer (daemon supervisor + command entry) has not been released. 

Restore the complete implementation through step-by-step reverse tracing of the call chain: 
``` 
/remote-control-server (slash command) 
→ spawn: claude daemon start 
→ daemonMain() (supervisor, manages worker life cycle) 
→ spawn: claude --daemon-worker=remoteControl 
→ runDaemonWorker('remoteControl') 
→ runBridgeHeadless(opts, signal) ← Already fully implemented 
→ runBridgeLoop() → accept remote session 
``` 
### Implementation 
#### 1. Worker Registry (`src/daemon/workerRegistry.ts`) 

Restore from stub to worker dispatcher: 
- `runDaemonWorker(kind)` is distributed to different worker implementations according to `kind` 
- `runRemoteControlWorker()` reads the configuration from the environment variable (`DAEMON_WORKER_*`), constructs `HeadlessBridgeOpts`, and calls `runBridgeHeadless()` 
- Distinguish between permanent (`EXIT_CODE_PERMANENT = 78`) and transient errors, based on which the supervisor decides to retry or park 
- SIGTERM/SIGINT signal processing, passed to bridge loop through `AbortController` 

#### 2. Daemon Supervisor (`src/daemon/main.ts`) 

Restore from stub to full supervisor process: 
- `daemonMain(args)` supports subcommands: `start` (start), `status`, `stop`, `--help` 
- `runSupervisor()` spawn `remoteControl` worker child process, passing configuration through environment variables 
- Exponential backoff restart (2s → 120s), if the park worker crashes 5 times in a row within 10s 
- permanent exit code (78) park directly without retrying 
- graceful shutdown: SIGTERM → forward to worker → 30s grace → SIGKILL 
- CLI parameter support: `--dir`, `--spawn-mode`, `--capacity`, `--permission-mode`, `--sandbox`, `--name` 

#### 3. Remote Control Server command (`src/commands/remoteControlServer/`) 

**`index.ts`** — Command registration: 
- type `local-jsx`, name `/remote-control-server`, alias `/rcs` 
- Double feature gating: `feature('DAEMON') && feature('BRIDGE_MODE')` + `isBridgeEnabled()` 
- lazy load `remoteControlServer.tsx` 

**`remoteControlServer.tsx`** — UI within REPL: 
- First call: pre-check (bridge availability + OAuth token) → spawn daemon child process 
- Call again: pop up the management dialog box (stop/restart/continue), display the PID and the last 5 lines of logs 
- Module-level state maintains daemon process references across calls 
- graceful stop: SIGTERM → 10s grace → SIGKILL 

#### 4. Feature Flag enabled 

`build.ts` / `scripts/dev.ts`: `DEFAULT_BUILD_FEATURES` / `DEFAULT_FEATURES` added `DAEMON` 

DAEMON only has compile-time feature flag gate control and no GrowthBook gate. 

### Differences from `/remote-control` 

| | `/remote-control` | `/remote-control-server` (daemon) | 
|---|---|---| 
| Mode | Single session, interactive bridge within REPL | Multi-session, daemon persistence server | 
| Life cycle | Bind to REPL session | Independent background process, automatically restart after crash | 
| Concurrency | 1 remote connection | Default 4, configurable `--capacity` | 
| Isolation | Share the current directory | Support `worktree` mode isolation | 
| Low-level | `initReplBridge()` | `runBridgeHeadless()` → `runBridgeLoop()` | 

### Modify files 

| Documentation | Changes | 
|------|------| 
| `build.ts` | `DEFAULT_BUILD_FEATURES` added `DAEMON` | 
| `scripts/dev.ts` | `DEFAULT_FEATURES` added `DAEMON` | 
| `src/daemon/main.ts` | Restore from stub to supervisor implementation | 
| `src/daemon/workerRegistry.ts` | Restore from stub to worker dispatcher | 
| `src/commands/remoteControlServer/index.ts` | **New** command registration | 
| `src/commands/remoteControlServer/remoteControlServer.tsx` | **NEW** REPL UI | 

### Verify 

| Project | Results | 
|------|------| 
| `bun run build` | ✅ Success (490 files) | 
| tsc new file check | ✅ No new type error | 

### How to use 

```bash 
# CLI starts daemon directly 
bun run dev daemon start 
bun run dev daemon start --spawn-mode=worktree --capacity=8 

# within the REPL 
/remote-control-server # or /rcs 
``` 

Prerequisite: Anthropic OAuth login (`claude login`) is required. 

---
## /ultraplan enabled + GrowthBook Fallback hardening + Away Summary improvements (2026-04-06) 

**branch**: `feat/ultraplan-enablement` 
**Commit**: `feat: enable /ultraplan and harden GrowthBook fallback chain` 

### Background 

`/ultraplan` is Claude Code's advanced multi-agent planning function: tasks are sent to Claude Code on the web (CCR), in-depth planning is performed by Opus, and after the plan is completed, it is returned to the terminal for user approval and execution. This feature is locked with 3-level gating: `feature('ULTRAPLAN')` compile flag + `isEnabled: () => USER_TYPE === 'ant'` + `INTERNAL_ONLY_COMMANDS` list. 

In addition, it was found that the GrowthBook fallback chain will throw an exception and skip `LOCAL_GATE_DEFAULTS` when the config is not initialized, and the Away Summary does not work on terminals (CMD/PowerShell) that do not support the DECSET 1004 focus event. 

### Implementation 

#### 1. Ultraplan enabled 

- `build.ts` / `scripts/dev.ts`: Add `ULTRAPLAN` to default build flag 
- `src/commands.ts`: Move ultraplan from `INTERNAL_ONLY_COMMANDS` into the public `COMMANDS` list 
- `src/commands/ultraplan.tsx`: `isEnabled` changed to `() => true` 
- `src/screens/REPL.tsx`: Add imports of `UltraplanChoiceDialog`, `UltraplanLaunchDialog`, and `launchUltraplan` (the HEAD version uses it but does not import it, and the build reports `not defined`) 

#### 2. Decompile UltraplanChoiceDialog / UltraplanLaunchDialog 

REPL.tsx references these two components but do not exist in the code base. Locate minified functions `M15` (UltraplanChoiceDialog) and `P15` (UltraplanLaunchDialog) from `cli.js` of the official CLI 2.1.92 and decompile into readable TSX through the symbol map. 

**`src/components/ultraplan/UltraplanChoiceDialog.tsx`** — Choice dialog after remote plan approval: 
- 3 options: Implement here (inject into current session)/Start new session (clear session and reopen)/Cancel (save to .md file) 
- Scrollable plan preview (ctrl+u/d to turn pages, mouse wheel), adaptive terminal height 
- Mark remote task completion after selection, clear `ultraplanPendingChoice` status, archive remote CCR session 

**`src/components/ultraplan/UltraplanLaunchDialog.tsx`** — Launch confirmation dialog: 
- Shows feature description, time estimate (~10–30 min), link to terms of service 
- Handle Remote Control bridge conflicts (automatically disconnect the bridge when run is selected) 
- Persist `hasSeenUltraplanTerms` to global configuration on first use 

Key points of decompilation: Strip React Compiler `_c(N)` cache array and restore to standard `useMemo`/`useCallback`; `useFocusedInputDialog()` registration hook is omitted (REPL internal calculation `focusedInputDialog`); GrowthBook configuration query is replaced with local default value. 

#### 3. GrowthBook Fallback reinforcement 

`src/services/analytics/growthbook.ts`: 
- `getFeatureValue_CACHED_MAY_BE_STALE`: Move `getLocalGateDefault()` lookup outside try/catch 
- `checkStatsigFeatureGate_CACHED_MAY_BE_STALE`: Same as above, config reading is wrapped in try/catch 

Before repair: config is not initialized → `getGlobalConfig()` throws an exception → catch returns `defaultValue` directly → skips `LOCAL_GATE_DEFAULTS` 
After repair: config is not initialized → catch silently → continue to check `LOCAL_GATE_DEFAULTS` → if there is a default value, use it, if not, fallback 

#### 4. Away Summary improvements (Windows terminal compatible) 

**Issue**: Away Summary (`feature('AWAY_SUMMARY')` + `tengu_sedge_lantern` gate, enabled in the previous round) relies on the DECSET 1004 terminal focus event to detect whether the user leaves. However, Windows CMD and PowerShell do not support this protocol. `getTerminalFocusState()` always returns `'unknown'`. The original logic performs no-op on the `'unknown'` state, resulting in Windows users never being able to trigger the leave summary. 

**Modification**: `src/hooks/useAwaySummary.ts` 

1. **focus status handling**: `'unknown'` is now regarded as `'blurred'` (may have left), and the idle timer (5 minutes) will be started when subscribing. 
2. **idle-based presence detection**: Added `isLoading` conversion listener as user activity signal instead of focus event: 
- The user initiates a new turn (`isLoading` → `true`) → indicates presence and cancels the ongoing generation of idle timer + abort 
- turn ends (`isLoading` → `false`) → restart idle timer 
- timer expires with no ongoing turn → triggers away summary generation 
3. **Compatibility**: The idle logic is only activated when `getTerminalFocusState() === 'unknown'`. Terminals that support DECSET 1004 (iTerm2, Windows Terminal, kitty, etc.) still follow the original blur/focus path 

**Effect**: After the Windows CMD/PowerShell user leaves the terminal for 5 minutes, the system automatically calls the API to generate a summary and appends it to the conversation flow as a system message of type `away_summary`. When the user comes back, he can see it directly in the UI without executing any command.
#### 5. Cron scheduled task management skills 

`src/skills/bundled/cronManage.ts` (**NEW**) + `src/skills/bundled/index.ts`: 

The KAIROS scheduled task system (`tengu_kairos_cron` gate, which was opened in the last round of GrowthBook activation) provides `ScheduleCronTool` to create scheduled tasks, but it lacks list/delete skills that users can call. Two new bundled skills are added to complete the management closed loop: 

| Skills | Usage | Functions | 
|------|------|------| 
| `/cron-list` | `/cron-list` | Call `CronListTool` to list all scheduled tasks, the table displays ID, Schedule, Prompt, Recurring, Durable | 
| `/cron-delete` | `/cron-delete <job-id>` | Call `CronDeleteTool` to cancel the specified scheduled task by ID | 

Both skills are gated by `isKairosCronEnabled()` (`feature('AGENT_TRIGGERS') && tengu_kairos_cron` gate), consistent with `ScheduleCronTool`. 

#### 6. Fullscreen gating repair 

- `src/utils/fullscreen.ts`: `isFullscreenEnvEnabled()` changes from unconditionally returning `true` to `process.env.USER_TYPE === 'ant'` to avoid non-ant users accidentally triggering full-screen mode 

### Modify files 

| Documentation | Changes | 
|------|------| 
| `build.ts` | `DEFAULT_BUILD_FEATURES` added `ULTRAPLAN` | 
| `scripts/dev.ts` | `DEFAULT_FEATURES` added `ULTRAPLAN` | 
| `src/commands.ts` | ultraplan moved to public command list | 
| `src/commands/ultraplan.tsx` | `isEnabled` removes ant-only restriction | 
| `src/components/ultraplan/UltraplanChoiceDialog.tsx` | **New** Decompiled from 2.1.92 | 
| `src/components/ultraplan/UltraplanLaunchDialog.tsx` | **New** Decompiled from 2.1.92 | 
| `src/screens/REPL.tsx` | Add 3 imports | 
| `src/services/analytics/growthbook.ts` | fallback chain reinforcement | 
| `src/hooks/useAwaySummary.ts` | idle-based away detection | 
| `src/skills/bundled/index.ts` | Register cron skills | 
| `src/skills/bundled/cronManage.ts` | **New** cron list/delete skills | 
| `src/utils/fullscreen.ts` | fullscreen gating repair | 

### Verify 

| Project | Results | 
|------|------| 
| `bun run build` | ✅ Success (480 files) | 
| `bun run lint` | ✅ biome-ignore warning only | 
| `/ultraplan` manual test | ✅ The command registration is visible, the remote session can be started, the callback plan can be received and the ChoiceDialog can be displayed | 

### Ultraplan Workflow 

``` 
/ultraplan <prompt> 
→ UltraplanLaunchDialog Confirm 
→ teleportToRemote creates a CCR remote session 
→ pollForApprovedExitPlanMode polling (3s interval, 30min timeout) 
→ ExitPlanModeScanner parses the event stream 
→ Plan approved → UltraplanChoiceDialog shows choices 
→ Implement here / Start new session / Cancel 
``` 

Requires Anthropic OAuth (`/login`). The remote session runs at claude.ai/code. 

--- 

## GrowthBook Local Gate Defaults + P0/P1 Feature Enablement (2026-04-06) 

**branch**: `feat/bookgrowth-enablement` 

### Background 

Claude Code uses GrowthBook (Anthropic's self-built proxy at api.anthropic.com) for remote function switch control, and the code is named with the `tengu_*` prefix. In the decompiled version, GrowthBook does not start (analytics empty implementation), resulting in 70+ functions being blocked by the gate. 

After in-depth analysis by 4 parallel research agents, it was confirmed that **all functional codes controlled by gates are truly implemented** (not stubs).
### Implementation plan 

**Commit 1** (`feat`): Add `LOCAL_GATE_DEFAULTS` mapping table (25+ boolean gates + 2 object config gates) in `growthbook.ts`, modify 4 getter functions to look for local default values when `isGrowthBookEnabled() === false`. 

**Commit 2** (`fix`): It was found that `LOCAL_GATE_DEFAULTS` is invalid in the user environment with API key - because `isGrowthBookEnabled()` returns `true` (analytics is not disabled), the code follows the GrowthBook path but the cache is empty, and returns `defaultValue` directly, skipping the local default value. Fix: Inserted `LOCAL_GATE_DEFAULTS` lookup in cache miss paths for 3 getter functions. Also fixes `tengu_onyx_plover` value type (`JSON.stringify` → direct object) and adds `tengu_kairos_brief_config` object type gate. 

Fixed fallback chain: 
``` 
env overrides → config overrides → [GrowthBook enabled?] 
→ Memory cache → Disk cache → LOCAL_GATE_DEFAULTS → defaultValue 
``` 

It can be disabled with one click through the `CLAUDE_CODE_DISABLE_LOCAL_GATES=1` environment variable. 

### Enabled features 

**P0 — Purely local functionality (7 gates):** 

| Gate | Function | 
|------|------| 
| `tengu_keybinding_customization_release` | Custom shortcut keys (~/.claude/keybindings.json) | 
| `tengu_streaming_tool_execution2` | Streaming tool execution (executing while collecting) | 
| `tengu_kairos_cron` | Scheduled task system | 
| `tengu_amber_json_tools` | Token efficient JSON tool format (save ~4.5%) | 
| `tengu_immediate_model_command` | Instantly switch models during operation | 
| `tengu_basalt_3kr` | MCP instruction incremental transmission | 
| `tengu_pebble_leaf_prune` | Session storage leaf pruning optimization | 

**P1 — API dependent functions (8 gates):** 

| Gate | Function | 
|------|------| 
| `tengu_session_memory` | Session memory (persistence across session contexts) | 
| `tengu_passport_quail` | Automatic memory retrieval | 
| `tengu_chomp_inflection` | Tips and suggestions | 
| `tengu_hive_evidence` | Verification agent (adversarial verification) | 
| `tengu_kairos_brief` | Brief simplified output mode | 
| `tengu_sedge_lantern` | Leave summary | 
| `tengu_onyx_plover` | Automatic dreaming (memory consolidation) | 
| `tengu_willow_mode` | Idle return prompt | 

**Kill Switch (10 gates remain true):** 

`tengu_turtle_carbon`, `tengu_amber_stoat`, `tengu_amber_flint`, `tengu_slim_subagent_claudemd`, `tengu_birch_trellis`, `tengu_c ollage_kaleidoscope`, `tengu_compact_cache_prefix`, `tengu_kairos_cron_durable`, `tengu_attribution_header`, `tengu_slate_prism` 

**New compilation flag:** 

| Flag | build.ts | dev.ts | Purpose | 
|------|:--------:|:------:|------| 
| `AGENT_TRIGGERS` | ON | ON | Scheduled task system | 
| `EXTRACT_MEMORIES` | ON | ON | Automatic memory retrieval | 
| `VERIFICATION_AGENT` | ON | ON | Adversarial Verification Agent | 
| `KAIROS_BRIEF` | ON | ON | Brief lite mode | 
| `AWAY_SUMMARY` | ON | ON | Leave summary | 
| `ULTRATHINK` | ON | ON | Ultrathink Extended Thinking (Double Gating Repair) | 
| `BUILTIN_EXPLORE_PLAN_AGENTS` | ON | ON | Built-in Explore/Plan agents (double gate repair) | 
| `LODESTONE` | ON | ON | Deep link protocol registration (double gating repair) | 

**Excluded compilation flags:** 
- `KAIROS` — pull in `useProactive.js` (missing file), `KAIROS_BRIEF` is sufficient 
- `TERMINAL_PANEL` — pull in `TerminalCaptureTool` (missing file) 

**Double Gating Repair Instructions:** 
Some functions are controlled by both the compilation flag and the GrowthBook gate (double gate control), and it is not enough to just open the GrowthBook gate. 
Audit found 3 stuck: `ULTRATHINK`, `BUILTIN_EXPLORE_PLAN_AGENTS`, `LODESTONE`. 

### Modify files 

| Documentation | Changes | 
|------|------| 
| `build.ts` | `DEFAULT_BUILD_FEATURES` added 8 new compilation flags | 
| `scripts/dev.ts` | `DEFAULT_FEATURES` added 8 new compilation flags | 
| `src/services/analytics/growthbook.ts` | Added `LOCAL_GATE_DEFAULTS` mapping (27 gates) + `getLocalGateDefault()` + Modified the fallback chain of 4 getters | 
| `scripts/verify-gates.ts` | Added gate verification script (30 gates) | 
| `docs/features/bookgrowth-enablement-plan.md` | Full research report and enablement plan | 
| `docs/features/feature-flags-audit-complete.md` | Update enabled status table | 

### Verify 

| Project | Results | 
|------|------| 
| `bun run build` | ✅ Success (481 files) | 
| `bun test` | ✅ 2106 pass / 23 fail (all existing problems) / 0 new addition failed | 
| `verify-gates.ts` | ✅ 30/30 PASS | 
| `/brief` Manual testing | ✅ Available (after fallback fix) | 

--- 

## Enable SHOT_STATS, TOKEN_BUDGET, PROMPT_CACHE_BREAK_DETECTION (2026-04-05) 

**PR**: [claude-code-best/claude-code#140](https://github.com/claude-code-best/claude-code/pull/140) 
**branch**: `feat/enable-safe-feature-flags` 

Actual source code verification (6 parallel sub-agents + Codex CLI independent review) was conducted on 22 compile-time feature flags marked "COMPLETE", and it was found that there were a large number of misjudgments in the audit report. It was finally confirmed that only 3 flags are truly compile-only and can be safely enabled. 

**Verification process:** 

1. 6 parallel subagents check each flag's `feature('FLAG_NAME')` reference point, dependent module integrity, and external service dependencies. 
2. Codex CLI (v0.118.0, 240K tokens) independently reviewed and further reduced the original 7 "compile-only" to 3 
3. 3 dedicated agents verify code path integrity and runtime security one by one 

**3 newly enabled flags:** 

| Flag | Function | User-perceptible effect | 
|------|------|---------------| 
| `SHOT_STATS` | shot distribution statistics | `/stats` panel displays shot distribution and one-shot rate | 
| `TOKEN_BUDGET` | token budget target | Supports `+500k` / `spend 2M tokens` syntax, automatically renews until target is reached, with progress bar | 
| `PROMPT_CACHE_BREAK_DETECTION` | cache key change detection | Internal diagnosis, visible in `--debug` mode, write diff to temporary directory | 

**Modify file:** 

| Documentation | Changes | 
|------|------| 
| `build.ts` | `DEFAULT_BUILD_FEATURES` added 3 flags | 
| `scripts/dev.ts` | `DEFAULT_FEATURES` added 3 flags | 
| `package.json` / `bun.lock` | Added `openai` dependency (required for OpenAI compatibility layer) | 

**New document:** 

| Documentation | Description | 
|------|------| 
| `docs/features/feature-flags-codex-review.md` | Codex independent review report: revised 5-category classification, recovery priorities, three-axis classification criteria recommendations | 
| `docs/features/feature-flags-audit-complete.md` | Mark all enabled flag states (`[build: ON]` / `[dev: ON]`) | 

**Codex review key findings:** 

- Among the original 22 "COMPLETE" flags, 8 core modules are stubs and 3 rely on remote services 
- `TEAMMEM`, `AGENT_TRIGGERS`, `EXTRACT_MEMORIES`, `KAIROS_BRIEF` were downgraded to "conditionally available" (gated by GrowthBook) 
- It is recommended that the audit classification standard be changed to three axes: implementation completeness × activation conditions × operational risk 
- Recovery priority: REACTIVE_COMPACT > BG_SESSIONS > PROACTIVE > CONTEXT_COLLAPSE 

**Verification result:** 

- `bun run build` → 475 files ✅ 
- `bun test` → Zero new addition failed ✅ 
- All 3 flag code paths are complete, no missing dependencies, no crash risk ✅ 

---
## /dream manual trigger + DreamTask type completion (2026-04-04) 

Decouple the `/dream` command from the KAIROS feature gate and unconditionally register it as a bundled skill; complete the DreamTask type stub. 

**New files:** 

| Documentation | Description | 
|------|------| 
| `src/skills/bundled/dream.ts` | `/dream` skill registration, call `buildConsolidationPrompt()` to generate consolidation prompt words | 

**Modify file:** 

| Documentation | Changes | 
|------|------| 
| `src/skills/bundled/index.ts` | Import and register `registerDreamSkill()` | 
| `src/components/tasks/src/tasks/DreamTask/DreamTask.ts` | `any` stub → re-export full type from `src/tasks/DreamTask/DreamTask.js` | 

**New document:** 

| Documentation | Description | 
|------|------| 
| `docs/features/auto-dream.md` | Complete description of Auto Dream principles, triggering mechanisms, and usage scenarios | 

--- 

## Computer Use macOS adaptation fix (2026-04-04) 

**Branch**: `feature/computer-use/mac-support` 

- **darwin.ts** — Application enumeration uses Spotlight `mdfind` + `mdls` to obtain the real bundleId (the old solution synthesizes `com.app.xxx`), covering `/Applications` + `/System/Applications` + CoreServices 
- **index.ts** — Added `hotkey` backend fallback, non-native modules will not crash 
- **toolCalls.ts** — `resolveRequestedApps()` added substring fuzzy matching (`"Chrome"` → `"Google Chrome"`) 
- **hostAdapter.ts** — `ensureOsPermissions()` checks `cu.tcc` existence, cross-platform JS backend safe downgrade 
- **Test**: 10 out of 17 MCP tools passed completely, 6 passed on full tier applications (IDE click tier is limited to expected behavior), `screenshot` did not return pictures (suspected screen recording permission issue) 

--- 

## Computer Use Windows enhancement: window binding screenshot + UI Automation + OCR (2026-04-03) 


Based on the basic implementation of the three platforms, Windows native APIs are used to enhance Computer Use’s Windows-specific capabilities. 

**New files:** 

| File | Number of lines | Description | 
|------|------|------| 
| `src/utils/computerUse/win32/windowCapture.ts` | — | `PrintWindow` window binding screenshot, supports blocked/background windows | 
| `src/utils/computerUse/win32/windowEnum.ts` | — | `EnumWindows` Exact window enumeration (HWND + PID + title) | 
| `src/utils/computerUse/win32/uiAutomation.ts` | — | `IUIAutomation` UI element tree reading, button click, text writing, coordinate recognition | 
| `src/utils/computerUse/win32/ocr.ts` | — | `Windows.Media.Ocr` screenshot + text recognition (English + Chinese) | 

**Modify file:** 

| Documentation | Changes | 
|------|------| 
| `packages/@ant/computer-use-swift/src/backends/win32.ts` | `listRunning` uses EnumWindows instead; new `captureWindowTarget` window-level screenshot | 

**Verification results (Windows x64):** 
- Window enumeration: 38 visible windows ✅ 
- Window screenshot: VS Code 2575x1415, 444KB ✅ (PrintWindow, even if it is blocked) 
- UI Automation: Coordinate element recognition ✅ 
- OCR: Recognize VS Code interface text, 34 lines ✅ 

---
## Enable Computer Use — macOS + Windows + Linux (2026-04-03) 

Restore Computer Use screen control functionality. The reference project is only for macOS, and this extension supports three platforms. 

**Phase 1 — MCP server stub replacement:** 
Copied `@ant/computer-use-mcp` full implementation (12 files, 6517 lines) from the reference project. 

**Phase 2 — Remove 8 macOS hardcoded locations in src/:** 

| Documentation | Changes | 
|------|------| 
| `src/main.tsx:1605` | Remove `getPlatform() === 'macos'` | 
| `src/utils/computerUse/swiftLoader.ts` | Remove darwin-only throw | 
| `src/utils/computerUse/executor.ts` | Platform guard extension is darwin+win32+linux; clipboard is distributed by platform (pbcopy→PowerShell→xclip); paste shortcut key command→ctrl | 
| `src/utils/computerUse/drainRunLoop.ts` | Direct execution of fn() without darwin | 
| `src/utils/computerUse/escHotkey.ts` | non-darwin returns false (Ctrl+C fallback) | 
| `src/utils/computerUse/hostAdapter.ts` | Non-darwin permission check returns granted | 
| `src/utils/computerUse/common.ts` | platform + screenshotFiltering dynamic | 
| `src/utils/computerUse/gates.ts` | enabled:true + hasRequiredSubscription→true | 

**Phase 3 — input/swift package dispatcher + backends three-platform architecture:** 

``` 
packages/@ant/computer-use-{input,swift}/src/ 
├── index.ts ← dispatcher 
├── types.ts ← Shared interface 
└── backends/ 
├── darwin.ts ← macOS AppleScript (removed as is, without changing the logic) 
├── win32.ts ← Windows PowerShell 
└── linux.ts ← Linux xdotool/scrot/xrandr/wmctrl 
``` 

**Compile switch:** `CHICAGO_MCP` added DEFAULT_FEATURES + DEFAULT_BUILD_FEATURES 

**Verification results (Windows x64):** 
- `isSupported: true` ✅ 
- Mouse positioning + front window information ✅ 
- Dual monitor detection 2560x1440 × 2 ✅ 
- Full screen screenshot 3MB base64 ✅ 
- `bun run build` 463 files ✅ 

--- 

## Enable Voice Mode / VOICE_MODE (2026-04-03) 

Restore `/voice` voice input function. All voice-related source codes under `src/` are consistent with the official ones (0 lines of difference). The problem lies in: ① The `VOICE_MODE` compilation switch is not turned on, and the command is not displayed; ② `audio-capture-napi` is a SoX sub-process stub (not supported by Windows) and lacks the official native `.node` binary. 

**New files:** 

| Documentation | Description | 
|------|------| 
| `vendor/audio-capture/{platform}/audio-capture.node` | Native audio binaries for 6 platforms (cpal, from reference project) | 
| `vendor/audio-capture-src/index.ts` | Native module loader (dynamic require `.node` according to `${arch}-${platform}`) | 

---

## Enable Claude in Chrome MCP (2026-04-03) 

Restore Chrome browser controls. All claudeInChrome related source codes under `src/` are consistent with the official ones (0 lines of difference). The problem lies in the `@ant/claude-for-chrome-mcp` package which is a 6-line stub (returns an empty tool list and null server). 

**Replacement file:** 

| Documentation | Changes | 
|------|------| 
| `packages/@ant/claude-for-chrome-mcp/src/index.ts` | 6 lines of stub → 15 lines of complete export | 

**New files:** 

| File | Number of lines | Description | 
|------|------|------| 
| `packages/@ant/claude-for-chrome-mcp/src/types.ts` | 134 | Type definition | 
| `packages/@ant/claude-for-chrome-mcp/src/browserTools.ts` | 546 | 17 browser tool definitions | 
| `packages/@ant/claude-for-chrome-mcp/src/mcpServer.ts` | 96 | MCP Server | 
| `packages/@ant/claude-for-chrome-mcp/src/mcpSocketClient.ts` | 493 | Unix Socket Client | 
| `packages/@ant/claude-for-chrome-mcp/src/mcpSocketPool.ts` | 327 | Multi-Profile connection pool | 
| `packages/@ant/claude-for-chrome-mcp/src/bridgeClient.ts` | 1126 | Bridge WebSocket Client | 
| `packages/@ant/claude-for-chrome-mcp/src/toolCalls.ts` | 301 | Tool call routing | 

**No feature flag is required, no changes to dev.ts/build.ts, and no changes to any files under src/. ** 

**Runtime dependencies:** Chrome browser + Claude in Chrome extension (https://claude.ai/chrome) 

--- 

## OpenAI interface compatible (2026-04-03) 

**Branch**: `feature/openai` 

Added the "OpenAI Compatible" option in the `/login` process to support Ollama, DeepSeek, vLLM, One API and other third-party services compatible with the OpenAI Chat Completions API. After the user configures it through `/login`, all API requests automatically go through the OpenAI path. 

**Changed files (10, +384 / -134):** 

| Documentation | Changes | 
|------|------| 
| `.github/workflows/ci.yml` | CI runner changed from `ubuntu-latest` to `macos-latest` | 
| `README.md` | Added "OpenAI interface compatible" entry to TODO list | 
| `src/components/ConsoleOAuthFlow.tsx` | Added `openai_chat_api` OAuth state (including Base URL / API Key / 3 model mapping fields); added "OpenAI Compatible" option to idle selection list; complete form UI (Tab switch, Enter to save); write `modelType: 'openai'` + env to settings.json when saving; OAuth reset when logging in `modelType` is `anthropic` | 
| `src/services/api/openai/index.ts` | Change from direct `yield* adaptOpenAIStreamToAnthropic()` to full stream processing loop: accumulate content blocks (text/tool_use/thinking), press `content_block_stop` to yield `AssistantMessage`, and yield `StreamEvent` for live display; error handling uses new signature `createAssistantAPIErrorMessage({ content, apiError, error })` | 
| `src/services/api/openai/convertMessages.ts` | Input type changed from Anthropic SDK `BetaMessageParam[]` to internal `(UserMessage \| AssistantMessage)[]`; determine role by `msg.type` instead of `msg.role`; read content from `msg.message.content`; skip `cache_edits` / `server_tool_use` and other internal block types | 
| `src/services/api/openai/modelMapping.ts` | Removed `OPENAI_MODEL_MAP` JSON environment variable + caching mechanism; added `getModelFamily()` classified by haiku/sonnet/opus; changed the parsing priority to: `OPENAI_MODEL` → `ANTHROPIC_DEFAULT_{FAMILY}_MODEL` → `DEFAULT_MODEL_MAP` → original name transparent transmission | 
| `src/services/api/openai/__tests__/convertMessages.test.ts` | Test input changed from bare `{ role, content }` to `makeUserMsg()` / `makeAssistantMsg()` wrapped internal format | 
| `src/services/api/openai/__tests__/modelMapping.test.ts` | Test changed from `OPENAI_MODEL_MAP` to `ANTHROPIC_DEFAULT_{HAIKU,SONNET,OPUS}_MODEL`; added 3 new env var override tests | 
| `src/utils/model/providers.ts` | `getAPIProvider()` adds the highest priority: judged from the `modelType` field in settings.json; the environment variable `CLAUDE_CODE_USE_OPENAI` is reduced to the second priority | 
| `src/utils/settings/types.ts` | `SettingsSchema` added `modelType` field: `z.enum(['anthropic', 'openai']).optional()` | 

**Key Design Decisions:** 

1. **`modelType` is stored in settings.json** — instead of a pure environment variable, making the `/login` configuration persistent and still effective after restarting 
2. **Reuse `ANTHROPIC_DEFAULT_*_MODEL` environment variables** — instead of adding `OPENAI_MODEL_MAP`, share the same set of model mapping configurations with Custom Platform to reduce user cognitive burden 
3. **Stream processing double yield** — simultaneously yield `AssistantMessage` (called to the consumer processing tool) and `StreamEvent` (given to REPL real-time rendering), aligned with Anthropic path behavior 
4. **OAuth login reset modelType** — Automatically reset to `anthropic` when the user switches back to the official Anthropic login to avoid residual configuration causing requests to take the wrong path 

**Configuration method:** 

``` 
/login → Select "OpenAI Compatible" → Fill in the Base URL / API Key / Model Name 
``` 

Or manually edit `~/.claude/settings.json`: 

```json 
{ 
"modelType": "openai", 
"env": { 
"OPENAI_BASE_URL": "http://localhost:11434/v1", 
"OPENAI_API_KEY": "ollama", 
"ANTHROPIC_DEFAULT_SONNET_MODEL": "qwen3:32b" 
} 
} 
``` 

---
## Enable Remote Control / BRIDGE_MODE (2026-04-03) 

**PR**: [claude-code-best/claude-code#60](https://github.com/claude-code-best/claude-code/pull/60) 

The Remote Control function registers the local CLI as a bridge environment and generates a shareable URL (`https://claude.ai/code/session_xxx`), allowing remote viewing of output, sending messages, and approving tool calls from a browser, mobile phone, or other device. 

**Change file:** 

| Documentation | Changes | 
|------|------| 
| `scripts/dev.ts` | `DEFAULT_FEATURES` added `"BRIDGE_MODE"`, dev mode is enabled by default | 
| `src/bridge/peerSessions.ts` | stub → Complete implementation: sending cross-session messages through the bridge API, including three layers of security protection (trim + validateBridgeId whitelist + encodeURIComponent) | 
| `src/bridge/webhookSanitizer.ts` | stub → Complete implementation: regular redact 8 class secret (GitHub/Anthropic/AWS/npm/Slack token), redact first and then truncate, return safe placeholder on failure | 
| `src/entrypoints/sdk/controlTypes.ts` | 12 `any` stubs → `z.infer<ReturnType<typeof XxxSchema>>` Deduces types from existing Zod schema | 
| `src/hooks/useReplBridge.tsx` | `tengu_bridge_system_init` default value `false` → `true`, so that the app displays "active" instead of stuck in "connecting" | 

**Key Design Decisions:** 

1. **Do not change the existing code logic** — only complete the stub, modify the default value, and turn on the compilation switch 
2. **`tengu_bridge_system_init`** — Anthropic pushes `true` to subscribers through GrowthBook, but our build cannot receive the push; changing the default value is the only solution that does not invade other code 
3. **`peerSessions.ts` authentication** — Use `getBridgeAccessToken()` to obtain OAuth Bearer token, consistent with `bridgeApi.ts`/`codeSessionApi.ts` authentication mode 
4. **`webhookSanitizer.ts` security** — fail-closed (returns `[webhook content redacted due to sanitization error]` on error), does not leak the original content 

**Verification result:** 

- `/remote-control` command is visible and available 
- CLI connects Anthropic CCR to generate shareable URL 
- The App (claude.ai/code) displays "Remote Control active" 
- The mobile phone (Claude iOS app) connects through URL, and two-way messages are normal 

![Remote Control on Mobile](docs/images/remote-control-mobile.png) 

--- 

## GrowthBook Custom Server Adapter (2026-04-03) 

The GrowthBook function switching system was originally designed for Anthropic's internal build, with hard-coded SDK keys and API addresses, and external builds are always disabled due to the `is1PEventLoggingEnabled()` gate. Added a new adapter mode to connect to the customized GrowthBook server through environment variables. If there is no configuration, all feature reads return code default values. 

**Modify file:** 

| Documentation | Changes | 
|------|------| 
| `src/constants/keys.ts` | `getGrowthBookClientKey()` reads the `CLAUDE_GB_ADAPTER_KEY` environment variable first | 
| `src/services/analytics/growthbook.ts` | `isGrowthBookEnabled()` returns `true` directly in adapter mode, bypassing 1P event logging gating | 
| `src/services/analytics/growthbook.ts` | `getGrowthBookClient()` base URL is preferred `CLAUDE_GB_ADAPTER_URL` | 
| `docs/internals/bookgrowth-adapter.mdx` | New adapter configuration document, including all ~58 feature key lists | 

**Usage:** `CLAUDE_GB_ADAPTER_URL=https://gb.example.com/ CLAUDE_GB_ADAPTER_KEY=sdk-xxx bun run dev` 

--- 

## Datadog log endpoint configurable (2026-04-03) 

Change Datadog's hard-coded Anthropic internal endpoints to environment variable drivers, which are disabled by default. 

**Modify file:** 

| Documentation | Changes | 
|------|------| 
| `src/services/analytics/datadog.ts` | `DATADOG_LOGS_ENDPOINT` and `DATADOG_CLIENT_TOKEN` changed from hard-coded constants to read `process.env.DATADOG_LOGS_ENDPOINT` / `process.env.DATADOG_API_KEY`, default empty string; `initializeDatadog()` adds guard: endpoint or Token Returns `false` directly when not configured | 
| `docs/telemetry-remote-config-audit.md` | Updated section 1 to reflect new way of configuring environment variables | 

**Effect:** By default, data is not sent to any external source; you can access your own Datadog instance by setting two environment variables. The original `DISABLE_TELEMETRY`, privacy level, sink killswitch and other defense lines are retained. 

**Usage:** `DATADOG_LOGS_ENDPOINT=https://http-intake.logs.datadoghq.com/api/v2/logs DATADOG_API_KEY=xxx bun run dev` 

--- 

## Sentry error reporting integration (2026-04-03) 

Restore Sentry integration that was removed during decompilation. Controlled through the `SENTRY_DSN` environment variable. When not set, all functions are no-op, which does not affect normal operation. 

**New files:** 

| Documentation | Description | 
|------|------| 
| `src/utils/sentry.ts` | Core modules: `initSentry()`, `captureException()`, `setTag()`, `setUser()`, `closeSentry()`; `beforeSend` filters sensitive information such as auth headers; ignores non-actionable errors such as ECONNREFUSED/AbortError | 

**Modify file:** 

| Documentation | Changes | 
|------|------| 
| `src/utils/errorLogSink.ts` | Call `captureException()` at the end of `logErrorImpl`, and all errors passed by `logError()` will be automatically reported | 
| `src/components/SentryErrorBoundary.ts` | Add `componentDidCatch`, React component rendering errors are reported to Sentry (including componentStack) | 
| `src/entrypoints/init.ts` | Call `initSentry()` after network configuration | 
| `src/utils/gracefulShutdown.ts` | flush Sentry event during graceful shutdown | 
| `src/screens/REPL.tsx:2809` | `fireCompanionObserver` call adds `typeof` protection, no error will be reported when BUDDY feature is enabled (TODO: to be implemented) | 
| `package.json` | devDependencies added `@sentry/node` | 

**Usage:** `SENTRY_DSN=https://xxx@xxx.ingest.sentry.io/xxx bun run dev` 

--- 

## Automatic updates are turned off by default (2026-04-03) 

Modify `src/utils/config.ts` — `getAutoUpdaterDisabledReason()` and insert the default shutdown logic before the original check logic. When `ENABLE_AUTOUPDATER=1` is not set, automatic updates always return `{ type: 'config' }` disabled. 

**Enable method:** `ENABLE_AUTOUPDATER=1 bun run dev` 

**Reason:** This project is a reverse engineering/decompiled version, and automatic updates will overwrite locally modified code. 

**New documents are also added:** `docs/auto-updater.md` — Complete audit of the automatic update mechanism, covering update strategies for three installation types, background polling, version gating, native installer architecture, file locks, configuration items, etc. 

---
## WebSearch Bing adapter completion (2026-04-03) 

The original `WebSearchTool` only supports Anthropic API server-side search (`web_search_20250305` server tool), and the search function is not available under unofficial API endpoints (third-party proxies). This change introduces the adapter architecture and adds Bing search page parsing as fallback. 

**New files:** 

| Documentation | Description | 
|------|------| 
| `src/tools/WebSearchTool/adapters/types.ts` | Adapter interface definition: `WebSearchAdapter`, `SearchResult`, `SearchOptions`, `SearchProgress` | 
| `src/tools/WebSearchTool/adapters/apiAdapter.ts` | API adapter - encapsulate the original `queryModelWithStreaming` logic into `ApiSearchAdapter` | 
| `src/tools/WebSearchTool/adapters/bingAdapter.ts` | Bing Adapter - directly capture Bing HTML and extract search results using regular expressions | 
| `src/tools/WebSearchTool/adapters/index.ts` | Adapter factory — select backend based on environment variables / API Base URL | 
| `src/tools/WebSearchTool/__tests__/bingAdapter.test.ts` | Bing adapter unit test (32 cases: decodeHtmlEntities, extractBingResults, search mock) | 
| `src/tools/WebSearchTool/__tests__/bingAdapter.integration.ts` | Bing Adapter Integration Test — Real Network Request Verification | 

**Refactored file:** 

| Documentation | Changes | 
|------|------| 
| `src/tools/WebSearchTool/WebSearchTool.ts` | Change from calling API directly to `createAdapter()` factory mode; `isEnabled()` always returns true; remove ~200 lines of inline API call logic | 
| `src/tools/WebFetchTool/utils.ts` | `skipWebFetchPreflight` default value changed from `!undefined` (i.e. true) to explicit `=== false`, making domain preflight enabled by default | 

**Bing Adapter Key Technical Details:** 

1. **Anti-crawling bypass**: Use the complete Edge browser request header (including 13 headers such as `Sec-Ch-Ua`, `Sec-Fetch-*`, etc.) to avoid Bing returning an empty page rendered by JS; the `setmkt=en-US` parameter forces the American English market to avoid regionalized results caused by IP geolocation (irrelevant content such as German forums, Singapore gold prices, etc.) 
2. **URL decoding** (`resolveBingUrl()`): The `u` parameter in the redirect URL returned by Bing (`bing.com/ck/a?...&u=a1aHR0cHM6Ly9...`) is the real URL encoded by base64, which needs to be decoded before use. 
3. **Summary extraction** (`extractSnippet()`): three-level downgrade strategy — `b_lineclamp` → `b_caption <p>` → `b_caption` direct text 
4. **HTML entity decoding** (`decodeHtmlEntities()`): handles 7 common HTML entities 
5. **Domain filtering**: Client side `allowedDomains` / `blockedDomains` filtering, supporting subdomain name matching 

**Current status**: `createAdapter()` in `adapters/index.ts` is hard-coded to return `BingSearchAdapter`, skipping the API/Bing automatic selection logic (the original logic is retained by comments). Automatic selection can be restored in the future by uncommenting. 

---
## Remove anti-distillation mechanism (2026-04-02) 

Three anti-distillation related codes were found in the project and all were removed. 

**Content removed:** 
- `src/services/api/claude.ts` — Remove fake_tools injection logic (original lines 302-314), which injects `anti_distillation: ['fake_tools']` in API requests via the `ANTI_DISTILLATION_CC` feature flag, allowing the server to mix fake tool calls into the response to pollute the distilled data 
- `src/utils/betas.ts` — Remove the connector-text summarization beta injection block and the `SUMMARIZE_CONNECTOR_TEXT_BETA_HEADER` import. This mechanism allows the server to buffer the assistant text between tool calls and summarize the return 
- `src/constants/betas.ts` — Remove `SUMMARIZE_CONNECTOR_TEXT_BETA_HEADER` constant definition (original lines 23-25) 
- `src/utils/streamlinedTransform.ts` — comment changed from "distillation-resistant" to "compact", streamlined mode itself is a valid output compression feature, only description fixed 

--- 

## Buddy command integration + Feature Flag specification revision (2026-04-02) 

Merge into `pr/smallflyingpig/36` branch (support buddy command + fix rehatch), and correct the usage of feature flag. 

**Incorporated content (from PR):** 
- `src/commands/buddy/buddy.ts` — Added `/buddy` command to support hatch / rehatch / pet / mute / unmute subcommands 
- `src/commands/buddy/index.ts` — changed from stub to correct `Command` type export 
- `src/buddy/companion.ts` — Added `generateSeed()`, `getCompanion()` to support seed-driven reproducible rolling 
- `src/buddy/types.ts` — `CompanionSoul` added `seed?` field 

**Post-merge corrections:** 
- `src/entrypoints/cli.tsx` — PR hardcoded `const feature = (name) => name === "BUDDY"`, which violates the feature flag specification and reverts to the standard `import { feature } from 'bun:bundle'` 
- `src/commands.ts` — PR uses static `import buddy` to bypass the feature gate and revert to `feature('BUDDY') ? require(...) : null` + conditional expansion 
- `src/commands/buddy/buddy.ts` — Remove unused `companionInfoText` function and redundant `Roll`/`SPECIES` import 
- `CLAUDE.md` — Rewrite the Feature Flag System chapter to clarify the specification: use `import { feature } from 'bun:bundle'` uniformly in the code, and enable the environment variable `FEATURE_<NAME>=1` 

**Usage:** `FEATURE_BUDDY=1 bun run dev` 

--- 

## Auto Mode completion (2026-04-02) 

The three prompt template files of the auto mode classifier were lost during decompilation. The code logic is complete but cannot be run. 

**New:** 
- `yolo-classifier-prompts/auto_mode_system_prompt.txt` — Main system prompt word 
- `yolo-classifier-prompts/permissions_external.txt` — External permissions template (user rules replace default values) 
- `yolo-classifier-prompts/permissions_anthropic.txt` — Internal permission template (user rules appended) 

**Changes:** 
- `scripts/dev.ts` + `build.ts` — Scan `FEATURE_*` environment variables to inject Bun `--feature` 
- `cli.tsx` — print enabled features on startup 
- `permissionSetup.ts` — `AUTO_MODE_ENABLED_DEFAULT` is determined by `feature('TRANSCRIPT_CLASSIFIER')`. Turning on feature will turn on auto mode 
- `docs/safety/auto-mode.mdx` — added prompt template chapter 

**Usage:** `FEATURE_TRANSCRIPT_CLASSIFIER=1 bun run dev` 

**Note:** The prompt template is a rebuilt product. 

---## USER_TYPE=ant TUI fix (2026-04-02) 

Global functions declared in `global.d.ts` are undefined when the decompiled version is run, causing the TUI to crash when `USER_TYPE=ant` is used. 

Repair method: explicit import / local stub / global stub / create a new stub file. Documents involved: 
`cli.tsx`, `model.ts`, `context.ts`, `effort.ts`, `thinking.ts`, `undercover.ts`, `Spinner.tsx`, `AntModelSwitchCallout.tsx`(new), `UndercoverAutoCallout.tsx`(new) 

Note: 
- `USER_TYPE=ant` enables alt-screen full screen mode, filling the center area with the entire screen is expected behavior 
- The remaining unstubbed global functions in `global.d.ts` (`getAntModels`, etc.) will be handled in the same way when encountering `X is not defined` 

--- 

## /login Add Custom Platform option (2026-04-03) 

A new "Custom Platform" option (located first) is added to the login method selection list of the `/login` command, allowing users to configure the Base URL, API Key and three model mappings of third-party API compatible services directly in the terminal, and save them to `~/.claude/settings.json`. 

**Modify file:** 

| Documentation | Changes | 
|------|------| 
| `src/components/ConsoleOAuthFlow.tsx` | `OAuthStatus` type adds `custom_platform` state (including `baseUrl`, `apiKey`, `haikuModel`, `sonnetModel`, `opusModel`, `activeField`); `idle` case Select option adds Custom Platform and ranks first; adds `custom_platform` case rendering 5 Field form (Tab/Shift+Tab switching, focus highlighting, Enter jump/save); Select onChange handles `custom_platform` initial state (prefill the current value from `process.env`); `OAuthStatusMessageProps` type and call location add `onDone` prop | 
| `src/components/ConsoleOAuthFlow.tsx` | Added `updateSettingsForSource` import | 

**UI Interaction:** 
- 5 fields on the same screen: Base URL, API Key, Haiku Model, Sonnet Model, Opus Model 
- The label of the currently active field is highlighted with `suggestion` background color + `inverseText` inverse color 
- Tab / Shift+Tab switches between fields, each retaining the entered value 
- Press Enter for each field to jump to the next, press Enter for the last field (Opus) to save 
- Model fields automatically read the current configuration from `process.env` as a pre-filled value, or empty if there is no value 
- Call `updateSettingsForSource('userSettings', { env })` when saving to write settings.json and update `process.env` at the same time 

**Saved settings.json env fields:** 
```json 
{ 
"ANTHROPIC_BASE_URL": "...", 
"ANTHROPIC_AUTH_TOKEN": "...", 
"ANTHROPIC_DEFAULT_HAIKU_MODEL": "...", 
"ANTHROPIC_DEFAULT_SONNET_MODEL": "...", 
"ANTHROPIC_DEFAULT_OPUS_MODEL": "..." 
} 
``` 

Only non-empty fields are written, and they take effect immediately after saving (`onDone()` triggers `onChangeAPIKey()` to refresh the API client).