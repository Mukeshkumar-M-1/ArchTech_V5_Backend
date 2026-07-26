# LAN Pipes — Technical Implementation Documentation

Implementation details for developers. For the user guide, see [lan-pipes.md](./lan-pipes.md).

---

## Architecture

```
Machine A (192.168.50.22)                Machine B (192.168.50.27)
┌───────────────────────────┐           ┌───────────────────────────┐
│ PipeServer                │           │ PipeServer                │
│   UDS: ~/.claude/pipes/   │           │   UDS: ~/.claude/pipes/   │
│       cli-abc.sock        │           │       cli-def.sock        │
│   TCP: 0.0.0.0:<random>  │◄──TCP───►│   TCP: 0.0.0.0:<random>  │
├───────────────────────────┤           ├───────────────────────────┤
│ LanBeacon                 │           │ LanBeacon                 │
│   UDP 224.0.71.67:7101    │◄──UDP───►│   UDP 224.0.71.67:7101    │
├───────────────────────────┤           ├───────────────────────────┤
│ usePipeIpc (hook)         │           │ usePipeIpc (hook)         │
│   initPipeServer          │           │   initPipeServer          │
│   registerMessageHandlers │           │   registerMessageHandlers │
│   runMainHeartbeat        │           │   runSubHeartbeat         │
│   cleanupPipeIpc          │           │   cleanupPipeIpc          │
└───────────────────────────┘           └───────────────────────────┘
```

## Feature Flag

`LAN_PIPES` — Enabled within `DEFAULT_FEATURES` in `scripts/dev.ts` and `build.ts`.

All LAN code paths are gated via `feature('LAN_PIPES')` at compile time. Note that `feature()` can only be used within `if` statements or ternary expressions due to Bun's compile-time constant constraints.

---

## Core Files

| File | Description |
| :--- | :--- |
| `src/utils/pipeTransport.ts` | PipeServer/PipeClient (Dual-mode UDS + TCP). |
| `src/utils/lanBeacon.ts` | UDP multicast beacon + module-level singleton. |
| `src/utils/ndjsonFramer.ts` | Shared NDJSON socket frame parsing. |
| `src/utils/pipeRegistry.ts` | File registry + `mergeWithLanPeers()`. |
| `src/utils/peerAddress.ts` | Address resolution (UDS/bridge/TCP schemes). |
| `src/utils/pipePermissionRelay.ts` | Permission forwarding + `setPipeRelay`/`getPipeRelay` singleton. |
| `src/hooks/usePipeIpc.ts` | Lifecycle hook (extracted from `REPL.tsx`). |
| `src/hooks/usePipeRelay.ts` | Message回传 (back-propagation) hook. |
| `src/hooks/usePipePermissionForward.ts` | Permission forwarding hook. |
| `src/hooks/usePipeRouter.ts` | Input routing hook. |
| `src/hooks/useMasterMonitor.ts` | Slave registry + message subscription. |

---

## PipeServer TCP Extension

`src/utils/pipeTransport.ts`

### Types

```typescript
export type PipeTransportMode = 'uds' | 'tcp'
export type TcpEndpoint = { host: string; port: number }
export type PipeServerOptions = { enableTcp?: boolean; tcpPort?: number }
```

### PipeServer Changes

- `setupSocket(socket)`: A shared method extracted from `start()`, used by both UDS and TCP.
- `start(options?)`: Optionally enables TCP; `port=0` allows the OS to assign an available port.
- Internally maintains two `net.Server` instances, sharing the same `clients: Set<Socket>` and `handlers`.
- `tcpAddress` getter exposes the TCP port.
- `close()` terminates both servers simultaneously.

Socket frame parsing uses `attachNdjsonFramer()` from `ndjsonFramer.ts` (replacing three instances of duplicated code).

### PipeClient Changes

- Added optional `TcpEndpoint` parameter to the constructor.
- `connect()` dispatches to `connectTcp()` or `connectUds()` based on the presence of a TCP endpoint.
- TCP connections do not require file existence polling and connect directly.

---

## LAN Beacon

`src/utils/lanBeacon.ts`

### Protocol Parameters

