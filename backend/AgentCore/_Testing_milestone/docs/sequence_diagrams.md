# AgentCore Sequence Diagrams

All Mermaid diagrams for AgentCore. These documents the runtime flow
for developers who need to understand how components interact.

---

## 1. Document Generation Full Flow

```mermaid
sequenceDiagram
    participant Client
    participant Routes as agents/routes.py
    participant Kernel as AgentKernel
    participant Agent as DocumentGenerationAgent
    participant Controller as DocumentController
    participant Planner as TaskPlanner
    participant Ctx as ContextBuilder
    participant QueryLoop
    participant LLM as Anthropic API
    participant Obs as Observability

    Client->>Routes: POST /generate-document-stream
    Routes->>Kernel: AgentKernel(project_id, session_id)
    Kernel->>Kernel: start()
    Routes->>Agent: DocumentGenerationAgent(project_id)
    Agent->>Controller: initialize()
    Controller->>Controller: SectionRegistry + DependencyGraph
    Controller->>Controller: GoalManager + TaskPlanner
    Controller->>Controller: ContextBuilder + Observability

    Agent->>Agent: build_knowledge_index_block()

    loop For each section
        Agent->>Controller: generate_section(section_number, template, knowledge, query_loop_run)
        Controller->>Planner: decide_next_turn_goal()
        Planner-->>Controller: NextGoal(section, objective)
        Controller->>Ctx: build_turn_context(next_goal, completed, section_name)
        Ctx-->>Controller: WorkingContext
        Controller->>QueryLoop: run(user_message, tools, context)
        loop Each turn
            QueryLoop->>LLM: chat.completions.create()
            LLM-->>QueryLoop: text + tool_calls
            alt tool_calls exist
                QueryLoop->>QueryLoop: execute_tools(tool_calls)
                QueryLoop->>Obs: publish TOOL_EXECUTED
            else no tool_calls
                QueryLoop-->>Controller: section_content
            end
        end
        Controller->>Controller: validate output
        Controller->>Planner: record_completed(section_number)
        Controller->>Obs: publish MISSION_PROGRESS (SSE)
    end

    Agent->>Agent: full_doc = join(document_parts)
    Agent->>Routes: yield_event gen_complete
    Routes-->>Client: SSE stream
```

---

## 2. QueryLoop Inner Turn

```mermaid
sequenceDiagram
    participant QL as QueryLoop
    participant Abort as AbortController
    participant Budget as BudgetManager
    participant Comp as CompactPipeline
    participant Mem as SessionMemoryCache
    participant Sys as SystemPromptManager
    participant API as LLM API
    participant Parser as PTAOResponseParser
    participant Dec as DecisionManager
    participant Exec as ToolExecutor
    participant Todo as TodoWrite
    participant Obs as ObservationManager

    QL->>Abort: check is_aborted
    Abort-->>QL: False
    QL->>Budget: check("tokens_input")
    Budget-->>QL: OK
    QL->>Comp: run(messages)
    Comp-->>QL: compressed_messages
    QL->>Mem: load(session_id)
    Mem-->>QL: session_memory
    QL->>Sys: build(tool_defs, session_memory, goal, phase)
    Sys-->>QL: system_prompt
    QL->>API: chat.completions.create()
    API-->>QL: response
    QL->>Parser: parse(response)
    Parser-->>QL: (text_content, tool_calls)
    QL->>Dec: record(decisions)
    QL->>Obs: record(tool_results)
    alt tool_calls exist
        loop For each tool_call
            QL->>Exec: execute(tool_name, tool_call_id, args)
            Exec-->>QL: ToolExecutionResult
            QL->>QL: append tool result to messages
        end
    else no tool_calls
        QL->>QL: break (final response)
    end
    QL->>Mem: update(session_id)
```

---

## 3. Tool Execution Flow

```mermaid
sequenceDiagram
    participant QL as QueryLoop
    participant TE as ToolExecutor
    participant Reg as ToolRegistry
    participant Perm as PermissionChecker
    participant Tool as Tool Implementation
    participant EB as EventBus

    QL->>TE: execute(tool_name, tool_call_id, args)
    TE->>Reg: get(tool_name)
    Reg-->>TE: ToolDefinition
    TE->>Perm: can_use(tool_name, PermissionMode.AUTO)
    Perm-->>TE: True
    TE->>TE: validate args against input_model
    TE->>EB: publish(TOOL_CALLING)
    TE->>Tool: execute(**validated_args)
    Tool-->>TE: execution_result
    TE->>EB: publish(TOOL_EXECUTED, result)
    TE-->>QL: ToolExecutionResult
```

