#Automatic update mechanism

## Overview

Claude Code has a complex multi-strategy automatic update system that supports three installation methods, background silent updates, manual CLI commands, server-side version gating, and update log display. The system design goal is to keep the CLI up to date with minimal user intervention while providing fallback means for rollback and manual control.

---

## Installation type and update strategy

The update strategy is determined by the installation method and is detected through `src/utils/doctorDiagnostic.ts`:

| Installation type | Update policy | Automatically install? |
|---|---|---|
| `native` | Download binaries from GCS/Artifactory, activate via symlink | Yes (silent) |
| `npm-global` | `npm install -g` / `bun install -g` | Yes (silent) |
| `npm-local` | `npm install` to `~/.claude/local/` | yes (silent) |
| `package-manager` | Display a notification with the upgrade command for the corresponding operating system | No (notification only) |
| `development` | Not applicable - an error is reported when executing `claude update` | Not applicable |

### Policy routing

`src/components/AutoUpdaterWrapper.tsx` — mounted in the React/Ink UI tree — detects the installation type and renders the corresponding update component:

- `native` → `NativeAutoUpdater` (binary download + symbolic link)
- `package-manager` → `PackageManagerAutoUpdater` (notification only)
- Others → `AutoUpdater` (based on JS/npm)

---

## Background automatic update cycle

The three update components share the same polling pattern:

```typescript
useInterval(checkForUpdates, 30 * 60 * 1000); // every 30 minutes
```

A check is also performed when the component is mounted (i.e. at startup).

### Pre-check gate control

Before any update attempt, the system checks for:

1. **Is automatic updates disabled? ** — `getAutoUpdaterDisabledReason()` (`src/utils/config.ts:1737`)
   - `NODE_ENV === 'development'`
   - Set the `DISABLE_AUTOUPDATER` environment variable
   - Necessary traffic mode only
   - `config.autoUpdates === false` (except for native installed protected mode)
2. **Maximum version limit? ** — `getMaxVersion()` (`src/utils/autoUpdater.ts:108`) — Server-side circuit breaker to prevent updates to known problematic versions
3. **Skip this version? ** — `shouldSkipVersion()` (`src/utils/autoUpdater.ts:145`) — Respect the user’s `minimumVersion` setting to prevent unexpected version downgrades when switching to the stable channel

### Native automatic updater (`src/components/NativeAutoUpdater.tsx`)

1. Call `installLatest()` in `src/utils/nativeInstaller/installer.ts`
2. Download the binary file (GCS or Artifactory) through `src/utils/nativeInstaller/download.ts`
3. Verify SHA256 checksum (3 retries, 60 seconds lag detection)
4. Store versioned binaries into the XDG directory
5. Update symbolic links (`~/.local/bin/claude` → new version binary)
6. Keep the last 2 versions and clean up the old versions
7. Report errors into categories for analysis (timeout, checksum, permissions, insufficient disk space, npm, network)

### JS/npm automatic updater (`src/components/AutoUpdater.tsx`)

1. Call `getLatestVersion()` to get the current npm dist-tag
2. Compare versions through semver `gte()`
3. Route to local or global installation based on installation type
4. Use file locks (`acquireLock()` / `releaseLock()`) to prevent concurrent updates

### Package Manager Notifier (`src/components/PackageManagerAutoUpdater.tsx`)

Check for updates via GCS bucket (non-npm) every 30 minutes. **No automatic installation** — Only the upgrade command for the corresponding operating system is displayed:

- macOS: `brew upgrade claude-code`
- Windows: `winget upgrade Anthropic.ClaudeCode`
- Alpine: `apk upgrade claude-code`

---

## Start version gating

`src/utils/autoUpdater.ts:70` — `assertMinVersion()`

Defined in `src/utils/autoUpdater.ts:70`, it is designed to be called at startup (currently not connected to the startup process):

```typescript
void assertMinVersion();
```

1. Get `tengu_version_config` from GrowthBook dynamic configuration
2. If `MACRO.VERSION < minVersion`, print error message and call `gracefulShutdownSync(1)` — force user to update
3. This is a **hard gate** — CLIs below the minimum version will fail to launch

---

## Manual CLI commands

### `claude update` / `claude upgrade`

