# WORKFLOW_SCRIPTS — Workflow Automation

> Feature Flag: `FEATURE_WORKFLOW_SCRIPTS=1`
> Implementation Status: Mostly stubs (7 files); wiring is complete.
> Reference Count: 10

## I. Feature Overview

`WORKFLOW_SCRIPTS` implements file-based, multi-step automated workflows. Users define workflow descriptions in YAML or JSON format, which the system parses into executable sequences of multi-agent steps. A `/workflows` command is provided to manage and trigger these workflows.

## II. Implementation Architecture

### 2.1 Module Status

| Module | File | Status |
| :--- | :--- | :--- |
| **WorkflowTool** | `packages/builtin-tools/src/tools/WorkflowTool/WorkflowTool.ts` | **Partial** — Schema and rendering are complete; the `call` method returns a "missing implementation" notice. |
| **Workflow Permissions** | `packages/builtin-tools/src/tools/WorkflowTool/WorkflowPermissionRequest.tsx` | **Partial** — Permission request component. |
| **Constants** | `packages/builtin-tools/src/tools/WorkflowTool/constants.ts` | **Implemented** — Tool names, directories, and file extension constants. |
| **Command Creation** | `packages/builtin-tools/src/tools/WorkflowTool/createWorkflowCommand.ts` | **Implemented** — Scans the `.claude/workflows/` directory to create Command objects. |
| **Bundled Workflows** | `packages/builtin-tools/src/tools/WorkflowTool/bundled/index.ts` | **Implemented** — Initialization for built-in workflows. |
| **Local Workflow Task** | `src/tasks/LocalWorkflowTask/LocalWorkflowTask.ts` | **Stub** — Types and no-op implementations. |
| **UI Task Component** | `src/components/tasks/src/tasks/LocalWorkflowTask/` | **Stub** — Empty exports. |
| **Detail Dialog** | `src/components/tasks/WorkflowDetailDialog.ts` | **Stub** — Returns null. |
| **Task Registration** | `src/tasks.ts` | **Wired** — Dynamically loaded. |
| **Tool Registration** | `src/tools.ts` | **Wired** — Dynamically loaded; bundled workflow initialization. |
| **Command Registration**| `src/commands.ts` | **Wired** — `/workflows` command integrated. |

### 2.2 Expected Data Flow

```
User defines a workflow (YAML/JSON file)
         │
         ▼
/workflows command discovers workflow files
         │
         ▼
createWorkflowCommand() parses into Command objects [To Be Implemented]
         │
         ▼
WorkflowTool executes the workflow [To Be Implemented]
         │
         ├── Step 1: Agent({ task: "..." })
         ├── Step 2: Agent({ task: "..." })
         └── Step N: Agent({ task: "..." })
         │
         ▼
LocalWorkflowTask coordinates step execution [To Be Implemented]
         │
         ▼
WorkflowDetailDialog displays progress [To Be Implemented]
```

### 2.3 Expected Workflow DSL

```yaml
# workflow.yaml (Expected format, subject to design)
name: "Code Review Workflow"
steps:
  - name: "Static Analysis"
    agent: { type: "general-purpose", prompt: "Run lint and type checks" }
  - name: "Testing"
    agent: { type: "general-purpose", prompt: "Run the test suite" }
  - name: "Summary Report"
    agent: { type: "general-purpose", prompt: "Summarize analysis results and write a report" }
```

## III. Missing Implementations

| Priority | Module | Effort | Description |
| :--- | :--- | :--- | :--- |
| 1 | `WorkflowTool.ts` `call` method | Medium | Actual workflow execution logic. |
| 2 | `LocalWorkflowTask.ts` | High | Step coordination, kill/skip/retry logic. |
| 3 | `WorkflowDetailDialog.ts` | Medium | Progress detail UI. |

## IV. Key Design Decisions

1.  **File-based DSL**: Workflows are defined as YAML/JSON files, making them version-control friendly.
2.  **Multi-Agent Steps**: Each step is an independent agent task, supporting both parallel and serial execution.
3.  **Bundled Workflows**: An out-of-the-box set of common workflows provided in the `bundled/` directory.
4.  **`/workflows` Command**: A unified entry point for discovery and triggering.

## V. Usage

```bash
# Enable the feature (requires further implementation to be functional)
FEATURE_WORKFLOW_SCRIPTS=1 bun run dev
```

## VI. File Index

| File | Responsibility |
| :--- | :--- |
| `packages/builtin-tools/src/tools/WorkflowTool/WorkflowTool.ts` | Tool definition (Partial). |
| `packages/builtin-tools/src/tools/WorkflowTool/WorkflowPermissionRequest.tsx` | Permission request component. |
| `packages/builtin-tools/src/tools/WorkflowTool/constants.ts` | Constant definitions. |
| `packages/builtin-tools/src/tools/WorkflowTool/createWorkflowCommand.ts` | Command creation logic. |
| `packages/builtin-tools/src/tools/WorkflowTool/bundled/index.ts` | Built-in workflow initialization. |
| `src/tasks/LocalWorkflowTask/LocalWorkflowTask.ts` | Task coordination (Stub). |
| `src/components/tasks/WorkflowDetailDialog.ts` | Detail dialog component (Stub). |
| `src/tools.ts` | Tool registration wiring. |
| `src/commands.ts` | Command registration wiring. |
