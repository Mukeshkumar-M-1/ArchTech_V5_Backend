# GrowthBook Feature Enablement Plan

> **Date**: 2026-04-06
> **Based On**: `feature-flags-codex-review.md` + deep analysis of 4 parallel research agents.
> **Prerequisite**: We are paid subscribers with valid Anthropic API keys.

---

## Background

Claude Code utilizes a three-layer gating system:
1.  **Compile-time feature flags** — `feature('FLAG_NAME')` from `bun:bundle`.
2.  **GrowthBook remote switches** — Prefixed with `tengu_*`, connected to Anthropic servers via SDK.
3.  **Runtime environment variables** — `USER_TYPE`, `CLAUDE_CODE_*`, etc.

In our decompiled version, GrowthBook is not initialized (analytics chain is a stub), causing all `tengu_*` checks to return `false` by default.

**Core Finding: All feature code gated by GrowthBook is actually implemented and functional (not stubs).**

---

## Enablement Methods

### Method 1: Hardcoded Bypass (Recommended for immediate use)
Add default value mappings in the `getFeatureValueInternal()` function within `src/services/analytics/growthbook.ts`.

### Method 2: Self-Hosted GrowthBook Server
```bash
docker run -p 3100:3100 growthbook/growthbook
# Set environment variables
CLAUDE_GB_ADAPTER_URL=http://localhost:3100
CLAUDE_GB_ADAPTER_KEY=sdk-xxx
```

### Method 3: Restore Native 1P Connection
Set `is1PEventLoggingEnabled()` to return `true` to connect to Anthropic's GrowthBook servers.
*Note: This will send usage statistics (excluding code and conversation content).*

---

## Priority P0: Purely Local Features (Zero external dependencies, ready immediately)

These features do not require API calls and can be activated by enabling the gates.

### P0-1. Custom Keybindings
- **Gate**: `tengu_keybinding_customization_release` → `true`
- **Compile Flag**: None (built-in).
- **Code**: 473 lines, full implementation.
- **Function**: Loads `~/.claude/keybindings.json`; supports hot reloading, duplicate key detection, and structure validation.
- **Effect**: Allows users to customize all keybindings.
- **Risk**: None.

### P0-2. Streaming Tool Execution
- **Gate**: `tengu_streaming_tool_execution2` → `true`
- **Compile Flag**: None (built-in).
- **Code**: 577 lines (`StreamingToolExecutor`), full implementation.
- **Function**: Starts tool execution while the API response is still streaming, reducing latency.
- **Effect**: Significantly improves interaction speed.
- **Risk**: Low (production-grade code with error handling).

### P0-3. Scheduled Task System
- **Gate**: `tengu_kairos_cron` → `true` (Add: `tengu_kairos_cron_durable` defaults to `true`).
- **Compile Flag**: `AGENT_TRIGGERS` (newly required) or `AGENT_TRIGGERS_REMOTE` (enabled).
- **Code**: 1025 lines (`cronTasks` + `cronScheduler`), full implementation.
- **Function**: Local cron scheduling; supports one-off/periodic tasks, anti-thundering-herd jitter, and automatic expiration.
- **Effect**: Allows setting scheduled Claude tasks.
- **Risk**: Low.

### P0-4. Agent Teams / Swarm
- **Gate**: `tengu_amber_flint` → `true` (Kill switch, defaults to `true`).
- **Compile Flag**: None (built-in).
- **Code**: 45 lines (gate layer); swarm implementation is within teammate tools.
- **Function**: Multi-agent collaboration; requires `--agent-teams` or `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`.
- **Effect**: Allows creation and management of agent teams.
- **Risk**: None.

### P0-5. Token-Efficient JSON Tool Format
- **Gate**: `tengu_amber_json_tools` → `true`
- **Compile Flag**: None (built-in).
- **Code**: A few lines of gate checks in `betas.ts`.
- **Function**: Enables FC v3 format, reducing output tokens by approximately 4.5%.
- **Effect**: Cost savings.
- **Risk**: Low (requires model support for this beta header).

