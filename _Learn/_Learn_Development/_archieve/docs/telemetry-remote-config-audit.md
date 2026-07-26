# Telemetry and Remote Configuration Audit

## 1. Datadog Logging

**File**: `src/services/analytics/datadog.ts`

- **Endpoint**: Configured via the `DATADOG_LOGS_ENDPOINT` environment variable (disabled if empty).
- **Client Token**: Configured via the `DATADOG_API_KEY` environment variable (disabled if empty).
- **Behavior**: Batch sends logs (15s flush interval, 100-entry cap). Limited to 1P (direct Anthropic API) users.
- **Event Whitelist**: `tengu_*` series events (startup, errors, OAuth, tool calls, etc. - ~35 types).
- **Baseline Data**: Collects model, platform, arch, version, and `userBucket` (user hashed into 30 buckets).
- **Requirement**: `NODE_ENV === 'production'`.
- **Example Config**: `DATADOG_LOGS_ENDPOINT=https://http-intake.logs.datadoghq.com/api/v2/logs DATADOG_API_KEY=xxx bun run dev`

## 2. 1P Event Logging (BigQuery)

**File**: `src/services/analytics/firstPartyEventLogger.ts` + `firstPartyEventLoggingExporter.ts`

- **Endpoint**: `https://api.anthropic.com/api/event_logging/batch` (switchable to staging).
- **Behavior**: Uses the OpenTelemetry SDK's `BatchLogRecordProcessor` for batch exporting to Anthropic's internal BQ pipeline.
- **Data**: Complete event metadata (session, model, env context, user data, subscription type, etc.).
- **Resilience**: Failed events are persisted to local disk (JSONL) with exponential backoff retries (up to 8 attempts).
- **Proto Schema**: Events are serialized using the `ClaudeCodeInternalEvent` / `GrowthbookExperimentEvent` Protobuf formats.
- **Auth Fallback**: Automatically retries without auth headers on 401 errors.

## 3. GrowthBook Remote Feature Flags / Dynamic Configuration

**File**: `src/services/analytics/growthbook.ts`

- **Server**: `https://api.anthropic.com/` (remote evaluation mode).
- **Behavior**: Fetches full feature flags at startup; refreshes every 6 hours (external users) or 20 minutes (Anthropic internal).
- **Disk Cache**: Feature values are cached in `~/.claude.json` under `cachedGrowthBookFeatures`.
- **Use Cases**:
  - Toggles for Datadog (`tengu_log_datadog_events`).
  - Event sampling rates (`tengu_event_sampling_config`).
  - Killswitches for sinks (`tengu_frond_boric`).
  - BQ batch configurations (`tengu_1p_event_batch_config`).
  - Version caps and auto-updater killswitches.
  - Security gates for remote managed settings.
- **User Attributes**: Sends `deviceId`, `sessionId`, `organizationUUID`, `accountUUID`, `email`, `subscriptionType`, etc.

## 4. Remote Managed Settings (Enterprise Configuration)

**File**: `src/services/remoteManagedSettings/index.ts`

- **Endpoint**: `{BASE_API_URL}/api/claude_code/settings`.
- **Behavior**: Delivers enterprise-specific configurations; supports ETag/304 caching with hourly background polling.
- **Security**: Prompts the user for confirmation if changes include "dangerous settings."
- **Eligibility**: Available to all API key users; limited to Enterprise/C4E/Team for OAuth users.
- **Fail-Open**: Uses local cache on failure; skips if no cache is available.

## 5. Settings Sync

**File**: `src/services/settingsSync/index.ts`

- **Endpoint**: `{BASE_API_URL}/api/claude_code/user_settings`.
- **Behavior**: CLI uploads local settings/memory to the remote server; CCR mode downloads from the remote.
- **Synchronized Content**: `userSettings`, `userMemory`, `projectSettings`, and `projectMemory`.
- **Feature Gates**: `UPLOAD_USER_SETTINGS` / `DOWNLOAD_USER_SETTINGS`.
- **File Limits**: 500KB per file.

