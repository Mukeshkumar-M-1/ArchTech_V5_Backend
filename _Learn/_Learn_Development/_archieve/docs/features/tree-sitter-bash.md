# TREE_SITTER_BASH — Bash AST Parsing

> Feature Flag: `FEATURE_TREE_SITTER_BASH=1`
> Implementation Status: Fully operational (Pure TypeScript implementation, ~7000+ lines).
> Reference Count: 3

## I. Feature Overview

`TREE_SITTER_BASH` enables a comprehensive Bash AST parser for validating Bash commands. It replaces the legacy regex-based shell-quote parser with a full tree-traversal security analyzer. A key property of this parser is its **fail-closed** nature: any unrecognized content is categorized as `too-complex` and requires explicit user approval.

### Associated Features

| Feature | Description |
| :--- | :--- |
| `TREE_SITTER_BASH` | Activates the AST parser for permission checks. |
| `TREE_SITTER_BASH_SHADOW` | Shadow/Observation mode: Runs the parser but discards results, logging only telemetry data. |

## II. Security Architecture

### 2.1 Fail-Closed Design

The core design utilizes an **allowlist** traversal pattern:
- `walkArgument()` only processes known safe node types (e.g., `word`, `number`, `raw_string`, `string`, `concatenation`, `arithmetic_expansion`, `simple_expansion`).
- Any unknown node types → `tooComplex()` → Requires user approval.
- If the parser fails (e.g., timeout, node budget exceeded, or panic) → Returns a `PARSE_ABORTED` symbol (distinguished from "module not loaded").

### 2.2 Parsing Results

```ts
parseForSecurity(cmd) returns:
  { kind: 'simple', commands: SimpleCommand[] }     // Statically analyzable
  { kind: 'too-complex', reason, nodeType }          // Requires user approval
  { kind: 'parse-unavailable' }                      // Parser not loaded
```

### 2.3 Security Check Hierarchy

```
parseForSecurity(cmd)
      │
      ▼
parseCommandRaw(cmd) → AST root node
      │
      ▼
Pre-checks: Control characters, Unicode whitespace, backslash+whitespace,
            zsh ~[ ] syntax, zsh =cmd expansion, brace+quote confusion
      │
      ▼
walkProgram(root) → collectCommands(root, commands, varScope)
      │
      ├── 'command'             → walkCommand()
      ├── 'pipeline'/'list'     → Structural; recurses children
      ├── 'for_statement'       → Tracks loop variables as VAR_PLACEHOLDER
      ├── 'if/while'            → Scope-isolated branches
      ├── 'subshell'            → Scope duplication
      ├── 'variable_assignment' → walkVariableAssignment()
      ├── 'declaration_command' → Validates declare/export flags
      ├── 'test_command'        → Walks test expressions
      └── Others                → tooComplex()
      │
      ▼
checkSemantics(commands)
  ├── EVAL_LIKE_BUILTINS (eval, source, exec, trap...)
  ├── ZSH_DANGEROUS_BUILTINS (zmodload, emulate...)
  ├── SUBSCRIPT_EVAL_FLAGS (test -v, printf -v, read -a)
  ├── Shell keywords as argv[0] (Misparsing detection)
  ├── /proc/*/environ access
  ├── jq system() and dangerous flags
  └── Wrapper stripping (time, nohup, timeout, nice, env, stdbuf)
```

## III. Implementation Architecture

### 3.1 Core Modules

| Module | File | Lines | Responsibility |
| :--- | :--- | :--- | :--- |
| **Gating Entry** | `src/utils/bash/parser.ts` | ~110 | `parseCommand()`, `parseCommandRaw()`, `ensureInitialized()`. |
| **Bash Parser** | `src/utils/bash/bashParser.ts` | 4437 | Pure TS lexing and recursive-descent parsing. |
| **Security Analyzer** | `src/utils/bash/ast.ts` | 2680 | Tree-traversal security analysis and `parseForSecurity()`. |
| **AST Analysis Helpers** | `src/utils/bash/treeSitterAnalysis.ts` | 507 | Quote contexts, compound structures, and dangerous pattern extraction. |
| **Permission Hook** | `src/tools/BashTool/bashPermissions.ts` | — | Integration of AST results into permission decisions. |

