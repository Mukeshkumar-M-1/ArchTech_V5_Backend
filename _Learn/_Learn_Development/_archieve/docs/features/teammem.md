# TEAMMEM — Team Shared Memory

> Feature Flag: `FEATURE_TEAMMEM=1`
> Implementation Status: Fully operational (requires Anthropic OAuth + GitHub remote).
> Reference Count: 51

## I. Feature Overview

`TEAMMEM` implements a team-shared memory system based on GitHub repositories. Files in the `memory/team/` directory are bidirectionally synchronized with Anthropic servers, allowing all authenticated team members to share project knowledge.

### Core Features

- **Incremental Sync**: Only uploads files with changed content hashes (delta upload).
- **Conflict Resolution**: ETag-based optimistic locking + 412 conflict retries.
- **Secret Scanning**: Detects and skips files containing secrets before upload (PSR M22174).
- **Path Traversal Protection**: All write paths are validated within the `memory/team/` boundary.
- **Batch Uploads**: Automatically splits PUT requests exceeding 200KB to avoid gateway rejection.

## II. User Interaction

### Sync Behavior

| Event | Behavior |
| :--- | :--- |
| **Project Startup** | Automatically pulls team memory to `memory/team/`. |
| **Local File Edit** | Watcher detects changes and triggers an automatic push. |
| **Server Update** | Overwrites local files on the next pull (server-wins). |
| **Secret Detected** | Skips the file and logs a warning; does not block synchronization of other files. |

### API Endpoints

```
GET  /api/claude_code/team_memory?repo={owner/repo}             → Full data + entryChecksums
GET  /api/claude_code/team_memory?repo={owner/repo}&view=hashes → Checksums only (for conflict resolution)
PUT  /api/claude_code/team_memory?repo={owner/repo}             → Upload entries (upsert semantics)
```

## III. Implementation Architecture

### 3.1 Sync State

```ts
type SyncState = {
  lastKnownChecksum: string | null    // ETag for conditional requests
  serverChecksums: Map<string, string> // sha256:<hex> per-file hashes
  serverMaxEntries: number | null      // Server capacity learned from 413 errors
}
```

### 3.2 Pull Flow (Server → Local)

File: `src/services/teamMemorySync/index.ts:770-867`

```
pullTeamMemory(state)
      │
      ▼
Check OAuth + GitHub remote
      │
      ▼
fetchTeamMemory(state, repo, etag)
  ├── 304 Not Modified → Return (No change)
  ├── 404 → Return (No data on server)
  └── 200 → Parse TeamMemoryData
      │
      ▼
Refresh serverChecksums (per-key hashes)
      │
      ▼
writeRemoteEntriesToLocal(entries)
  ├── Path traversal validation (validateTeamMemKey)
  ├── File size check (Skip if > 250KB)
  ├── Content comparison (Skip write if identical)
  └── Parallel writes (Promise.all)
```

### 3.3 Push Flow (Local → Server)

File: `src/services/teamMemorySync/index.ts:889-1146`

```
pushTeamMemory(state)
      │
      ▼
readLocalTeamMemory(maxEntries)
  ├── Recursively scan memory/team/ directory
  ├── Skip oversized files (> 250KB)
  ├── Secret scanning (scanForSecrets using gitleaks rules)
  └── Truncate by serverMaxEntries (if known)
      │
      ▼
Calculate delta = Local Files - serverChecksums
  (Includes only files with mismatched hashes)
      │
      ▼
batchDeltaByBytes(delta)
  (Split into batches ≤ 200KB)
      │
      ▼
uploadTeamMemory(state, repo, batch, etag) per batch
  ├── 200 Success → Update serverChecksums
  ├── 412 Conflict → fetchTeamMemoryHashes() to refresh checksums
  │              → Retry delta calculation (up to 2 times)
  └── 413 Capacity Exceeded → Learn serverMaxEntries
```

### 3.4 Secret Scanning

File: `src/services/teamMemorySync/secretScanner.ts`

Scans file contents using gitleaks rule patterns. When a secret is detected:
- The file is skipped (not uploaded).
- A `tengu_team_mem_secret_skipped` event is logged (logs the rule ID only, not the value).
- Other files continue to synchronize.

### 3.5 File Watcher

File: `src/services/teamMemorySync/watcher.ts`

Monitors the `memory/team/` directory for changes and triggers automatic pushes. It suppresses false changes caused by local writes during a pull.

### 3.6 Path Security

File: `src/memdir/teamMemPaths.ts`

- `validateTeamMemKey(relPath)`: Validates that the relative path does not exceed the `memory/team/` boundary.
- `getTeamMemPath()`: Returns the absolute path to the team memory root directory.

## IV. Key Design Decisions

1.  **Server-Wins on Pull, Local-Wins on Push**: Server content overwrites local on pull; local edits overwrite server on push. Local edits by the user are never silently discarded.
2.  **Delta Upload**: Saves bandwidth by only uploading entries with hash changes. The initial push is full; subsequent pushes are incremental.
3.  **Batch PUT**: Limits single PUT requests to ≤200KB to avoid rejection by API gateways (~256-512KB). Each batch is an independent upsert; partial failures do not affect successfully committed batches.
4.  **Pre-Upload Secret Scanning**: PSR M22174 requires that secrets never leave the local machine. Scanning is performed in `readLocalTeamMemory`, and files containing secrets are excluded from the upload set.
5.  **ETag Optimistic Locking**: Pushes use the `If-Match` header. On 412 errors, the system probes `?view=hashes` (fetching checksums only) to refresh state and retry.
6.  **Dynamic Capacity Learning**: The client does not assume a capacity limit; it learns from the `extra_details.max_entries` field in 413 responses.

## V. Usage

```bash
# Enable the feature
FEATURE_TEAMMEM=1 bun run dev

# Prerequisites:
# 1. Logged in via Anthropic OAuth.
# 2. Project has a GitHub remote (git remote -v shows origin).
# 3. memory/team/ directory is created automatically.
```

## VI. External Dependencies

| Dependency | Description |
| :--- | :--- |
| **Anthropic OAuth** | First-party authentication. |
| **GitHub Remote** | `getGithubRepo()` retrieves `owner/repo` as the sync scope. |
| **Team Memory API** | `/api/claude_code/team_memory` endpoint. |

## VII. File Index

| File | Lines | Responsibility |
| :--- | :--- | :--- |
| `src/services/teamMemorySync/index.ts` | 1257 | Core sync logic (pull/push/sync). |
| `src/services/teamMemorySync/watcher.ts` | — | File monitoring and auto-sync triggers. |
| `src/services/teamMemorySync/secretScanner.ts` | — | Gitleaks secret scanning. |
| `src/services/teamMemorySync/types.ts` | — | Zod schemas and type definitions. |
| `src/services/teamMemorySync/teamMemSecretGuard.ts` | — | Secret protection helpers. |
| `src/memdir/teamMemPaths.ts` | — | Path validation and directory management. |