---

## 4. Agent Spawning Flow

```mermaid
sequenceDiagram
    participant AgentTool as builtins/agent.py
    participant Spawner as AgentSpawner
    participant Child as Child Agent
    participant QLoop as QueryLoop
    participant Hierarchy as AbortHierarchy
    participant Cleaner as AgentCleaner

    AgentTool->>Spawner: spawn(agent_type, prompt, project_id)
    Spawner->>Hierarchy: create child AbortController
    Spawner->>Spawner: create AgentContext (contextvars)
    Spawner->>Child: run QueryLoop with prompt
    Child->>QLoop: run()
    QLoop-->>Child: result
    Child-->>Spawner: AgentResult(content, metrics)
    Spawner->>Cleaner: cleanup_agent(agent_id)
    Cleaner->>Hierarchy: remove_child(agent_id)
    Spawner-->>AgentTool: AgentResult
```

---

## 5. Cancellation Flow

```mermaid
sequenceDiagram
    participant Client
    participant Routes
    participant Kernel
    participant Controller
    participant Agent
    participant QLoop
    participant Abort as AbortController

    Client->>Routes: POST /document-generation-cancel/{project_id}
    Routes->>Agent: abort_controller.abort()
    Agent->>Abort: abort(reason)
    Abort->>Kernel: cancel()
    Kernel->>Kernel: state = CANCELLED
    Kernel->>QLoop: check abort (next turn)
    QLoop->>Abort: is_aborted?
    Abort-->>QLoop: True
    QLoop->>QLoop: raise AbortRequestedError
    QLoop-->>Controller: AbortRequestedError
    Controller->>Controller: mark_section_failed()
    Controller-->>Agent: section content (partial)
    Agent->>Kernel: cleanup()
    Kernel->>Kernel: state = IDLE
    Agent-->>Routes: gen_complete event
    Routes-->>Client: SSE stream (partial result)
```

---

## 6. Session Lifecycle

```mermaid
sequenceDiagram
    participant Client
    participant Routes
    participant Session as SessionLifecycle
    participant FS as Filesystem

    Client->>Routes: POST /generate-document-stream
    Routes->>Session: create_generation(project_id, template_type)
    Session->>FS: write session JSON
    Session-->>Routes: SessionRecord

    loop Per section
        Routes->>Session: update_progress(section, status)
        Session->>FS: update session JSON
    end

    Routes->>Session: update_progress("complete", 100)
    Session->>FS: update session JSON
    Routes-->>Client: gen_complete SSE event

    alt User calls GET progress
        Client->>Routes: GET /document-generation-progress/{project_id}
        Routes->>Session: get_progress(project_id)
        Session->>FS: read session JSON
        Session-->>Routes: progress dict
        Routes-->>Client: JSON progress response
    end
```

---

## 7. EventBus Communication

```mermaid
sequenceDiagram
    participant PROD as Publishers
    participant EB as EventBus
    participant SUB as Subscribers

    PROD->>EB: publish(KERNEL_STARTED)
    EB->>SUB: Observability (log, track)

    PROD->>EB: publish(MISSION_CREATED)
    EB->>SUB: Scheduler (enqueue tasks)
    EB->>SUB: Observability (log, track)

    PROD->>EB: publish(TASK_SCHEDULED)
    EB->>SUB: Observability (log)
    EB->>SUB: BudgetManager (reserve tokens)

    PROD->>EB: publish(TOOL_EXECUTED)
    EB->>SUB: Blackboard (write observation)
    EB->>SUB: LearningEngine (log pattern)
    EB->>SUB: Observability (log)

    PROD->>EB: publish(MISSION_PROGRESS)
    EB->>SUB: Observability → SSE stream

    PROD->>EB: publish(MISSION_COMPLETED)
    EB->>SUB: SessionLifecycle (update progress)
    EB->>SUB: TranscriptWriter (persist)
```
