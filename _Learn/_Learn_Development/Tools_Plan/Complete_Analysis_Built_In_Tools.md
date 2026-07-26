# Complete Analysis of All Built-in Tools

Here is a categorization of every tool organized by purpose, with what each one does and when it's needed.

## 1. FILE READING
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| FileReadTool | Read | `file_path`, `offset`, `limit`, `pages` | Reads text files, images (PNG/JPG/GIF/WebP), PDFs, and Jupyter notebooks (.ipynb). Default 2000 lines. |

## 2. FILE WRITING
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| FileWriteTool | Write | `file_path`, `content` | Full file replacement. Creates parent dirs if needed. Read-before-write validation. Outputs a structured diff. |

## 3. FILE EDITING
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| FileEditTool | Edit | `file_path`, `old_string`, `new_string`, `replace_all` | In-place string replacement. Find-and-replace within a file. Produces structured patch output. |
| NotebookEditTool | Edit Notebook | `notebook_path`, `cell_id`, `new_source`, `cell_type`, `edit_mode` | Jupyter notebook cell-level edit: replace, insert, or delete cells. |

## 4. FILE EXPLORATION / SEARCHING
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| GlobTool | Glob | `pattern`, `path` | File/directory pattern matching. Replaces find, ls, etc. Capped at 100 results. |
| GrepTool | Search | `pattern`, `path`, `glob`, `output_mode`, `-B`, `-A`, `-C`, `-n`, `-i`, `type`, `head_limit` | Content search via ripgrep. Three output modes: content, files_with_matches, count. |
| BashTool | Bash | `command`, `timeout`, `description`, `run_in_background` | Arbitrary shell command execution. Can do cat, ls, find, grep but should use dedicated tools instead. |
| PowerShellTool | Bash | Same as Bash | PowerShell variant for Windows environments. |

## 5. AGENT CREATION / MULTI-AGENT
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| AgentTool | Agent | `description`, `prompt`, `subagent_type`, `model`, `run_in_background`, `isolation` | Spawns sub-agents (child Claude Code instances). Supports sync/async modes, model overrides, worktree isolation. |
| SendMessageTool | SendMessage | `to`, `content` | Inter-agent messaging via mailbox system. For multi-agent swarms. |
| ListPeersTool | ListPeers | none | Lists active peer agents in the current team context. |

## 6. TASK MANAGEMENT (V2 System)
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| TaskCreateTool | TaskCreate | `subject`, `description`, `activeForm` | Creates a task with "pending" status. Runs task_created hooks. |
| TaskUpdateTool | TaskUpdate | `taskId`, `subject`, `description`, `status`, `owner` | Updates tasks (status transitions, ownership, dependencies). |
| TaskListTool | TaskList | none | Lists all non-internal tasks. |
| TaskGetTool | TaskGet | `taskId` | Retrieves a single task by ID. |
| TaskOutputTool | TaskOutput | `task_id`, `block`, `timeout` | Retrieves output from a background task. |
| TaskStopTool | TaskStop | `task_id` | Stops a running background task. |

## 7. TODO LIST (V1 System)
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| TodoWriteTool | TodoWrite | `todos` (array with content, status, activeForm) | Manages flat per-agent todo list for task tracking. |

## 8. WEB / INTERNET
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| WebFetchTool | WebFetch | `url`, `prompt` | Fetches and processes web content. Converts HTML to markdown. 15-min cache. |
| WebBrowserTool | WebBrowser | (browser actions) | Full browser automation. |

## 9. CLI / SHELL INTERACTIVE
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| REPLTool | REPL | `command` | Interactive REPL execution. |
| TerminalCaptureTool | TerminalCapture | `command` | Captures terminal output for execution. |

## 10. MCP INTEGRATION
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| MCPTool | MCP | `server_name`, `tool_name`, `arguments` | Calls tools exposed by MCP servers. |
| ReadMcpResourceTool | ReadMcpResource | `uri` | Reads resources from MCP servers. |
| ListMcpResourcesTool | ListMcpResources | `server_name` | Lists available resources from an MCP server. |

## 11. SKILL MANAGEMENT
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| SkillTool | Skill | `skill`, `args` | Invokes a skill (e.g., /review, /teach-me, /security-review). |
| DiscoverSkillsTool | DiscoverSkills | none | Discovers available skills. |

## 12. PLANNING / WORKFLOW
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| EnterPlanModeTool | EnterPlanMode | none | Enters plan mode (design phase before implementation). |
| ExitPlanModeTool | ExitPlanMode | `allowedPrompts` | Exits plan mode, requests user approval. |
| WorkflowTool | Workflow | (workflow params) | Orchestrates multi-step workflows. |

## 13. GIT / VERSION CONTROL
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| EnterWorktreeTool | EnterWorktree | `name`, `path` | Creates/isolates a git worktree for safe parallel work. |
| ExitWorktreeTool | ExitWorktree | `action`, `discard_changes` | Exits a worktree session. |

## 14. CONFIGURATION / SETTINGS
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| ConfigTool | Config | (config params) | Reads/writes Claude Code configuration. |

## 15. CONTEXT / INSPECTION
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| CtxInspectTool | CtxInspect | none | Inspects current context/session state. |

## 16. TIME / DELAY
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| SleepTool | Sleep | `duration` | Delays execution for a specified duration. |

## 17. NOTIFICATION / PR OPERATIONS
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| PushNotificationTool | PushNotification | (notification params) | Push notifications to user. |
| SubscribePRTool | SubscribePR | (PR params) | Subscribes to PR notifications. |
| SuggestBackgroundPRTool | SuggestBackgroundPR | (PR params) | Suggests background PR review. |
| ReviewArtifactTool | ReviewArtifact | (artifact params) | Reviews code artifacts. |
| VerifyPlanExecutionTool | VerifyPlanExecution | (plan params) | Verifies plan execution was done correctly. |

## 18. TEAM / COLLABORATION
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| TeamCreateTool | TeamCreate | (team params) | Creates a team context for multi-agent collaboration. |
| TeamDeleteTool | TeamDelete | (team params) | Deletes a team context. |

## 19. SPECIALIZED / MISC
| Tool | Name | Key Parameters | What It Does |
|------|------|----------------|--------------|
| LSPTool | LSP | (LSP params) | Language Server Protocol integration. |
| BriefTool | Brief | (brief params) | Generates concise summaries. |
| SendUserFileTool | SendUserFile | (file params) | Sends files to user. |
| OverflowTestTool | OverflowTest | (test params) | Tests overflow handling. |
| SyntheticOutputTool | SyntheticOutput | (output params) | Generates synthetic output for testing. |
| TungstenTool | Tungsten | (params) | Tungsten-specific functionality. |
| McpAuthTool | McpAuth | (auth params) | MCP authentication handling. |
| ReadMcpResourceTool | see MCP | see MCP | see MCP |

---

# Summary: Core Toolkit for Common Development Tasks

If you're asking "what tools do I actually need for everyday work?", here's the essential set:

| Task | Tool(s) to Use |
|------|----------------|
| Read files | FileReadTool (Read) |
| Write/create files | FileWriteTool (Write) |
| Edit files (string replacement) | FileEditTool (Edit) |
| Edit notebooks | NotebookEditTool (Edit Notebook) |
| Find files by pattern | GlobTool (Glob) |
| Search file contents | GrepTool (Search) |
| Run bash commands | BashTool (Bash) |
| Spawn sub-agents | AgentTool (Agent) |
| Manage tasks | TodoWriteTool / TaskCreate-Update-List-Get |
| Web fetching | WebFetchTool |
| Call MCP tools | MCPTool |
| Use skills | SkillTool |
