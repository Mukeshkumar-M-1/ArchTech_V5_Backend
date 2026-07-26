---
title: "Skills System - The Architectural Philosophy of 'Prompt as Capability'"
description: "In-depth analysis of the complete implementation of the Claude Code Skills system: from disk loading, frontmatter parsing, budget-aware description truncation, dual-mode execution (inline/fork), permission allowlisting, conditional activation, dynamic discovery to remote skill loading, revealing the entire Skill lifecycle pipeline."
keywords:
  [
    "Skills",
    "SkillTool",
    "Skill Loading",
    "Frontmatter",
    "whenToUse",
    "allowedTools",
    "fork execution",
    "Dynamic Discovery",
  ]
---

{/* Goal: Reveal the complete pipeline of the Skill system from file to execution */}

## Tool vs Skill: Fundamental Differences

| Feature | Tool | Skill |
| :--- | :--- | :--- |
| **Granularity** | Single atomic operation (read file, execute command) | A complete workflow (code review, create PR) |
| **Trigger Method** | AI's autonomous choice | User `/skill-name` or AI auto-match via `SkillTool` |
| **Nature** | TypeScript execution logic | Declarative encapsulation of **Prompt + Permission Config** |
| **Registration** | `src/tools.ts` → `getTools()` | `src/commands.ts` → `getCommands()` |
| **Executor** | `call()` method of each Tool | `SkillTool.call()` → Two branches (inline / fork) |

The core insight behind Skills: **The key to complex tasks lies not in code logic, but in Prompt quality**. A code review Skill doesn't need a review engine; it just needs to tell the AI "what to review, in what order, and in what format"—Skills encapsulate this "expertise" into reusable Markdown.

## Five Sources of Skills and Loading Pipelines

### 1. Built-in Commands

Hardcoded in the `COMMANDS` memoized array in `src/commands.ts:299`, containing 70+ commands (`/commit`, `/review`, `/compact`, etc.). These are TypeScript modules rather than Markdown, but they implement the same `Command` interface (`src/types/command.ts`).

### 2. Bundled Skills (Compiled-in)

Registered during module initialization via `registerBundledSkill()` (`src/skills/bundledSkills.ts:53`). Key features:

- **Lazy File Extraction**: If a Skill declares `files` (reference files), they are only extracted to a temporary directory (`getBundledSkillExtractDir()`) upon the first call, using `O_NOFOLLOW | O_EXCL` to prevent symbolic link attacks (`safeWriteFile`, line 186).
- **Closure-level memoize**: Concurrent calls share the same extraction promise, avoiding race conditions during writing.
- **Tagged as `source: 'bundled'`**: These enjoy **non-truncatable** privilege within the Prompt budget.

### 3. Disk Skills (`.claude/skills/`)

Loaded by `loadSkillsFromSkillsDir()` (`src/skills/loadSkillsDir.ts:407`), which is the most important loading path:

```
Management Policy: $MANAGED_DIR/.claude/skills/     (policySettings)
User Global: ~/.claude/skills/                      (userSettings)
Project Level: .claude/skills/                      (projectSettings, traverses up to home)
Additional Directories: .claude/skills/ under paths specified by --add-dir
```

**Loading Protocol**: Only recognizes the `skill-name/SKILL.md` directory format; single-file `.md` is no longer supported. The loading flow:

1. `readdir` scans directories → only `isDirectory()` or `isSymbolicLink()` entries are kept.
2. Looks for `SKILL.md` in each subdirectory, skipping if not found.
3. `parseFrontmatter()` parses the YAML header to extract fields like `whenToUse`, `allowedTools`, and `context`.
4. `parseSkillFrontmatterFields()` (line 185) uniformly parses 16 frontmatter fields.
5. `createSkillCommand()` (line 270) constructs the `Command` object.

**De-duplication Mechanism**: Uses `realpath()` to resolve symbolic links into canonical paths (`getFileIdentity`, line 118), preventing duplicate loading via symbolic links or overlapping parent directories.

### 4. MCP Skills (Dynamic Discovery)

Registered via `registerMCPSkillBuilders()`, where prompts from the MCP Server are converted into `Command` objects by `mcpSkillBuilders.ts`. Tagged as `loadedFrom: 'mcp'`.