### P0-6. Ultrathink Expanded Thinking
- **Gate**: `tengu_turtle_carbon` → `true` (Defaults to `true`, kill switch).
- **Compile Flag**: None.
- **Function**: Triggers expanded thinking mode via keywords.
- **Effect**: Already enabled by default; ensure it is not remotely disabled.
- **Risk**: None.

### P0-7. Immediate Model Switching
- **Gate**: `tengu_immediate_model_command` → `true`
- **Compile Flag**: None.
- **Function**: Enables immediate execution of `/model`, `/fast`, and `/effort` commands during an active query.
- **Effect**: Switch models without waiting for the current task to finish.
- **Risk**: Low.

---

## Priority P1: API-Dependent Features (Requires Claude API key)

These features require calling the Claude API (using forked subagents or `queryModel`) and are available with a valid subscription.

### P1-1. Session Memory
- **Gate**: `tengu_session_memory` → `true` (Config: `tengu_sm_config` → `{}`).
- **Compile Flag**: None (built-in).
- **Code**: 1127 lines, full implementation.
- **Function**: Cross-session context persistence. Uses forked agents to periodically extract notes into markdown files.
- **Effect**: Claude remembers working context across different sessions.
- **Dependency**: Claude API (forked subagent).
- **Risk**: Low (additional API token consumption).

### P1-2. Auto Memory Extraction
- **Gate**: `tengu_passport_quail` → `true` (Related: `tengu_moth_copse`, `tengu_coral_fern`).
- **Compile Flag**: `EXTRACT_MEMORIES` (newly required).
- **Code**: 616 lines, full implementation.
- **Function**: Automatically extracts persistent memory during conversations to `~/.claude/projects/<path>/memory/`.
- **Effect**: Automatically builds a project knowledge base.
- **Dependency**: Claude API (forked subagent).
- **Risk**: Low.

### P1-3. Prompt Suggestions
- **Gate**: `tengu_chomp_inflection` → `true`
- **Compile Flag**: None (built-in).
- **Code**: 525 lines, full implementation.
- **Function**: Automatically generates next-step operation suggestions with speculative prefetching.
- **Effect**: Smoother interaction experience.
- **Dependency**: Claude API (forked subagent).
- **Risk**: Low (additional API consumption, but includes cache awareness).

### P1-4. Verification Agent
- **Gate**: `tengu_hive_evidence` → `true`
- **Compile Flag**: `VERIFICATION_AGENT` (newly required).
- **Code**: 153 lines (agent definition), full implementation.
- **Function**: Adversarial verification agent that actively attempts to break your implementation (read-only mode).
- **Effect**: Automated code verification.
- **Dependency**: Claude API (subagent).
- **Risk**: Low (read-only; does not modify code).

### P1-5. Brief Mode
- **Gate**: `tengu_kairos_brief` → `true`
- **Compile Flag**: `KAIROS` or `KAIROS_BRIEF` (newly required).
- **Code**: 335 lines, full implementation.
- **Function**: `/brief` command toggles a concise output mode.
- **Effect**: Reduces redundant output.
- **Dependency**: Claude API.
- **Risk**: Low.

### P1-6. Away Summary
- **Gate**: `tengu_sedge_lantern` → `true`
- **Compile Flag**: `AWAY_SUMMARY` (newly required).
- **Code**: 176 lines, full implementation.
- **Function**: Automatically summarizes what happened while the user was away from the terminal for more than 5 minutes.
- **Effect**: Rapidly restores context.
- **Dependency**: Claude API + Terminal focus event support.
- **Risk**: Low.

### P1-7. Auto-Dream
- **Gate**: `tengu_onyx_plover` → `{"enabled": true}`
- **Compile Flag**: None (built-in, but checks if auto-memory is enabled).
- **Code**: 349 lines, full implementation.
- **Function**: Background memory consolidation (equivalent to automatically running `/dream`).
- **Effect**: Automatically keeps memory organized and tidy.
- **Dependency**: Claude API (forked subagent) + auto-memory enabled.
- **Risk**: Low.

