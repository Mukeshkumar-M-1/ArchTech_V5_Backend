# Claude Code Best V5 (CCB)

[![GitHub Stars](https://img.shields.io/github/stars/claude-code-best/claude-code?style=flat-square&logo=github&color=yellow)](https://github.com/claude-code-best/claude-code/stargazers)
[![GitHub Contributors](https://img.shields.io/github/contributors/claude-code-best/claude-code?style=flat-square&color=green)](https://github.com/claude-code-best/claude-code/graphs/contributors)
[![GitHub Issues](https://img.shields.io/github/issues/claude-code-best/claude-code?style=flat-square&color=orange)](https://github.com/claude-code-best/claude-code/issues)
[![GitHub License](https://img.shields.io/github/license/claude-code-best/claude-code?style=flat-square)](https://github.com/claude-code-best/claude-code/blob/main/LICENSE)
[![Last Commit](https://img.shields.io/github/last-commit/claude-code-best/claude-code?style=flat-square&color=blue)](https://github.com/claude-code-best/claude-code/commits/main)
[![Bun](https://img.shields.io/badge/runtime-Bun-black?style=flat-square&logo=bun)](https://bun.sh/)
[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?style=flat-square&logo=discord)](https://discord.gg/uApuzJWGKX)

> Which Claude do you like? The open source one is the best.

Lao A (Anthropic) official [Claude Code](https://docs.anthropic.com/en/docs/claude-code) source code decompilation/reverse restoration project of CLI tool. The goal is to reproduce most of the functions and engineering capabilities of Claude Code (the question is that Lafayette has already paid). Although it is difficult to stretch, it is called CCB (step on the back)... Moreover, we have implemented an enterprise version or features that require logging in to a Claude account to achieve inclusive technology.

> We will standardize lint on the entire code repository during the May Day period. PRs submitted during this period may have a lot of conflicts, so please try to submit big features before then.

[Documents are here, support PR submission](https://ccb.agent-aura.top/) | [Photo files are here](./Friends.md) | [Discord group](https://discord.gg/uApuzJWGKX)

| Features                              | Description                                                                                                                                                                                                                           | Documentation                                                                                                                                          |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Claude Group Control Technology**   | Pipe IPC multi-instance collaboration: same-machine main/sub automatic orchestration + LAN cross-machine zero-configuration discovery and communication, `/pipes` selection panel + `Shift+↓` interaction + message broadcast routing | [Pipe IPC](https://ccb.agent-aura.top/docs/features/uds-inbox) / [LAN](https://ccb.agent-aura.top/docs/features/lan-pipes)                             |
| **ACP protocol first-class support**  | Supports access to IDEs such as Zed and Cursor, and supports session recovery, Skills, and permission bridging                                                                                                                        | [Documentation](https://ccb.agent-aura.top/docs/features/acp-zed)                                                                                      |
| **Remote Control private deployment** | Docker self-hosted remote interface, you can watch CC on your mobile phone                                                                                                                                                            | [Documentation](https://ccb.agent-aura.top/docs/features/remote-control-self-hosting)                                                                  |
| **Langfuse Monitoring**               | Enterprise-level Agent monitoring, you can clearly see the details of each agent loop, and can be converted into a data set with one click                                                                                            | [Document](https://ccb.agent-aura.top/docs/features/langfuse-monitoring)                                                                               |
| **Web Search**                        | Built-in web search tool, supports bing and brave searches                                                                                                                                                                            | [Documentation](https://ccb.agent-aura.top/docs/features/web-browser-tool)                                                                             |
| **Poor Mode**                         | Poor mode, turns off memory retrieval and typing suggestions, greatly reducing concurrent requests                                                                                                                                    | /poor can be switched                                                                                                                                  |
| **Channels channel notification**     | MCP server pushes external messages to sessions (Feishu/Slack/Discord/WeChat, etc.), `--channels plugin:name@marketplace` is enabled                                                                                                  | [Document](https://ccb.agent-aura.top/docs/features/channels)                                                                                          |
| **Custom model provider**             | OpenAI/Anthropic/Gemini/Grok compatible (`/login`)                                                                                                                                                                                    | [Documentation](https://ccb.agent-aura.top/docs/features/all-features-guide)                                                                           |
| Voice Mode                            | Voice input, supports Doubao language input (`/voice doubao`)                                                                                                                                                                         | [Documentation](https://ccb.agent-aura.top/docs/features/voice-mode)                                                                                   |
| Computer Use                          | Screenshot, keyboard and mouse control                                                                                                                                                                                                | [Documentation](https://ccb.agent-aura.top/docs/features/computer-use)                                                                                 |
| Chrome Use                            | Browser automation, form filling, data scraping                                                                                                                                                                                       | [Self-hosted](https://ccb.agent-aura.top/docs/features/chrome-use-mcp) [Native version](https://ccb.agent-aura.top/docs/features/claude-in-chrome-mcp) |
| Sentry                                | Enterprise-level error tracking                                                                                                                                                                                                       | [Documentation](https://ccb.agent-aura.top/docs/internals/sentry-setup)                                                                                |
| GrowthBook                            | Enterprise-level feature switch                                                                                                                                                                                                       | [Document](https://ccb.agent-aura.top/docs/internals/growthbook-adapter)                                                                               |
| /dream memory organization            | Automatically organize and optimize memory files                                                                                                                                                                                      | [Documentation](https://ccb.agent-aura.top/docs/features/auto-dream)                                                                                   |

- 🚀 [Want to start the project](#-Quick Start Source Code Version)
- 🐛 [Want to debug the project](#vs-code-debug)
- 📖[Want to learn a project](#teach-me-Learning project)## ⚡ Quick start (installation version)

No need to clone the repository, download it from NPM and use it directly

```sh
npm i -g claude-code-best

# There are many problems with bun installation, so npm installation is recommended.
# bun i -g claude-code-best
# bun pm -g trust claude-code-best @claude-code-best/mcp-chrome-bridge

ccb # Open claude code with nodejs
ccb-bun # Open in bun form
ccb update # Update to the latest version
CLAUDE_BRIDGE_BASE_URL=https://remote-control.claude-code-best.win/ CLAUDE_BRIDGE_OAUTH_TOKEN=test-my-key ccb --remote-control # We have self-deployed remote control
```

> **Installation/update failed? ** First `npm rm -g claude-code-best` to clean up the old version, then `npm i -g claude-code-best@latest`. If it still fails, specify the version number: `npm i -g claude-code-best@<version number>`

## ⚡ Quick start (source version)

### ⚙️ Environmental requirements

You must have the latest version of bun, otherwise there will be a bunch of weird bugs!!! bun upgrade!!!

- 📦 [Bun](https://bun.sh/) >= 1.3.11

**Install Bun:**

```bash
# Linux and macOS
curl -fsSL https://bun.sh/install | bash

# Windows (PowerShell)
powershell -c "irm bun.sh/install.ps1 | iex"
```

**Post-installation operations:**

1. **Let the current terminal recognize the `bun` command**

The installation script will write `~/.bun/bin` into the corresponding shell configuration file. The default zsh environment on macOS will usually see:

```text
Added "~/.bun/bin" to $PATH in "~/.zshrc"
```

You can restart the current shell as prompted by the installation script:

```bash
exec /bin/zsh
```

If you use bash, reload the bash configuration:

```bash
source ~/.bashrc
```

Windows PowerShell users simply close and reopen PowerShell.

2. **Verify whether Bun is available**

```bash
bun --help
bun --version
```

3. **If Bun is already installed, update to the latest version**

```bash
bun upgrade
```

- ⚙️ Conventional way to configure CC, each major provider has its own configuration method
### 📍 Command execution location 

- Commands to install or check Bun can be executed in any directory: 
`curl -fsSL https://bun.sh/install | bash`, `bun --help`, `bun --version`, `bun upgrade` 
- When installing the dependencies of this project, starting the development mode, and building the project, you must first enter the root directory of this warehouse, which is the directory containing `package.json`. 

### 📥 Installation 

```bash 
cd /path/to/claude-code 
bun install 
``` 

### ▶️ Run 

```bash 
# Development mode, if you see the version number 888, it means it is correct 
bun run dev 

# Build 
bun run build 
``` 

The build uses code splitting multi-file packaging (`build.ts`), and the product is output to the `dist/` directory (entry `dist/cli.js` + about 450 chunk files). 

The built version can be started by both bun and node. You can start it directly by publishing it to a private source. 

If you encounter a bug, please raise an issue directly and we will resolve it first. 

### 👤 Newcomer configuration /login 

After running for the first time, enter the `/login` command in the REPL to enter the login configuration interface, and select **Anthropic Compatible** to connect to third-party API compatible services (no official Anthropic account is required). 
Select the columns corresponding to OpenAI and Gemini to support the corresponding protocols. 

Required fields: 

| 📌 Field | 📝 Description | 💡 Example | 
| -------------------------- | ------------- | ---------------------------- | 
| Base URL | API service address | `https://api.example.com/v1` | 
| API Key | Authentication Key | `sk-xxx` | 
| Haiku Model | Quick Model ID | `claude-haiku-4-5-20251001` | 
| Sonnet Model | Equilibrium model ID | `claude-sonnet-4-6` | 
| Opus Model | High performance model ID | `claude-opus-4-6` | 

- ⌨️ **Tab / Shift+Tab** to switch fields, **Enter** to confirm and jump to the next one, press Enter to save the last field 

> ℹ️ Supports all Anthropic API compatible services (such as OpenRouter, AWS Bedrock proxy, etc.) as long as the interface is compatible with the Messages API. 

## Feature Flags 

All function switches are enabled through the `FEATURE_<FLAG_NAME>=1` environment variable, for example: 

```bash 
FEATURE_BUDDY=1 FEATURE_FORK_SUBAGENT=1 bun run dev 
``` 

Detailed descriptions of each Feature can be found in the [`docs/features/`](docs/features/) directory. Submissions are welcome.
## VS Code debugging 

TUI (REPL) mode requires a real terminal and cannot start debugging directly through VS Code launch. Use **attach mode**: 

### Steps 

1. **Start the inspect service in the terminal**: 

```bash 
bun run dev:inspect 
``` 

An address similar to `ws://localhost:8888/xxxxxxxx` will be output. 

2. **VS Code attaches the debugger**: 
- Breakpoints in `src/` files 
- F5 → Select **"Attach to Bun (TUI debug)"** 

## Teach Me Learning Project 

We have added a new teach-me skills to help you understand any module of this project through question-and-answer guidance. (Adjusted from [sigma skill](https://github.com/sanyuan0704/sanyuan-skills)) 

```bash 
# Enter directly in the REPL 
/teach-me Claude Code Architecture 
/teach-me React Ink terminal rendering --level beginner 
/teach-me Tool system --resume 
``` 

### What it can do 

- **Diagnostic Level** — automatically assesses your mastery of relevant concepts, skipping known ones and focusing on weak ones 
- **Construct a learning path** — Break down the topic into 5-15 atomic concepts, and gradually advance them in order of dependency 
- **Socratic Questioning** — use options to guide thinking rather than giving direct answers 
- **Misconception Tracking** — uncover and correct deep-seated misconceptions 
- **Resume from breakpoint** — `--resume` Continue from the last progress 

### Learning record 

Learning progress is saved in the `.claude/skills/teach-me/` directory, supporting cross-topic learner profiles. 

## Related documents and websites 

- **Online Documentation (Mintlify)**: [ccb.agent-aura.top](https://ccb.agent-aura.top/) — The document source code is located in the [`docs/`](docs/) directory. PR submissions are welcome 
- **DeepWiki**: [https://deepwiki.com/claude-code-best/claude-code](https://deepwiki.com/claude-code-best/claude-code) 

## Contributors 

<a href="https://github.com/claude-code-best/claude-code/graphs/contributors"> 
<img src="contributors.svg" alt="Contributors" /> 
</a> 

## Star History 

<a href="https://www.star-history.com/?repos=claude-code-best%2Fclaude-code&type=date&legend=top-left"> 
<picture> 
<source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/image?repos=claude-code-best/claude-code&type=date&theme=dark&legend=top-left" /> 
<source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/image?repos=claude-code-best/claude-code&type=date&legend=top-left" /> 
<img alt="Star History Chart" src="https://api.star-history.com/image?repos=claude-code-best/claude-code&type=date&legend=top-left" /> 
</picture> 
</a> 

## Acknowledgments 

- [doubaoime-asr](https://github.com/starccy/doubaoime-asr) — Doubao ASR speech recognition SDK provides a voice input solution for Voice Mode without Anthropic OAuth 

## License 

This project is for study and research purposes only. All rights to Claude Code belong to [Anthropic](https://www.anthropic.com/).