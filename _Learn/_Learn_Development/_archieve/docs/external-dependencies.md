# Claude Code Remote Server Dependencies

> This document lists the remote services and endpoints that Claude Code explicitly communicates with. Local services, npm package dependencies, and URLs used for display purposes are not included.

## Overview Table

| # | Service | Remote Endpoint | Protocol | Status |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Anthropic API | `api.anthropic.com` | HTTPS | Enabled by default |
| 2 | AWS Bedrock | `bedrock-runtime.*.amazonaws.com` | HTTPS | Requires `CLAUDE_CODE_USE_BEDROCK=1` |
| 3 | Google Vertex AI | `{region}-aiplatform.googleapis.com` | HTTPS | Requires `CLAUDE_CODE_USE_VERTEX=1` |
| 4 | Azure Foundry | `{resource}.services.ai.azure.com` | HTTPS | Requires `CLAUDE_CODE_USE_FOUNDRY=1` |
| 5 | OAuth (Anthropic) | `platform.claude.com`, `claude.com`, `claude.ai` | HTTPS | On user login |
| 6 | GrowthBook | `api.anthropic.com` (remoteEval) | HTTPS | Enabled by default |
| 7 | Sentry | Configurable (`SENTRY_DSN`) | HTTPS | Requires environment variable |
| 8 | Datadog | Configurable (`DATADOG_LOGS_ENDPOINT`) | HTTPS | Requires environment variable |
| 9 | OpenTelemetry | Configurable (`OTEL_EXPORTER_OTLP_ENDPOINT`) | gRPC/HTTP | Requires environment variable |
| 10 | 1P Event Logging | `api.anthropic.com/api/event_logging/batch` | HTTPS | Enabled by default |
| 11 | BigQuery Metrics | `api.anthropic.com/api/claude_code/metrics` | HTTPS | Enabled by default |
| 12 | MCP Proxy | `mcp-proxy.anthropic.com` | HTTPS+WS | When using MCP tools |
| 13 | MCP Registry | `api.anthropic.com/mcp-registry` | HTTPS | When querying MCP servers |
| 14 | Web Search | `www.bing.com`, `search.brave.com` | HTTPS | WebSearch tool (`WEB_SEARCH_ADAPTER`) |
| 15 | GCS (Updates) | `storage.googleapis.com` | HTTPS | Version checks |
| 16 | GitHub Raw | `raw.githubusercontent.com` | HTTPS | Changelogs and statistics |
| 17 | Chrome Bridge | `bridge.claudeusercontent.com` | WSS | Chrome integration |
| 18 | CCR Upstream Proxy | `api.anthropic.com` | WS | CCR remote sessions |
| 19 | Voice STT | `api.anthropic.com/api/ws/...` | WSS | Voice Mode |
| 20 | Desktop Download | `claude.ai/api/desktop/...` | HTTPS | Download guidance |

---

## Detailed Explanations

### 1. Anthropic Messages API
The core LLM reasoning service for sending conversation messages and receiving streaming responses.
- **Endpoint**: `https://api.anthropic.com` (Production) / `https://api-staging.anthropic.com` (Staging).
- **Override**: `ANTHROPIC_BASE_URL` environment variable.
- **Auth**: API Key or OAuth Token.
- **Files**: `src/services/api/client.ts`, `src/services/api/claude.ts`.

### 2. AWS Bedrock
- **Endpoint**: `bedrock-runtime.{region}.amazonaws.com`.
- **Auth**: AWS credential chain or `AWS_BEARER_TOKEN_BEDROCK`.
- **Files**: `src/services/api/client.ts:153-190`, `src/utils/aws.ts`.

### 3. Google Vertex AI
- **Endpoint**: `{region}-aiplatform.googleapis.com`.
- **Auth**: `GoogleAuth` with `cloud-platform` scope.
- **Files**: `src/services/api/client.ts:221-298`.

### 4. Azure Foundry
- **Endpoint**: `https://{resource}.services.ai.azure.com/anthropic/v1/messages`.
- **Auth**: API Key or Azure AD `DefaultAzureCredential`.
- **Files**: `src/services/api/client.ts:191-220`.

