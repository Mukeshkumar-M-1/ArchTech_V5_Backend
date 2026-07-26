# Channels — External Message Integration

> Startup Parameters: `--channels` / `--dangerously-load-development-channels`
> Status: Feature flag and OAuth restrictions removed; available for immediate use.

## Overview

A Channel is an MCP server that pushes external events into your running Claude Code session, allowing Claude to react even when you are away from the terminal. For detailed usage instructions, please refer to the following documentation:

- **Official Documentation**: [Using Channels to Push Events to Running Sessions](https://code.claude.com/docs/channels)
- **Feishu Plugin**: [claude-code-feishu-channel](https://github.com/whobot-ai/claude-code-feishu-channel) — The first community-developed Feishu Channel plugin, supporting bidirectional messaging, pairing authentication, group chat, and file attachments.

This repository now includes a **built-in WeChat channel**, eliminating the need to install an external marketplace plugin.

## Quick Start

```bash
# Enable channel listening (plugin format)
ccb --channels plugin:feishu@claude-code-feishu-channel

# Enable built-in WeChat channel
ccb weixin login
ccb --channels plugin:weixin@builtin

# Enable channel listening (server format)
ccb --channels server:my-slack-bridge

# Enable multiple channels simultaneously
ccb --channels plugin:feishu@claude-code-feishu-channel --channels server:discord-bot

# Development mode (skips allowlist check, used for testing custom channels)
ccb --dangerously-load-development-channels server:my-custom-channel
```

## Supported Channels

| Channel | Description | Source |
| :--- | :--- | :--- |
| **Telegram** | Official Telegram Bot integration. | `/plugin install telegram@claude-plugins-official` |
| **Discord** | Official Discord Bot integration. | `/plugin install discord@claude-plugins-official` |
| **iMessage** | macOS native messages. | `/plugin install imessage@claude-plugins-official` |
| **Feishu (Lark)** | Bidirectional messaging, group chat, file attachments. | `/plugin install feishu@claude-code-feishu-channel` |
| **WeChat** | Built-in channel; supports QR code login, bidirectional messaging, and file pass-through. | `ccb weixin login` + `ccb --channels plugin:weixin@builtin` |

## Built-in WeChat Channel

### Login

```bash
ccb weixin login
```

The login state can be cleared:

```bash
ccb weixin login clear
```

### Enabling in a Session

```bash
ccb --channels plugin:weixin@builtin
```

### Pairing Authorization

When a message is first received from an unauthorized WeChat user, the weixin channel will reply with a 6-digit pairing code. The operator can execute the following in the terminal:

```bash
ccb weixin access pair <code>
```

Once confirmed, subsequent messages from that WeChat user will be directed to the Claude Code session.

## Related Files

| File | Responsibility |
| :--- | :--- |
| `src/services/mcp/channelNotification.ts` | Channel gating logic and message wrapping. |
| `src/services/mcp/channelAllowlist.ts` | Channel toggles (enabled by default). |
| `src/services/mcp/useManageMCPConnections.ts` | Channel registration within MCP connection management. |
| `src/components/LogoV2/ChannelsNotice.tsx` | Channel status hints displayed at startup. |
| `src/main.tsx` | Parsing of the `--channels` parameter. |
| `src/interactiveHelpers.tsx` | Confirmation dialog for development channels. |

## Reference Links

- [Official Channels Documentation](https://code.claude.com/docs/channels) — Full instructions, security, and Enterprise controls.
- [Feishu Channel Plugin](https://github.com/whobot-ai/claude-code-feishu-channel) — Installation guide, MCP tools, and Skill command reference.