**Security Boundary**: MCP Skills are **prohibited from executing inline shell commands** (guarded by `loadedFrom !== 'mcp'` in `loadSkillsDir.ts:374`), as remote content is untrusted.

### 5. Legacy Commands (`/commands/` directory)

A backward-compatible format loaded by `loadSkillsFromCommandsDir()` (line 566). Supports both the `SKILL.md` directory format and the single `.md` file format.

## Full Panorama of Frontmatter Fields

A complete frontmatter for a `SKILL.md` file (`parseSkillFrontmatterFields`, line 185):

```yaml
---
name: code-review                    # Display name (overrides directory name)
description: Systematic code review   # Description (or extracted from the first Markdown paragraph)
when_to_use: "User asks to review code or find bugs" # Basis for AI auto-matching
allowed-tools:                       # Tools whitelist
  - Read
  - Grep
  - Glob
argument-hint: "<file-or-directory>" # Argument hint
arguments: [path]                    # Declarative argument names (for $ARGUMENTS replacement)
model: opus                          # Model override
effort: high                         # Effort level
context: fork                        # Execution mode: inline (default) | fork
agent: code-reviewer                 # Specified Agent definition file
user-invocable: true                 # Whether the user can call it via /name
disable-model-invocation: false      # Prohibit AI from invoking autonomously
version: "1.0"                       # Version number
paths:                               # File path patterns for conditional activation
  - "src/**/*.ts"
hooks:                               # Hook configuration
  PreToolUse:
    - command: ["echo", "checking"]
shell: ["bash"]                      # Shell execution environment
---
```

16 fields are extracted after parsing, with `allowedTools`, `model`, and `effort` dynamically modifying the `toolPermissionContext` during execution.

## Two Execution Paths: Inline vs Fork

`SkillTool` (`packages/builtin-tools/src/tools/SkillTool/SkillTool.ts:332`) branches in its `call()` method based on `command.context`:

### Inline Mode (Default)

The Skill's prompt content is injected as a **UserMessage**, continuing within the main conversation flow:

1. `processPromptSlashCommand()` handles argument replacement (`$ARGUMENTS`) and shell command expansion (`` !`...` ``).
2. `${CLAUDE_SKILL_DIR}` is replaced with the absolute path of the directory containing the Skill.
3. `${CLAUDE_SESSION_ID}` is replaced with the current session ID.
4. Returns `newMessages` (injected into the conversation flow) + `contextModifier` (modifies permission context).

The `contextModifier` (line 776) performs three actions:
- **Tool Whitelist Injection**: Merges `allowedTools` into `alwaysAllowRules.command`.
- **Model Switching**: `resolveSkillModelOverride()` handles model overrides, preserving the `[1m]` suffix to avoid truncation in the 200K window.
- **Effort Level Override**: Modifies the `effortValue`.

### Fork Mode (`context: fork`)

The Skill executes within an **independent sub-agent** (`executeForkedSkill`, line 122):

1. `prepareForkedCommandContext()` constructs an isolated Agent definition and Prompt.
2. `runAgent()` starts the sub-agent loop with an independent token budget.
3. Reports tool usage progress via `onProgress` callbacks.
4. Results are extracted via `extractResultText()`; all messages from the sub-agent are released after extraction (`agentMessages.length = 0`).
5. State is eventually cleaned up via `clearInvokedSkillsForAgent()`.

Fork mode is suitable for scenarios requiring strong isolation (e.g., long-running review tasks), avoiding pollution of the main conversation's context.

## Permission Model: Safe Properties Allowlist

`checkPermissions()` (line 433) implements a five-layer permission check:

```
1. Deny Rule Matching (supports exact match and prefix:* wildcards)
   ↓ No match
2. Auto-release of remote canonical Skills (EXPERIMENTAL_SKILL_SEARCH + USER_TYPE === 'ant')
   ↓ No match
3. Allow Rule Matching
   ↓ No match
4. Safe Properties Allowlist Check (skillHasOnlySafeProperties, line 911)
   ↓ Has non-safe properties
5. Ask User for Confirmation (with suggested rules for exact and prefix matching)
```

**Safe Properties** (`SAFE_SKILL_PROPERTIES`, line 876) is an allowlist containing 30 property names (covering all safe properties for both `PromptCommand` and `CommandBase` types). Any **meaningful property value** (excluding `undefined`, `null`, empty arrays, and empty objects) not on the allowlist will trigger a permission request. This is a **positive-security** design—newly added properties will default to requiring permission.