**File**: `src/cli/update.ts`

Complete process:
1. Run `getDoctorDiagnostic()` to check system health status
2. Check whether there are multiple installations and configuration inconsistencies
3. Route based on installation type:
   - `development` → error ("The development version does not support automatic updates")
   - `package-manager` → print the update command for the corresponding operating system
   - `native` → use the native installer's `updateLatest()`
   - `npm-local` → Execute `npm install` in `~/.claude/local/`
   - `npm-global` → execute `npm install -g` (including permission check)
4. Report current version, latest version, success/failure status

### `claude rollback [target]` (internal only)

Roll back to previous version. Supports `--list`, `--dry-run`, `--safe` flags.

### `claude install [target]`

Install or reinstall the native build. Accepts an optional version target parameter.

### `claude doctor`

Checks the health of the auto-updater, reporting status, permissions, and configuration information.

---

## Native installer architecture

**File**: `src/utils/nativeInstaller/installer.ts`

### Binary file storage layout

```
~/.local/share/claude-code/
├── versions/ # Versioned binaries (claude-1.0.3, claude-1.0.4, ...)
├── staging/ # Temporary download staging area
└── locks/ # Lock file based on PID and mtime

~/.local/bin/claude # Symbolic link to the current version of the binary
```

Windows systems use file copying instead of symbolic links.

### Core operations

| Function | Description |
|---|---|
| `updateLatest()` | Core update process: maximum version limit → skip check → lock → download → install → update symbolic link |
| `installLatest()` | Singleflight packaged version to prevent repeated in-progress installations |
| `cleanupOldVersions()` | Keep the last 2 versions and clean up the expired staging area and temporary files |
| `lockCurrentVersion()` | Process life cycle lock to prevent the running version from being deleted |
| `cleanupNpmInstallations()` | Clean up old npm installations when migrating to native installations |

### Download and Verification

**File**: `src/utils/nativeInstaller/download.ts`

1. Route to Artifactory (internal users) or GCS bucket (external users)
2. Download binaries and track progress
3. SHA256 checksum verification
4. 60-second freeze detection (aborting stalled downloads)
5. Automatically retry 3 times on failure

---

## File lock mechanism

**File**: `src/utils/autoUpdater.ts:176-268`

To prevent concurrent update processes from disrupting the installation:

- Lock file: `~/.claude/update.lock` (or equivalent path)
- 5 minute timeout - locks older than 5 minutes are considered expired and forced to be acquired
- The process writes its PID to the lock file
- `acquireLock()` and `releaseLock()` are used by both JS/npm and native installers

---

## Configuration

### Setting items

**File**: `src/utils/settings/types.ts`

| Setting items | Type | Description |
|---|---|---|
| `autoUpdatesChannel` | `'latest' \| 'stable'` | Release channel for automatic updates |
| `minimumVersion` | string | Minimum version requirement to prevent accidental version downgrade |

### Global configuration

**File**: `src/utils/config.ts:191-193`

| Field | Type | Description |
|---|---|---|
| `autoUpdates` | boolean | Enable/disable automatic updates (legacy) |
| `autoUpdatesProtectedForNative` | boolean | Native installations always update automatically |

### Configuration migration

**File**: `src/migrations/migrateAutoUpdatesToSettings.ts`

One-time migration of legacy `globalConfig.autoUpdates = false` to `DISABLE_AUTOUPDATER=1` environment variable in settings. Defined in `src/migrations/migrateAutoUpdatesToSettings.ts` (currently not connected to the startup process).

---

## Update notification deduplication

**File**: `src/hooks/useUpdateNotification.ts`

React hook `useUpdateNotification(updatedVersion)` — Ensures that the "restart to update" message is only displayed once per semver change (major.minor.patch) to avoid repeated notifications for the same version.

---

## Update log

**File**: `src/utils/releaseNotes.ts`

1. Call from `src/setup.ts:387` on every startup
2. Get the changelog from GitHub
3. Cache to `~/.claude/cache/changelog.md`
4. Display the update log of a version newer than `lastReleaseNotesSeen`
5. Use semver to compare and determine which logs need to be displayed

---

## Version comparison

**File**: `src/utils/semver.ts`