| Parameter | Value |
| :--- | :--- |
| **Multicast Group** | `224.0.71.67` |
| **Port** | `7101` |
| **Broadcast Interval** | `3000ms` |
| **Peer Timeout** | `15000ms` |
| **TTL** | `1` |

### Announce Packet

```typescript
type LanAnnounce = {
  proto: 'claude-pipe-v1'
  pipeName: string
  machineId: string
  hostname: string
  ip: string
  tcpPort: number
  role: 'main' | 'sub'
  ts: number
}
```

### API

```typescript
class LanBeacon extends EventEmitter {
  constructor(announce: Omit<LanAnnounce, 'proto' | 'ts'>)
  start(): void
  stop(): void
  getPeers(): Map<string, LanAnnounce>  // Defensive copy
  updateAnnounce(partial): void         // Uses spread (immutable update)

  on('peer-discovered', (peer: LanAnnounce) => void)
  on('peer-lost', (pipeName: string) => void)
}
```

### Storage

Stored as a module-level singleton: `getLanBeacon()` / `setLanBeacon()`. It is not stored in the Zustand state to avoid losing references during `setState` spread operations.

### Interface Binding

`addMembership(group, localIp)` + `setMulticastInterface(localIp)` specifies the LAN interface. This resolves issues on Windows where WSL/Docker virtual adapters might hijack multicast traffic.

---

## Hook Architecture

Approximately 830 lines of Pipe IPC code extracted from `REPL.tsx`:

### usePipeIpc (Lifecycle)

`src/hooks/usePipeIpc.ts` (623 lines)

Loaded via feature-gated `require` at the top level of `REPL.tsx`:

```typescript
const usePipeIpc = feature('UDS_INBOX')
  ? require('../hooks/usePipeIpc.js').usePipeIpc
  : () => undefined;

// Within component
usePipeIpc({ store, handleIncomingPrompt });
```

Uses **lazy getter** functions to load dependencies, preventing Bun runtime crashes due to circular dependencies:

```typescript
const pt = () => require('../utils/pipeTransport.js')
const pr = () => require('../utils/pipeRegistry.js')
const mm = () => require('./useMasterMonitor.js')
// ...
```

`import type` is used for static typing without triggering module loading.

### Four-Phase Functions

| Function | Responsibility |
| :--- | :--- |
| `initPipeServer` | Role determination, server creation, and beacon initiation. |
| `registerMessageHandlers` | Handlers for `ping`, `attach`, `prompt`, `permission`, and `detach`. |
| `runMainHeartbeat` | Cleanup, discovery, auto-attach, and dead connection pruning. |
| `runSubHeartbeat` | Monitors `main` health; handles takeover or independent operation if `main` dies. |

### usePipeRelay (Message Back-propagation)

`src/hooks/usePipeRelay.ts` (38 lines)

Provides `relayPipeMessage()` and `pipeReturnHadErrorRef`. The relay function reads from the `getPipeRelay()` module singleton (replacing `globalThis.__pipeSendToMaster`).

### usePipePermissionForward (Permission Forwarding)

`src/hooks/usePipePermissionForward.ts` (159 lines)

Subscribes to `subscribePipeEntries()` and handles:
- `permission_request` → Payload parsing → Tool lookup → Addition to confirmation queue.
- `permission_cancel` → Removal from queue.
- `stream/error/done` → Conversion to system message display (including role and IP tags).

### usePipeRouter (Input Routing)

`src/hooks/usePipeRouter.ts` (130 lines)

Provides `routeToSelectedPipes(input): boolean`. Reads `selectedPipes` and `routeMode`, sending input to each connected target. Notifications display `[role] hostname/ip` (for LAN peers) or `[role]` (local).

---

## Registry Parallel Probing

`src/utils/pipeRegistry.ts`

### getAliveSubs()

```typescript
export async function getAliveSubs(): Promise<PipeRegistrySub[]> {
  const registry = await readRegistry()
  const results = await Promise.all(
    registry.subs.map(sub =>
      isPipeAlive(sub.pipeName, 1000).then(alive => alive ? sub : null)
    )
  )
  return results.filter(Boolean)
}
```

### cleanupStaleEntries()