### P1-8. Idle Return Prompts
- **Gate**: `tengu_willow_mode` → `"dialog"` or `"hint"`.
- **Compile Flag**: None.
- **Function**: Prompts the user to start a new session when the context is too large and the cache has expired.
- **Effect**: Avoids wasting tokens on expired caches.
- **Risk**: None.

---

## Priority P2: Enhancement Features (Improved experience but non-essential)

### P2-1. Incremental MCP Instruction Transfer
- **Gate**: `tengu_basalt_3kr` → `true`
- **Function**: Sends only modified MCP instructions rather than the full set.
- **Effect**: Reduces token consumption.
- **Risk**: Low.

### P2-2. Leaf Pruning Optimization
- **Gate**: `tengu_pebble_leaf_prune` → `true`
- **Function**: Removes dead-end message branches from session storage.
- **Effect**: Reduces storage and loading times.
- **Risk**: Low.

### P2-3. Message Merging
- **Gate**: `tengu_chair_sermon` → `true`
- **Function**: Merges adjacent `tool_result` and `text` blocks.
- **Effect**: Reduces token consumption.
- **Risk**: Low.

### P2-4. Deep Linking
- **Gate**: `tengu_lodestone_enabled` → `true`
- **Function**: Registers the `claude://` URL protocol handler.
- **Effect**: Opens Claude Code directly from a browser.
- **Risk**: Low.

### P2-5. Auto-Background Agents
- **Gate**: `tengu_auto_background_agents` → `true`
- **Function**: Automatically moves agent tasks to the background after 120 seconds of execution.
- **Effect**: Prevents blocking the main interaction.
- **Risk**: Low.

### P2-6. Fine-Grained Tool Status
- **Gate**: `tengu_fgts` → `true`
- **Function**: Includes fine-grained tool status information in system prompts.
- **Effect**: Better model understanding of tool availability.
- **Risk**: Low.

### P2-7. Git Diff for File Operations
- **Gate**: `tengu_quartz_lantern` → `true`
- **Function**: Calculates git diffs during file writes/edits (remote sessions only).
- **Effect**: Better change tracking.
- **Risk**: Low.

---

## Priority P3: Service or Anthropic OAuth Dependent Features

### P3-1. Team Memory
- **Gate**: `tengu_herring_clock` → `true`
- **Compile Flag**: `TEAMMEM` (newly required).
- **Code**: 1180+ lines, full implementation.
- **Function**: Shared memory across agents, synchronized with Anthropic API.
- **Dependency**: Anthropic OAuth + GitHub remote.
- **Status**: Requires Anthropic's `/api/claude_code/team_memory` endpoint.
- **Feasibility**: Unavailable unless a compatible API is self-hosted.

### P3-2. Settings Sync
- **Gate**: `tengu_enable_settings_sync_push` + `tengu_strap_foyer` → `true`
- **Compile Flag**: `UPLOAD_USER_SETTINGS` / `DOWNLOAD_USER_SETTINGS` (newly required).
- **Code**: 582 lines, full implementation.
- **Function**: Cross-device settings synchronization.
- **Dependency**: Anthropic OAuth + `/api/claude_code/user_settings`.
- **Feasibility**: Unavailable as above.

### P3-3. Bridge Remote Control
- **Gate**: `tengu_ccr_bridge` → `true` (Compile flag `BRIDGE_MODE` already enabled in dev).
- **Code**: 12,619 lines, full implementation.
- **Function**: Remote control of the CLI via the claude.ai web interface.
- **Dependency**: claude.ai subscription + WebSocket backend.
- **Feasibility**: Requires Anthropic's CCR (Claude Code Remote) backend.