## Prompt Budget: Truncation Strategy for 1% Context Window

When the Skill list is injected into the System Prompt, it follows a strict character budget (`prompt.ts`):

- **Budget Calculation**: `contextWindowTokens × 4 chars/token × 1%` (approx. 8000 characters).
- **Single Entry Cap**: `MAX_LISTING_DESC_CHARS = 250` characters (truncated to `…` if exceeded).
- **Bundled Skills are non-truncatable**: They always retain their full description; non-bundled skills are truncated if the budget is insufficient.
- **Downgrade Strategy**:
  1. Try full descriptions → Over budget?
  2. Bundled skills retain full descriptions, non-bundled skills share the remaining budget → If a description falls below 20 characters?
  3. Non-bundled skills retain only their names.

`formatCommandsWithinBudget()` (`prompt.ts:70`) implements this three-level downgrade.

## Dynamic Discovery and Conditional Activation

### Path-based Dynamic Discovery

`discoverSkillDirsForPaths()` (`loadSkillsDir.ts:861`) is triggered during file operations:

1. Starts from the path of the file being operated on and **traverses up** to the CWD (excluding the CWD itself).
2. Looks for a `.claude/skills/` directory at each level.
3. De-duplicates using `realpath` and filters gitignored directories via `git check-ignore`.
4. Sorted by path depth (**deepest first**); Skills closer to the file have higher priority.

### Conditional Activation (`paths` frontmatter)

Skills with a `paths` pattern are not immediately available upon loading but are stored in a `conditionalSkills` Map. When the path of a file being operated on matches a Skill's `paths` pattern (using the `ignore` library for gitignore-style matching), that Skill is **activated**—moved from `conditionalSkills` to `dynamicSkills`.

This means a testing Skill that only activates on `*.test.ts` remains completely invisible normally, only appearing when the AI reads or edits a test file.

## Usage Frequency Ranking

`recordSkillUsage()` (`skillUsageTracking.ts`) calculates a Skill's ranking score using an exponential decay algorithm:

```
score = usageCount × max(0.5^(daysSinceUse / 7), 0.1)
```

- **7-day Half-life**: Usage weight is halved after one week.
- **Minimum 0.1 Floor**: Prevents old but frequently used Skills from sinking to the bottom.
- **60-second De-bouncing**: Multiple calls to the same Skill within one minute count only as once, reducing file I/O.

Ranking data is persisted in the `skillUsage` field of the global configuration.

## Remote Skill Loading (Experimental)

Controlled by the `EXPERIMENTAL_SKILL_SEARCH` feature flag, this supports loading Skills in the `_canonical_<slug>` format from remote sources (AKI/GCS/S3):

1. `stripCanonicalPrefix()` in `validateInput()` intercepts canonical names.
2. `executeRemoteSkill()` (line 970) loads `SKILL.md` from a remote URL.
3. Supports URL protocols such as `gs://`, `https://`, and `s3://`.
4. Content is injected directly after frontmatter stripping and `${CLAUDE_SKILL_DIR}` replacement.
5. Registered in compaction retention state via `addInvokedSkill()` to ensure recovery after compression.
6. Remote Skills bypass `processPromptSlashCommand`—no `!command` replacement or `$ARGUMENTS` expansion.

## Complete Lifecycle Summary

```
Disk SKILL.md
  ↓ parseFrontmatter()
  ↓ parseSkillFrontmatterFields() → 16 fields
  ↓ createSkillCommand() → Command object
  ↓ De-duplication (realpath + seenFileIds)
  ↓ Conditional Skill → conditionalSkills Map (waiting for path match activation)
  ↓ getSkillDirCommands() memoize cache
  ↓ getAllCommands() merging local + MCP
  ↓ formatCommandsWithinBudget() → Truncated Skill list injected into System Prompt
  ↓ AI selects matching Skill
  ↓ SkillTool.validateInput() → Name validation + existence check
  ↓ SkillTool.checkPermissions() → Five-layer permission check
  ↓ SkillTool.call() → Inline or fork execution
  ↓ contextModifier() → Inject allowedTools + model + effort
  ↓ recordSkillUsage() → Update usage frequency ranking
```