Two phases:
1.  **Lock-free Parallel Probing**: Uses `Promise.all` to probe `main` and all `subs`.
2.  **Short-duration Lock Writing**: `acquireLock()` → Re-read → Apply changes → Write → `releaseLock()`.

Lock duration is reduced from several seconds to ~10ms.

### getMachineId()

Uses `execFile` (asynchronous) on Windows and macOS to avoid blocking the main thread. Results are cached after the first execution.

---

## NDJSON Protocol

### Message Types

| Type | Direction | Data |
| :--- | :--- | :--- |
| `ping` / `pong` | Bidirectional | None |
| `attach_request` | M→S | `meta: { machineId }` |
| `attach_accept` / `attach_reject` | S→M | `data: reason` |
| `detach` | M→S | None |
| `prompt` | M→S | `data: prompt_text` |
| `prompt_ack` | S→M | `data: 'accepted'` |
| `stream` | S→M | `data: partial_text` |
| `done` | S→M | None |
| `error` | Bidirectional | `data: error_message` |
| `permission_request` | S→M | `data: JSON(PipePermissionRequestPayload)` |
| `permission_response` | M→S | `data: JSON(PipePermissionResponsePayload)` |
| `permission_cancel` | M→S | `data: JSON({ requestId, reason })` |

### Frame Format

One JSON object per line, separated by `\n`:
```
{"type":"ping","from":"cli-abc","ts":"2026-04-11T00:00:00.000Z"}\n
{"type":"prompt","data":"check git status","from":"cli-abc"}\n
```

---

## Cross-Machine Attach Flow

```
CLI-B (192.168.50.27) Heartbeat Loop
  → beacon.getPeers() discovers CLI-A (192.168.50.22)
  → connectToPipe(pName, myName, 3000, { host: '192.168.50.22', port: 58853 })
  → PipeClient.connectTcp() → net.createConnection({ host, port })
  → client.send({ type: 'attach_request', meta: { machineId } })
  → CLI-A receives:
      isLanPeer = (msg.meta.machineId !== myMachineId) → true
      → Skip role check, directly reply({ type: 'attach_accept' })
      → setPipeRelay(socket.write)
  → CLI-B receives attach_accept
  → addSlaveClient(pName, client)
  → store.setState: role='master', slaves[pName] = { status: 'idle' }
```

**Crucial**: Cross-machine attachment does not require the target to be in a `sub` role. LAN peers are distinguished via `machineId`.

---

## SendMessageTool TCP Support

`packages/builtin-tools/src/tools/SendMessageTool/SendMessageTool.ts`

- The `to` field supports the `tcp:host:port` format.
- `checkPermissions`: The `tcp:` scheme returns `behavior: 'ask'` and `classifierApprovable: false`.
- `call()`: Creates a temporary `PipeClient` → connect → send → disconnect.

---

## Testing

| File | Test Count | Coverage |
| :--- | :--- | :--- |
| `lanBeacon.test.ts` | 7 | Socket initialization, announcement, peer discovery/filtering/cleanup. |
| `peerAddress.test.ts` | 8 | Scheme parsing, `parseTcpTarget`, port range validation. |
| `pipePermissionRelay.test.ts` | 2 | `setPipeRelay` singleton, permission request/response. |
| `pipeTransport.test.ts` | 2 | Basic UDS behavior. |
| `useMasterMonitor.test.ts` | 5 | Slave registration/removal, event emission. |

**Total**: 2190 pass / 0 fail.

---

## Known Limitations

1.  **No TCP Authentication**: Connections can be made by anyone on the LAN who knows the port.
2.  **Plaintext Beacon Broadcasts**: IP, hostname, and `machineId` are not hashed.
3.  **Single Interface Selection**: `getLocalIp()` returns the first non-internal IPv4, which may select a VPN.
4.  **Randomized Ports**: Ports change with each startup, relying on beacon discovery.
5.  **SendMessageTool Connection Overhead**: Creates a new connection for each call instead of reusing existing slave clients.

## Future Improvements

1.  HMAC-SHA256 TCP handshake authentication.
2.  Hash `machineId` before broadcasting.
3.  Multi-interface selection (prioritizing RFC 1918 addresses).
4.  Fixed port range configuration.
5.  TLS encryption for transport.
6.  `SendMessageTool` reuse of established slave clients.