### P3-4. Remote Scheduled Agents
- **Gate**: `tengu_surreal_dali` → `true`
- **Function**: Creates scheduled agents that execute remotely.
- **Dependency**: Anthropic CCR infrastructure.
- **Feasibility**: Requires remote services.

---

## Kill Switch List (Ensuring features are not remotely disabled)

These gates are `true` by default and act as kill switches. Ensure they remain `true`:

| Gate | Default | Description |
| :--- | :--- | :--- |
| `tengu_turtle_carbon` | `true` | Ultrathink expanded thinking. |
| `tengu_amber_stoat` | `true` | Built-in Explore/Plan agent. |
| `tengu_amber_flint` | `true` | Agent Teams/Swarm. |
| `tengu_slim_subagent_claudemd` | `true` | Simplified `CLAUDE.md` for subagents. |
| `tengu_birch_trellis` | `true` | Tree-sitter bash safety analysis. |
| `tengu_collage_kaleidoscope` | `true` | macOS clipboard image reading. |
| `tengu_compact_cache_prefix` | `true` | Reuse of prompt cache during compaction. |
| `tengu_kairos_cron_durable` | `true` | Persistent cron tasks. |
| `tengu_attribution_header` | `true` | API request attribution headers. |
| `tengu_slate_prism` | `true` | Agent progress summaries. |

---

## New Compile Flags Required

The following compile-time flags are not yet enabled in `build.ts` or `scripts/dev.ts`, but the corresponding code is complete:

| Flag | Purpose | Priority |
| :--- | :--- | :--- |
| `AGENT_TRIGGERS` | Scheduled task system (P0-3). | P0 |
| `EXTRACT_MEMORIES` | Auto memory extraction (P1-2). | P1 |
| `VERIFICATION_AGENT` | Verification agent (P1-4). | P1 |
| `KAIROS` or `KAIROS_BRIEF` | Brief mode (P1-5). | P1 |
| `AWAY_SUMMARY` | Away summary (P1-6). | P1 |
| `TEAMMEM` | Team memory (P3-1). | P3 |

---

## Implementation Roadmap

### Phase 1: Hardcode P0 Purely Local Gates (Fastest results)
1. Add default value mappings in `growthbook.ts`.
2. Add the `AGENT_TRIGGERS` compile flag in `build.ts` / `dev.ts`.
3. Verify that the 7 P0 features work correctly.
4. **Estimated Effort**: 1–2 hours.

### Phase 2: Enable P1 API-Dependent Features
1. Add compile flags: `EXTRACT_MEMORIES`, `VERIFICATION_AGENT`, `KAIROS_BRIEF`, `AWAY_SUMMARY`.
2. Add P1 gate default values.
3. Verify that the 8 P1 features work correctly.
4. **Estimated Effort**: 2–3 hours.

### Phase 3: Evaluate Self-Hosted GrowthBook (Optional)
1. Deploy a GrowthBook server via Docker.
2. Migrate hardcoded values to the GrowthBook management console.
3. Gain the ability to manage all flags via a Web UI.
4. **Estimated Effort**: Half a day.

### Phase 4: Evaluate Remote Features (Optional)
1. Research the feasibility of using Anthropic OAuth.
2. Evaluate self-hosting possibilities for Team Memory and Settings Sync.
3. **Estimated Effort**: TBD.

---

## Privacy Information

### Hardcoded Bypass (Option A)
- **Zero data exfiltration.**
- GrowthBook SDK is not started.
- Runs entirely offline.

### Self-Hosted GrowthBook (Option B)
- Data is sent only to your own server.
- Anthropic receives no data.
- All flags managed in real-time via Web UI.

### Restore Native 1P (Option C)
- Usage statistics are sent to `api.anthropic.com`.
- **NOT SENT**: Code, conversation content, or API keys.
- **SENT**: Email, device ID, machine fingerprints, repository hashes, and subscription types.
- Can be disabled via `DISABLE_TELEMETRY=1` (though this also disables GrowthBook).