### 5. OAuth
OAuth 2.0 + PKCE authorization code flow.
- **Endpoints**:
  - `https://platform.claude.com/oauth/authorize`: Authorization page.
  - `https://claude.com/cai/oauth/authorize`: Claude.ai authorization.
  - `https://platform.claude.com/v1/oauth/token`: Token exchange.
  - `https://api.anthropic.com/api/oauth/claude_cli/create_api_key`: API key creation.
  - `https://api.anthropic.com/api/oauth/claude_cli/roles`: Role retrieval.
  - `https://claude.ai/oauth/claude-code-client-metadata`: MCP client metadata.
- **Files**: `src/constants/oauth.ts`, `src/services/oauth/`.

### 6. GrowthBook (Feature Flags)
- **Endpoint**: `https://api.anthropic.com/` (remoteEval mode) or `CLAUDE_GB_ADAPTER_URL`.
- **SDK Keys**: `sdk-zAZezfDKGoZuXXKe` (External), `sdk-xRVcrliHIlrg4og4` (Ant Prod), `sdk-yZQvlplybuXjYh6L` (Ant Dev).
- **Files**: `src/services/analytics/growthbook.ts`, `src/constants/keys.ts`.

### 7. Sentry (Error Tracking)
- **Activation**: Set `SENTRY_DSN` (unconfigured by default).
- **Behavior**: Reports errors only; automatically filters sensitive headers.
- **Files**: `src/utils/sentry.ts`.

### 8. Datadog (Logs)
- **Activation**: Requires both `DATADOG_LOGS_ENDPOINT` and `DATADOG_API_KEY`.
- **Files**: `src/services/analytics/datadog.ts`.

### 9. OpenTelemetry Collector
- **Activation**: `CLAUDE_CODE_ENABLE_TELEMETRY=1` or `OTEL_*` environment variables.
- **Protocols**: gRPC / HTTP / Protobuf (supports OTLP and Prometheus exports).
- **Files**: `src/utils/telemetry/instrumentation.ts`.

### 10. 1P Event Logging (Internal Events)
- **Endpoint**: `https://api.anthropic.com/api/event_logging/batch`.
- **Protocol**: Batch export (10s intervals, 200 events per batch).
- **Files**: `src/services/analytics/firstPartyEventLoggingExporter.ts`.

### 11. BigQuery Metrics
- **Endpoint**: `https://api.anthropic.com/api/claude_code/metrics`.
- **Files**: `src/utils/telemetry/bigqueryExporter.ts`.

### 12. MCP Proxy
Proxy for Anthropic-hosted MCP servers.
- **Endpoint**: `https://mcp-proxy.anthropic.com/v1/mcp/{server_id}`.
- **Auth**: Claude.ai OAuth tokens.
- **Files**: `src/services/mcp/client.ts`, `src/constants/oauth.ts`.

### 13. MCP Registry
Retrieves the official list of MCP servers.
- **Endpoint**: `https://api.anthropic.com/mcp-registry/v0/servers?version=latest&visibility=commercial`.
- **Files**: `src/services/mcp/officialRegistry.ts`.

### 14. Web Search
The WebSearch tool scrapes Bing search results or uses the Brave LLM Context API; the backend can be toggled via `WEB_SEARCH_ADAPTER=bing|brave`.
- **Bing Endpoint**: `https://www.bing.com/search?q={query}&setmkt=en-US`.
- **Brave Endpoint**: `https://api.search.brave.com/res/v1/llm/context?q={query}`.
- **Files**:
  - `packages/builtin-tools/src/tools/WebSearchTool/adapters/bingAdapter.ts`
  - `packages/builtin-tools/src/tools/WebSearchTool/adapters/braveAdapter.ts`

Domain blocklist queries:
- **Endpoint**: `https://api.anthropic.com/api/web/domain_info?domain={domain}`.
- **Files**: `packages/builtin-tools/src/tools/WebFetchTool/utils.ts`.

### 15. Google Cloud Storage (Auto-Updater)
- **Endpoint**: `https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases`.
- **Files**: `src/utils/autoUpdater.ts`.