### 3.2 Bash Parser

File: `src/utils/bash/bashParser.ts` (4437 lines)
- Pure TypeScript implementation (no native dependencies).
- Generates an AST compatible with `tree-sitter-bash`.
- **Key Types**: `TsNode` (type, text, startIndex, endIndex, children).
- **Safety Limits**: `PARSE_TIMEOUT_MS = 50`, `MAX_NODES = 50_000` (prevents OOM from adversarial inputs).

### 3.3 Security Analyzer

File: `src/utils/bash/ast.ts` (2680 lines)

| Function | Responsibility |
| :--- | :--- |
| `parseForSecurity(cmd)` | Top-level entry; returns `simple`, `too-complex`, or `parse-unavailable`. |
| `parseForSecurityFromAst()` | Accepts a pre-parsed AST. |
| `checkSemantics(commands)` | Post-parsing semantic checks. |
| `walkCommand()` | Extracts `argv`, `envVars`, and `redirects`. |
| `walkArgument()` | Allowlist-based parameter traversal. |
| `collectCommands()` | Recursively collects all commands. |

### 3.4 AST Analysis Helpers

File: `src/utils/bash/treeSitterAnalysis.ts` (507 lines)

| Function | Responsibility |
| :--- | :--- |
| `extractQuoteContext()` | Identifies single/double quotes, ANSI-C strings, and heredocs. |
| `extractCompoundStructure()` | Detects pipelines, subshells, and command groups. |
| `hasActualOperatorNodes()`| Distinguishes real `;`/`&&`/`||` from escaped forms. |
| `extractDangerousPatterns()` | Detects command substitutions, parameter expansions, and heredocs. |
| `analyzeCommand()` | Extraction via single-pass traversal. |

### 3.5 Shadow Mode

`TREE_SITTER_BASH_SHADOW` runs the parser but **never affects permission decisions**:
```ts
// Shadow Mode: Logs telemetry, then forces use of the legacy path
astResult = { kind: 'parse-unavailable' }
astRoot = null
// Logs: available, astTooComplex, astSemanticFail, subsDiffer, ...
```
Logs the `tengu_tree_sitter_shadow` event, including comparisons with legacy `splitCommand()` data. Used for non-disruptive telemetry collection.

## IV. Key Design Decisions

1.  **Allowlist Traversal**: Only processes known safe node types; unknown types trigger `tooComplex()`.
2.  **`PARSE_ABORTED` Symbol**: Distinguishes "parser not loaded" from "parser failed." The latter prevents fallback to the legacy version (which lacks `EVAL_LIKE_BUILTINS` checks).
3.  **Variable Scope Tracking**: Handles patterns like `VAR=value && cmd $VAR`. Static values resolve to real strings; `$()` outputs use `VAR_PLACEHOLDER`.
4.  **PS4/IFS Allowlist**: PS4 assignments use a strict character allowlist `[A-Za-z0-9 _+:.\/=\[\]-]` and only allow `${VAR}` references.
5.  **Wrapper Stripping**: Strips `time`, `nohup`, `timeout`, `nice`, `env`, and `stdbuf` from `argv`; unknown flags lead to a fail-closed result.
6.  **Shadow Safety**: Shadow mode **always** forces `astResult = { kind: 'parse-unavailable' }` to ensure it never influences permissions.

## V. Usage

```bash
# Activate AST parsing for permission checks
FEATURE_TREE_SITTER_BASH=1 bun run dev

# Shadow Mode (Telemetry only, no behavioral impact)
FEATURE_TREE_SITTER_BASH_SHADOW=1 bun run dev
```

## VI. File Index

| File | Lines | Responsibility |
| :--- | :--- | :--- |
| `src/utils/bash/parser.ts` | ~110 | Gating entry point. |
| `src/utils/bash/bashParser.ts` | 4437 | Pure TS Bash parser. |
| `src/utils/bash/ast.ts` | 2680 | Core security analyzer. |
| `src/utils/bash/treeSitterAnalysis.ts` | 507 | AST analysis helpers. |
| `packages/builtin-tools/src/tools/BashTool/bashPermissions.ts` | ~140 | Permission integration and Shadow telemetry. |
