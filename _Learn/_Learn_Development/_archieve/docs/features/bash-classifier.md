# BASH_CLASSIFIER — Bash Command Classifier

> Feature Flag: `FEATURE_BASH_CLASSIFIER=1`
> Implementation Status: `bashClassifier.ts` is entirely stubbed; `yoloClassifier.ts` provides a complete reference implementation.
> Reference Count: 45

## I. Feature Overview

`BASH_CLASSIFIER` uses an LLM to classify the intent of bash commands (allow/deny/ask), enabling automated permission decisions. Users do not need to approve bash commands individually; the classifier automatically judges safety based on the command content and context.

### Core Features

- **LLM-Driven Classification**: Uses the Opus model to evaluate command safety.
- **Two-Stage Classification**: Fast Block/Allow → Deep Chain-of-Thought analysis.
- **Auto-Approval**: Commands determined safe by the classifier are automatically approved.
- **UI Integration**: The permission dialog displays the classifier's status and audit options.

## II. Implementation Architecture

### 2.1 Module Status

| Module | File | Status | Description |
| :--- | :--- | :--- | :--- |
| Bash Classifier | `src/utils/permissions/bashClassifier.ts` | **Stub** | All functions return no-ops. Commented as "ANT-ONLY". |
| YOLO Classifier | `src/utils/permissions/yoloClassifier.ts` | **Complete** | 1496 lines, two-stage XML classifier. |
| Approval Signals | `src/utils/classifierApprovals.ts` | **Complete** | Map + signal management for classifier decisions. |
| Permission UI | `src/components/permissions/BashPermissionRequest.tsx` | **Wired** | Classifier status display and audit options. |
| Permission Pipeline | `src/hooks/toolPermission/handlers/*.ts` | **Wired** | Classifier results routed to decision making. |
| API Beta Headers | `src/services/api/withRetry.ts` | **Wired** | Sends the `bash_classifier` beta header when enabled. |

### 2.2 Reference Implementation: yoloClassifier.ts

File: `src/utils/permissions/yoloClassifier.ts` (1496 lines)

This is a complete implementation of a classifier that can serve as a reference for `bashClassifier.ts`:

```
Two-stage classification:
1. Fast stage: Construct conversation history → Call sideQuery (Opus) → Fast block/allow.
2. Deep stage: Chain-of-thought analysis → Final decision.
```

Features:
- Constructs complete conversation history context.
- Calls `sideQuery` with a safety system prompt.
- GrowthBook configuration and metrics.
- Error handling and fallbacks.

### 2.3 Classifier Position in the Permission Pipeline

```
Bash command arrives
      │
      ▼
bashPermissions.ts permission check
      │
      ├── Traditional rule matching (string-level)
      │
      └── [BASH_CLASSIFIER] LLM Classification
            │
            ├── allow → Auto-pass
            ├── deny → Auto-deny
            └── ask → Display permission dialog
                  │
                  ├── Classifier auto-approval tag
                  └── Audit options (user can override)
```

## III. Missing Implementations

| Function | Needs Implementation | Description |
| :--- | :--- | :--- |
| `classifyBashCommand()` | LLM call for safety evaluation | Refer to the two-stage pattern in `yoloClassifier.ts`. |
| `isClassifierPermissionsEnabled()` | GrowthBook/config check | Controls whether the classifier is active. |
| `getBashPromptDenyDescriptions()` | Return prompt-based deny rules | Permission setting descriptions. |
| `getBashPromptAskDescriptions()` | Return ask rules | Commands requiring user confirmation. |
| `getBashPromptAllowDescriptions()` | Return allow rules | Automatically passed commands. |
| `generateGenericDescription()` | LLM-generated command description | Provides explanations for the permission dialog. |
| `extractPromptDescription()` | Parse rule content | Extracts descriptions from rules. |

## IV. Key Design Decisions

1.  **ANT-ONLY Tagging**: `bashClassifier.ts` is labeled as "ANT-ONLY," likely serving as a client-side adapter for Anthropic's internal server-side classifier.
2.  **Two-Stage Classification**: The fast stage handles clear-cut cases to reduce latency, while the deep stage handles ambiguous ones.
3.  **Auditable Results**: The permission UI displays the classifier's decision, which the user can override.
4.  **YOLO Classifier Reference**: `yoloClassifier.ts` provides a complete classifier implementation pattern for direct reference.

## V. Usage

```bash
# Enable the feature
FEATURE_BASH_CLASSIFIER=1 bun run dev

# Use in conjunction with TREE_SITTER_BASH (AST + LLM dual safety)
FEATURE_BASH_CLASSIFIER=1 FEATURE_TREE_SITTER_BASH=1 bun run dev
```

## VI. File Index

| File | Line Count | Responsibility |
| :--- | :--- | :--- |
| `src/utils/permissions/bashClassifier.ts` | — | Bash classifier (stub, ANT-ONLY). |
| `src/utils/permissions/yoloClassifier.ts` | 1496 | YOLO classifier (complete reference implementation). |
| `src/utils/classifierApprovals.ts` | — | Classifier approval signal management. |
| `src/components/permissions/BashPermissionRequest/BashPermissionRequest.tsx` | — | Classifier UI. |
| `src/hooks/toolPermission/handlers/interactiveHandler.ts` | — | Interactive permission handling. |
| `src/services/api/withRetry.ts` | — | API beta headers. |
