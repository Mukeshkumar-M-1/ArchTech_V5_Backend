# Tier 3 — Pure Stubs / N/A Low Priority Features Overview

> This document summarizes all Tier 3 features. These functions are either pure stubs (all functions return null), part of Anthropic's internal infrastructure (N/A), or auxiliary features with very low reference counts.

## Overview

| Feature | References | Status | Category | Brief Description |
| :--- | :--- | :--- | :--- | :--- |
| `CHICAGO_MCP` | 16 | Implemented | Tool | Computer Use + Chrome MCP control (Enabled by default in builds). |
| `MONITOR_TOOL` | 13 | Implemented | Tool | Background monitoring tool; continuously monitors shell output (Enabled by default in builds). |
| `BG_SESSIONS` | 11 | Partial | Session | Background session registration/cleanup is implemented; task summary is a stub (Enabled by default in dev). |
| `SHOT_STATS` | 10 | Implemented | Stats | API call statistics panel (Enabled by default in builds). |
| `EXTRACT_MEMORIES` | 7 | Implemented | Memory | Automatic memory extraction (Enabled by default in builds; gated by GrowthBook). |
| `TEMPLATES` | 6 | Partial | Management | Project/prompt template system (Enabled by default in dev). |
| `LODESTONE` | 6 | Implemented | Deep Link | URL protocol handler (Enabled by default in builds). |

## Single-Reference Features (40+)

The following features have only one reference each and are mostly internal markers or experimental functions:

`UNATTENDED_RETRY`, `ULTRATHINK`, `TORCH`, `SLOW_OPERATION_LOGGING`, `SKILL_IMPROVEMENT`, `SELF_HOSTED_RUNNER`, `RUN_SKILL_GENERATOR`, `PERFETTO_TRACING`, `NATIVE_CLIENT_ATTESTATION`, `KAIROS_DREAM` (see [kairos.md](./kairos.md)), `IS_LIBC_MUSL`, `IS_LIBC_GLIBC`, `DUMP_SYSTEM_PROMPT`, `COMPACTION_REMINDERS`, `CCR_REMOTE_SETUP`, `BYOC_ENVIRONMENT_RUNNER`, `BUILTIN_EXPLORE_PLAN_AGENTS`, `BUILDING_CLAUDE_APPS`, `ANTI_DISTILLATION_CC`, `AGENT_TRIGGERS`, `ABLATION_BASELINE`.

## Priority Rationale

These features are classified as Tier 3 for the following reasons:

1.  **Implemented but low impact**: (`CHICAGO_MCP`, `LODESTONE`, `SHOT_STATS`, `EXTRACT_MEMORIES`, `MONITOR_TOOL`) These are enabled by default in build/dev modes but primarily serve as infrastructure for other features.
2.  **Partially implemented**: (`BG_SESSIONS`, `TEMPLATES`) Core registration logic is implemented, but certain parts (e.g., task summaries) remain stubs.
3.  **Auxiliary features**: (`STREAMLINED_OUTPUT`, `HOOK_PROMPTS`) These have a very small scope of influence.
4.  **CCR Series**: These depend on remote control infrastructure and require `BRIDGE_MODE` to be fully matured first.

To learn more about a specific Tier 3 feature, search for `feature('FEATURE_NAME')` in the codebase to see its usage context.
