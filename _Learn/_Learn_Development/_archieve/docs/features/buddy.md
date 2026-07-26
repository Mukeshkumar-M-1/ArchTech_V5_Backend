---
title: "Buddy Virtual Pet System"
description: "Buddy is a virtual pet companion in the CLI that can be hatched and interacted with via the /buddy command, accompanying you next to the input box while you write code."
keywords: ["buddy", "pet", "companion", "virtual pet"]
---

## Overview

Buddy is a built-in virtual pet system in Claude Code. By using the `/buddy` command in the REPL, you can hatch a randomly generated pet companion that appears next to the input box, accompanying you during your coding process.

> Feature Flag: `FEATURE_BUDDY=1`

## Activation Method

```bash
FEATURE_BUDDY=1 bun run dev
```

Hatching window: When starting between April 1st and 7th, 2026, a rainbow-colored `/buddy` hint will be displayed at the top of the REPL. After April 7th, the command remains available but will no longer be automatically prompted.

## Commands

| Command | Description |
| :--- | :--- |
| `/buddy` | View current pet information and attributes. |
| `/buddy hatch` | Hatch a new pet (for first-time use). |
| `/buddy rehatch` | Randomly regenerate a pet (replaces the existing one). |
| `/buddy pet` | Pet the companion, triggering a heart animation. |
| `/buddy mute` | Mute the pet (hide it). |
| `/buddy unmute` | Unmute the pet. |

## Pet Attributes

### Species (18 Types)

| | | | |
| :--- | :--- | :--- | :--- |
| Duck | Goose | Blob | Cat |
| Dragon | Octopus | Owl | Penguin |
| Turtle | Snail | Ghost | Axolotl |
| Capybara | Cactus | Robot | Rabbit |
| Mushroom | Chonk | | |

### Rarity

| Rarity | Stars | Weight |
| :--- | :--- | :--- |
| Common | ★ | 60% |
| Uncommon | ★★ | 25% |
| Rare | ★★★ | 10% |
| Epic | ★★★★ | 4% |
| Legendary | ★★★★★ | 1% |

Rarity is determined randomly based on a seed during hatching. There is an extremely low probability of a "Shiny" variant appearing.

### Property Values

Each pet has 5 attributes (scored from 0-100):

- **DEBUGGING** — Debugging capability.
- **PATIENCE** — Level of patience.
- **CHAOS** — Index of chaos.
- **WISDOM** — Wisdom value.
- **SNARK** — Level of snarkiness.

### Appearance

Each pet also has random appearance accessories:

- **Eyes**: `·` `✦` `×` `◉` `@` `°`
- **Hats**: none, crown, tophat, propeller, halo, wizard, beanie, tinyduck

## Data Storage

Pet information is stored in the `companion` field of `~/.claude.json`. A pet's appearance attributes (species, rarity, property values, etc.) are deterministically generated based on a hash of the user ID, meaning rarity cannot be manipulated by editing the configuration file.

## Related Source Files

| File | Description |
| :--- | :--- |
| `src/commands/buddy/index.ts` | `/buddy` command registration. |
| `src/commands/buddy/buddy.ts` | `/buddy` command handling. |
| `src/buddy/companion.ts` | Pet generation and loading. |
| `src/buddy/companionReact.ts` | Pet reaction system (triggered after each REPL query turn). |
| `src/buddy/types.ts` | Type definitions (species, rarity, attributes). |
| `src/buddy/sprites.ts` | Terminal pixel art rendering. |
| `src/buddy/CompanionSprite.tsx` | React component (displayed next to the input box). |
| `src/buddy/CompanionCard.tsx` | Pet information card (displayed when `/buddy` is called without arguments). |
| `src/buddy/useBuddyNotification.tsx` | Startup notification hint. |
| `src/buddy/prompt.ts` | Pet-related prompt templates. |