## 6. OpenTelemetry Third-Party Telemetry

**File**: `src/utils/telemetry/instrumentation.ts`

- **Behavior**: Full OTEL SDK initialization supporting metrics, logs, and traces.
- **Protocols**: gRPC / http-json / http-protobuf (via `OTEL_EXPORTER_OTLP_PROTOCOL`).
- **Exporters**: Console, OTLP, or Prometheus.
- **Activation**: `CLAUDE_CODE_ENABLE_TELEMETRY=1`.
- **Enhanced Tracing**: Enabled via `feature('ENHANCED_TELEMETRY_BETA')` and the `enhanced_telemetry_beta` GrowthBook gate.

## 7. BigQuery Metrics Exporter (Internal Metrics)

**File**: `src/utils/telemetry/bigqueryExporter.ts`

- **Endpoint**: `https://api.anthropic.com/api/claude_code/metrics`.
- **Behavior**: Periodically (5-minute intervals) exports OTel metrics to internal BigQuery.
- **Eligibility**: API customers and C4E/Team subscribers.
- **Organization-Level Opt-out**: Checked via the `checkMetricsEnabled()` API.

## 8. Organization-Level Metrics Opt-out Query

**File**: `src/services/api/metricsOptOut.ts`

- **Endpoint**: `https://api.anthropic.com/api/claude_code/organizations/metrics_enabled`.
- **Behavior**: Queries whether an organization has enabled metrics; implements a two-level cache (1h memory, 24h disk).

## 9. Startup Profiling

**File**: `src/utils/startupProfiler.ts`

- **Behavior**: Samples startup performance data (100% for Anthropic internal, 0.5% for external users) reported via `tengu_startup_perf`.
- **Verbose Mode**: `CLAUDE_CODE_PROFILE_STARTUP=1` outputs a full performance report to a file.

## 10. Beta Session Tracing

**File**: `src/utils/telemetry/betaSessionTracing.ts`

- **Behavior**: Detailed debugging traces including system prompts, model output, and tool schemas.
- **Activation**: `ENABLE_BETA_TRACING_DETAILED=1` and `BETA_TRACING_ENDPOINT`.
- **External Users**: Automatically enabled in SDK/headless modes; requires the `tengu_trace_lantern` GrowthBook gate in interactive modes.

## 11. Bridge Poll Config

**File**: `src/bridge/pollConfig.ts`

- **Behavior**: Fetches bridge polling intervals from GrowthBook (`tengu_bridge_poll_interval_config`) for single and multi-session modes.

## 12. Plugin/MCP Telemetry

**File**: `src/utils/plugins/fetchTelemetry.ts`

- **Behavior**: Logs network requests for plugin/marketplace actions (install counts, clones, pulls).
- **Event**: `tengu_plugin_remote_fetch` containing host (sanitized), outcome, and duration.

---

## Global Disabling Methods

```bash
# Disable all telemetry (Datadog + 1P + surveys)
DISABLE_TELEMETRY=1

# Disable all non-essential network traffic (auto-updater, grove, release notes, etc.)
CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1

# Automatic disabling when using 3P providers
CLAUDE_CODE_USE_BEDROCK=1  # or VERTEX/FOUNDRY
```

`src/utils/privacyLevel.ts` is the central control point, managing three levels: `default`, `no-telemetry`, and `essential-traffic`.

---

## Data Flow Architecture

```
User Action → logEvent()
               ↓
          sink.ts (Routing Layer)
            ↙        ↘
   trackDatadogEvent()   logEventTo1P()
           ↓                      ↓
   Datadog HTTP API     OTel BatchLogRecordProcessor
   (us5.datadoghq.com)       ↓
                    FirstPartyEventLoggingExporter
                             ↓
                    api.anthropic.com/api/event_logging/batch
                             ↓
                    BigQuery (ClaudeCodeInternalEvent proto)
```

GrowthBook acts as an independent channel, driving the toggles and configurations for both sinks.
