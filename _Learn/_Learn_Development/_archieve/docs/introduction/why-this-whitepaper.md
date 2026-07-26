---
title: "Why This Whitepaper - Reverse Engineering Analysis of Claude Code"
description: "Whitepaper of reverse engineering analysis on Anthropic's official Claude Code CLI. In-depth analysis of runtime behavior and source code structure through decompiling a TypeScript single-file bundle."
keywords: ["Claude Code", "Reverse Engineering", "Whitepaper", "Decompilation", "TypeScript"]
---

## What This Whitepaper Is

This is a **reverse engineering analysis** of the official **Claude Code CLI** released by Anthropic.

The source code has been processed through reverse engineering (reverse engineering a TypeScript single-file bundle), preserving core functional modules but containing numerous `unknown`/`never`/`{}` type errors—these do not affect execution in the Bun runtime, but they mean our analysis is based on runtime behavior + remaining source code structure, rather than the original source code.

**This is NOT:**

- Official documentation or user tutorial
- API reference manual
- A feature sales pitch for Claude Code

**This IS:**

- An architectural deconstruction of a production-grade agentic system
- The "why" behind each design decision
- Reusable engineering patterns: agentic loop, tool abstraction, context engineering, and security depth-of-defense

## The Most Ingenious Design Decisions During Reverse Engineering

### 1. Self-healing Capability of the Agentic Loop

The core loop implemented in `src/query.ts` is not a simple "send request → receive response." It is a **self-healing state machine**:

- API returns an error (rate limiting, token limit exceeded) → automatic retry/fallback.
- Tool execution timeout → backgrounding + notification mechanism.
- Conversation too long triggers compaction → seamless continuation after compressing history.
- User interruption → generates a `UserInterruptionMessage` so the AI understands what happened.

This is not "if-else stacking," but letting the AI itself decide the next step based on context—even when unexpected things happen.

### 2. Tiered Strategy of Context Engineering

AI has no true "memory"; Claude Code creates this illusion through careful layering:

| Layer | Mechanism | Persistence |
| ----------------- | ------------------------------- | ------------------ |
| **System Prompt** | Project structure, git status, CLAUDE.md | Reconstructed each turn |
| **Dialogue History** | Complete User/Assistant/Tool messages | Within session |
| **Compaction** | Automatically compresses long dialogues into summaries | Replaces original messages after compression |
| **Memory Files** | Persistent notes across sessions | Permanent (user-controlled) |
| **File History** | File modification timestamp snapshots | Within session |

The strategy when `src/context.ts` assembles the System Prompt is: **place static content first, dynamic content last**—this utilizes the API's caching mechanism; cached tokens can be reused when the prefix remains unchanged.

### 3. Dual-track Permission System of the Tool System

`packages/builtin-tools/src/tools/BashTool/shouldUseSandbox.ts` demonstrates a sophisticated dual security model:

- **Application Layer**: Permission rules decide "can it execute" (whitelist/blacklist/user confirmation).
- **OS Layer**: Sandbox decides "what can it do when executing" (file system/network/process isolation).

The trust assumptions for the two layers are different: the application layer trusts user configuration, while the OS layer trusts nothing. Even if the AI bypasses application-layer permissions (theoretically impossible, but defense-in-depth), the OS-layer sandbox still limits actual harm.

### 4. Global Switch of Feature Flags

A single line of code in `src/entrypoints/cli.tsx` determines the behavior of the entire system:

```typescript
const feature = (_name: string) => false;
```

All `feature('FLAG_NAME')` calls return `false`—this means internal experimental features at Anthropic (COORDINATOR_MODE, KAIROS, PROACTIVE, etc.) are all disabled. In official builds, these flags are injected at compile-time via Bun's `bun:bundle`, and different user groups see different features.

This is a **progressive release architecture**: the same codebase controls feature visibility through feature flags, without the need to maintain multiple branches.

### 5. Tiered Strategy of Compaction

`src/services/compact/` implements three compression strategies:

- **Micro-compact**: Truncates results when a single tool output is too long.
- **Auto-compact**: Automatically compresses history when dialogue tokens approach the limit.
- **Reactive-compact**: Emergency compression and retry when the API returns a token limit error.

This is not simply "chopping off old messages"—it uses the AI itself to summarize the previous conversation, preserving semantic information. A `TombstoneMessage` is inserted after compression to mark the boundary.

## Reading Roadmap

Recommended reading order, with each chapter solving a core problem:

```
What is Claude Code (What you are reading) ← Establish intuition
    │
    ├── Architecture Panorama ← Five-layer architecture + data flow
    │
    ├── Security System ← Trust and control
    │   ├── Permission Model ← Application-layer security
    │   ├── Sandbox Mechanism ← OS-layer security
    │   └── Plan Mode ← User-led mode
    │
    ├── Dialogue Engine ← How the AI thinks
    │   ├── Agentic Loop ← Core loop
    │   ├── Streaming Response ← Real-time communication
    │   └── Multi-turn Dialogue ← Context management
    │
    ├── Context Engineering ← Memory and budget
    │   ├── System Prompt ← Context assembly
    │   ├── Token Budget ← Budget management
    │   └── Project Memory ← Cross-session persistence
    │
    ├── Tool System ← AI's hands
    │   ├── Tool Overview ← Unified interface
    │   ├── Shell Execution ← Bash tools
    │   └── Search and Navigation ← Glob/Grep
    │
    └── Agents and Extensions ← Capability expansion
        ├── Sub-Agents ← Parallel tasks
        ├── Custom Agents ← User-defined
        └── MCP Protocol ← External tool access
```

## Who This Is For

- **AI Agent Developers**: Those who want to understand the architectural patterns of production-grade agentic systems.
- **Security Engineers**: Those interested in the trust model when AI operates in real environments.
- **Tool Builders**: Those currently building similar coding assistants or CLI tools.
- **Curiosity-driven Developers**: Those who want to know "how exactly an AI programming assistant works."