- Provides `gt()`, `gte()`, `lt()`, `lte()`, `satisfies()`, `order()`
- Use `Bun.semver.order()` in Bun environment (20 times faster)
- Fallback to npm `semver` package in Node.js environment

---

## Analyze events

All update related telemetry data using `tengu_` prefixed events:

| Categories | Events |
|---|---|
| Version check | `tengu_version_check_success`, `tengu_version_check_failure` |
| JS automatic updater | `tengu_auto_updater_start/success/fail/up_to_date/lock_contention` |
| Native automatic updater | `tengu_native_auto_updater_start/success/fail` |
| Native update | `tengu_native_update_complete/skipped_max_version/skipped_minimum_version` |
| Lock mechanism | `tengu_version_lock_acquired/failed`, `tengu_native_update_lock_failed` |
| Binary download | `tengu_binary_download_attempt/success/failure`, `tengu_binary_manifest_fetch_failure` |
| Cleanup | `tengu_native_version_cleanup`, `tengu_native_staging_cleanup`, `tengu_native_stale_locks_cleanup` |
| Installation | `tengu_native_install_package_success/failure`, `tengu_native_install_binary_success/failure` |
| Manual update | `tengu_update_check` |
| Migration | `tengu_migrate_autoupdates_to_settings`, `tengu_migrate_autoupdates_error` |

---

## Key file index

| Documentation | Responsibilities |
|---|---|
| `src/utils/autoUpdater.ts` | Core logic: version checking, npm installation, file lock, minimum/maximum version gating |
| `src/cli/update.ts` | `claude update` command processing |
| `src/utils/nativeInstaller/installer.ts` | Native binary installer: download, version management, symbolic links, cleaning |
| `src/utils/nativeInstaller/download.ts` | Download the binary file from GCS/Artifactory and verify |
| `src/utils/localInstaller.ts` | Local installer (`~/.claude/local/`) based on npm |
| `src/components/AutoUpdaterWrapper.tsx` | Policy routing based on installation type |
| `src/components/AutoUpdater.tsx` | JS/npm background automatic updater (30 minutes interval) |
| `src/components/NativeAutoUpdater.tsx` | Native binary background automatic updater (30 minute interval) |
| `src/components/PackageManagerAutoUpdater.tsx` | Package Manager Notifications (30 minutes, display only) |
| `src/hooks/useUpdateNotification.ts` | Press semver to remove duplicate update notifications |
| `src/utils/releaseNotes.ts` | Changelog acquisition, caching and display |
| `src/utils/semver.ts` | Semver version comparison (Bun native + npm fallback) |
| `src/utils/doctorDiagnostic.ts` | Installation type detection and health diagnosis |
| `src/utils/config.ts:1737` | `getAutoUpdaterDisabledReason()` — disable checking logic |
| `src/migrations/migrateAutoUpdatesToSettings.ts` | Old version configuration migration |
| `src/screens/Doctor.tsx` | Doctor command UI, showing automatic update status |

---

## Flowchart

```
startup phase
  ├── assertMinVersion() → Hard interception when the version is too low and refuses to start
  ├── migrateAutoUpdatesToSettings() → One-time configuration migration
  └── checkForReleaseNotes() → Show the update log of the new version

REPL running (every 30 minutes)
  ├── AutoUpdaterWrapper detects installation type
  │
  ├── native → NativeAutoUpdater
  │ ├── Get version from GCS/Artifactory
  │ ├── Check the maximum version limit (server-side control)
  │ ├── Check minimumVersion setting (skip)
  │ ├── acquireLock()
  │ ├── downloadAndVerifyBinary() (SHA256 verification, 3 retries)
  │ ├── Install to versions/ directory
  │ ├── Update symbolic link
  │ └── cleanupOldVersions() (retain 2 versions)
  │
  ├── npm-global/local → AutoUpdater
  │ ├── Get the latest version from npm registry
  │ ├── semver version comparison
  │ ├── acquireLock()
  │ └── npm install -g / local installation
  │
  └── package-manager → PackageManagerAutoUpdater
        ├── Get version from GCS
        └── Display "Run: brew upgrade ..." (no automatic installation)

manual operation
  └── claude update → Complete diagnosis + installation orchestration
```