### 16. GitHub Raw Content
- **Endpoints**:
  - `https://raw.githubusercontent.com/anthropics/claude-code/refs/heads/main/CHANGELOG.md`
  - `https://raw.githubusercontent.com/anthropics/claude-plugins-official/refs/heads/stats/stats/plugin-installs.json`
- **Files**: `src/utils/releaseNotes.ts`, `src/utils/plugins/installCounts.ts`.

### 17. Claude in Chrome Bridge
- **Endpoint**: `wss://bridge.claudeusercontent.com` (Production) / `wss://bridge-staging.claudeusercontent.com` (Staging).
- **Files**: `src/utils/claudeInChrome/mcpServer.ts`.

### 18. CCR Upstream Proxy
- **Endpoint**: `ws://api.anthropic.com/v1/code/upstreamproxy/ws`.
- **Activation**: `CLAUDE_CODE_REMOTE=1` and `CCR_UPSTREAM_PROXY_ENABLED=1`.
- **Files**: `src/upstreamproxy/upstreamproxy.ts`.

### 19. Voice STT
- **Endpoint**: `wss://api.anthropic.com/api/ws/...`.
- **Files**: `src/services/voiceStreamSTT.ts`.

### 20. Desktop App Download
- **Endpoints**:
  - Windows: `https://claude.ai/api/desktop/win32/x64/exe/latest/redirect`.
  - macOS: `https://claude.ai/api/desktop/darwin/universal/dmg/latest/redirect`.
- **Files**: `src/components/DesktopHandoff.tsx`.

---

## Summary of Anthropic API Helper Endpoints

The following endpoints are hosted on `api.anthropic.com`, categorized by functionality:

| Endpoint Path | Purpose | File |
| :--- | :--- | :--- |
| `/api/event_logging/batch` | Batch event reporting. | `firstPartyEventLoggingExporter.ts` |
| `/api/claude_code/metrics` | BigQuery metrics export. | `bigqueryExporter.ts` |
| `/api/oauth/claude_cli/create_api_key` | API key creation. | `oauth.ts` |
| `/api/oauth/claude_cli/roles` | Retrieval of user roles. | `oauth.ts` |
| `/api/oauth/accounts/grove` | Notification settings. | `grove.ts` |
| `/api/web/domain_info?domain={}` | Domain security checks. | `WebFetchTool/utils.ts` |
| `/api/claude_code/settings` | Settings synchronization. | `settingsSync/index.ts` |
| `/api/claude_code/managed_settings` | Managed enterprise settings. | `remoteManagedSettings/index.ts` |
| `/api/claude_code/team_memory?repo={}` | Team memory synchronization. | `teamMemorySync/index.ts` |
| `/api/auth/trusted_devices` | Trusted device registration. | `bridge/trustedDevice.ts` |
| `/mcp-registry/v0/servers` | MCP server registry. | `officialRegistry.ts` |
| `/v1/files` | File uploads/downloads. | `filesApi.ts` |
| `/v1/sessions/{id}/events` | Session history. | `sessionHistory.ts` |
| `/v1/code/triggers` | Remote triggers. | `RemoteTriggerTool.ts` |
| `/v1/organizations/{id}/mcp_servers` | Organization MCP config. | `claudeai.ts` |

## Non-Anthropic Remote Domains Summary

| Domain | Service | Protocol |
| :--- | :--- | :--- |
| `bedrock-runtime.*.amazonaws.com` | AWS Bedrock | HTTPS |
| `{region}-aiplatform.googleapis.com` | Google Vertex AI | HTTPS |
| `{resource}.services.ai.azure.com` | Azure Foundry | HTTPS |
| `www.bing.com` | Bing Search | HTTPS |
| `search.brave.com` | Brave Search | HTTPS |
| `storage.googleapis.com` | Auto-Updater | HTTPS |
| `raw.githubusercontent.com` | Changelog / Plugin Stats | HTTPS |
| `bridge.claudeusercontent.com` | Chrome Bridge | WSS |
| `platform.claude.com` | OAuth Auth Page | HTTPS |
| `claude.com` / `claude.ai` | OAuth / Downloads | HTTPS |
| `claude.fedstart.com` | FedStart OAuth | HTTPS |
