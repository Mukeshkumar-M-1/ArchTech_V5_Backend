# AgentCore File Structure

- **130 files** across 22 directories
- All paths relative to `backend/AgentCore/`

## Top-Level

- [__init__.py](__init__.py) — Package root, public API exports
- [event_bus.py](event_bus.py) — Consolidated event bus (InfraEventBus, AsyncEventBus, ObservationBus)

## action/ — Task planning & execution routing

- [action_executor.py](action/action_executor.py) — Task executor
- [action_planner.py](action/action_planner.py) — Action planner
- [tool_router.py](action/tool_router.py) — Tool routing logic

## agents/ — API routes

- [routes.py](agents/routes.py) — SSE streaming document generation routes

## cognitive/ — Self-improvement loop

- [reflection_engine.py](cognitive/reflection_engine.py) — Post-execution reflection
- [repair_engine.py](cognitive/repair_engine.py) — Error repair logic
- [verifier_engine.py](cognitive/verifier_engine.py) — Output verification

## context/ — Prompt & execution context management

- [context_builder.py](context/context_builder.py) — Context builder
- [execution_context.py](context/execution_context.py) — Execution context data
- [context_selector.py](context/context_selector.py) — Context selector

## core/ — Execution pipeline (legacy, now using execution/ layer)

- [agent_session_manager.py](core/agent_session_manager.py) — Session persistence
- [agent_state.py](core/agent_state.py) — Agent state store
- [execution_engine.py](core/execution_engine.py) — LLM loop & tool execution
- [execution_history.py](core/execution_history.py) — Turn history with compaction

## domain/ — Data models

- [action_result.py](domain/action_result.py) — Action result model
- [action_decision.py](domain/action_decision.py) — Action decision model
- [execution_plan.py](domain/execution_plan.py) — Execution plan model
- [runtime_policy.py](domain/runtime_policy.py) — Runtime policy data
- [reasoning_state.py](domain/reasoning_state.py) — Reasoning state model

## execution/ — Tool execution layer

- [abort_controller.py](execution/abort_controller.py) — Task abort/cancellation
- [agent_cleanup.py](execution/agent_cleanup.py) — Agent lifecycle cleanup
- [agent_mailbox.py](execution/agent_mailbox.py) — Inter-agent messaging
- [agent_spawner.py](execution/agent_spawner.py) — Spawn sub-agents
- [context_compaction.py](execution/context_compaction.py) — Context compaction pipeline
- [context_isolation.py](execution/context_isolation.py) — Context isolation
- [message_manager.py](execution/message_manager.py) — Message handling
- [pause_manager.py](execution/pause_manager.py) — Pause/resume control
- [permission_manager.py](execution/permission_manager.py) — Permission manager
- [query_loop.py](execution/query_loop.py) — LLM query loop with fallbacks
- [session_manager.py](execution/session_manager.py) — Chat session management
- [session_memory.py](execution/session_memory.py) — Session memory extraction
- [system_prompt.py](execution/system_prompt.py) — System prompt builder
- [task_state.py](execution/task_state.py) — Task state tracking
- [tool_executor.py](execution/tool_executor.py) — Tool executor
- [tool_registry.py](execution/tool_registry.py) — Tool registry
- [token_usage_tracker.py](execution/token_usage_tracker.py) — Token usage tracking
- [transcript_writer.py](execution/transcript_writer.py) — Session transcripts

### execution/builtins/ — Tool implementations

- [__init__.py](execution/builtins/__init__.py) — Auto-register all tools
- [agent.py](execution/builtins/agent.py) — Sub-agent spawning tool
- [bash.py](execution/builtins/bash.py) — Bash command execution
- [file_edit.py](execution/builtins/file_edit.py) — File editing tool
- [file_read.py](execution/builtins/file_read.py) — File reading tool
- [file_write.py](execution/builtins/file_write.py) — File writing tool
- [glob.py](execution/builtins/glob.py) — File pattern matching
- [propose_content_edit.py](execution/builtins/propose_content_edit.py) — Content edit proposal
- [request_user_input.py](execution/builtins/request_user_input.py) — User input request
- [search.py](execution/builtins/search.py) — Code search tool
- [send_message.py](execution/builtins/send_message.py) — Message sending
- [tasks.py](execution/builtins/tasks.py) — Internal task helpers (background agent coordination)

## infrastructure/ — Cross-cutting concerns

- [policy_manager.py](infrastructure/policy_manager.py) — Policy enforcement
- [telemetry_manager.py](infrastructure/telemetry_manager.py) — Telemetry & cost tracking

## journal/ — Execution logging

- [execution_journal.py](journal/execution_journal.py) — Execution journal

## knowledge/ — Knowledge graph & observation

- [evidence_manager.py](knowledge/evidence_manager.py) — Evidence model
- [knowledge_manager.py](knowledge/knowledge_manager.py) — Knowledge graph
- [observation_manager.py](knowledge/observation_manager.py) — Observation model
- [observation_bus.py](knowledge/observation_bus.py) — Observation pub/sub
- [observation_engine.py](knowledge/observation_engine.py) — Observation processing
- [observation_parser.py](knowledge/observation_parser.py) — Observation parsing

## memory/ — Multi-tier memory system

- [store_manager.py](memory/store_manager.py) — Memory store coordinator
- [mission_store.py](memory/mission_store.py) — Mission memory
- [scratchpad_store.py](memory/scratchpad_store.py) — Scratchpad storage
- [working_store.py](memory/working_store.py) — Working memory

## observability/ — Lifecycle & monitoring

- [agent_kernel.py](observability/agent_kernel.py) — ChatAgentKernel (lifecycle), GenerationAgentKernel (task executor)
- [blackboard.py](observability/blackboard.py) — Shared blackboard state
- [budget_manager.py](observability/budget_manager.py) — Cost/time budgeting

## orchestration/ — Multi-agent task scheduling

- [context_builder.py](orchestration/context_builder.py) — Context building for tasks
- [contracts.py](orchestration/contracts.py) — IAgentRuntime interface & contracts
- [dependency_graph.py](orchestration/dependency_graph.py) — Task dependency graph
- [__init__.py](orchestration/__init__.py) — Sub-module exports
- [mission_layer.py](orchestration/mission_layer.py) — Mission parsing & planning
- [next_goal.py](orchestration/next_goal.py) — Next goal inference
- [orchestrator.py](orchestration/orchestrator.py) — MissionOrchestrator (main entry)
- [planner_engine.py](orchestration/planner_engine.py) — Task planner
- [lease_manager.py](orchestration/lease_manager.py) — Task queue & dispatcher
- [result_layer.py](orchestration/result_layer.py) — Result processing
- [runtime_adapter.py](orchestration/runtime_adapter.py) — IAgentRuntime implementation
- [scheduling_manager.py](orchestration/scheduling_manager.py) — Scheduling policy & capability resolver
- [section_registry.py](orchestration/section_registry.py) — Document section registry
- [task_planner.py](orchestration/task_planner.py) — Task planning logic
- [traceability_builder.py](orchestration/traceability_builder.py) — Requirements traceability
- [worker_management.py](orchestration/worker_management.py) — Worker catalog & heartbeats
- [workflow.py](orchestration/workflow.py) — Workflow orchestration

## platform/ — Infrastructure abstractions

### platform/llm/

- [adapter.py](platform/llm/adapter.py) — LLM provider adapter
- [builder.py](platform/llm/builder.py) — Prompt builder
- [interfaces.py](platform/llm/interfaces.py) — LLM provider interfaces
- [parser.py](platform/llm/parser.py) — Response parser
- [renderer.py](platform/llm/renderer.py) — Output renderer

### platform/artifacts/

- [diff_engine.py](platform/artifacts/diff_engine.py) — Artifact diffing
- [artifact_manager.py](platform/artifacts/artifact_manager.py) — Artifact management

### platform/execution/

- [sandbox_manager.py](platform/execution/sandbox_manager.py) — Execution sandbox

## prompt/ — Prompt management

- [prompt_manager.py](prompt/prompt_manager.py) — Prompt management and rendering
- [prompt_registry.py](prompt/prompt_registry.py) — Prompt registry
- [prompt_template.py](prompt/prompt_template.py) — Prompt templates

## reasoning/ — Reasoning engine

- [reason_engine.py](reasoning/reason_engine.py) — Reasoning engine
- [turn_manager.py](reasoning/turn_manager.py) — Turn management

## repository/ — Code repository intelligence

- [__init__.py](repository/__init__.py) — Sub-module exports
- [repo_index.py](repository/repo_index.py) — Symbol/file indexing
- [repo_query_engine.py](repository/repo_query_engine.py) — Codebase query engine
- [repo_snapshot.py](repository/repo_snapshot.py) — Repository snapshots
- [test_repo_intelligence.py](repository/test_repo_intelligence.py) — Repo tests

## runtime/ — State machine & recovery

- [cancellation_manager.py](runtime/cancellation_manager.py) — Cancellation handling
- [checkpoint_manager.py](runtime/checkpoint_manager.py) — Checkpoint/savepoint
- [dispatch_manager.py](runtime/dispatch_manager.py) — Task dispatcher
- [failure_classifier.py](runtime/failure_classifier.py) — Failure classification
- [interrupt_manager.py](runtime/interrupt_manager.py) — Interrupt handling
- [replay_engine.py](runtime/replay_engine.py) — Execution replay
- [state_machine.py](runtime/state_machine.py) — Runtime state machine

## shared/ — Cross-cutting types

- [exceptions.py](shared/exceptions.py) — Custom exceptions
- [types.py](shared/types.py) — Shared Pydantic models

## _Testing_milestone/ — Validation test suite

- [ARCHITECTURE_DECISIONS.md](_Testing_milestone/ARCHITECTURE_DECISIONS.md) — ADR documentation
- [docs/data_flow.md](_Testing_milestone/docs/data_flow.md) — Data flow diagrams
- [docs/dependency_graph.md](_Testing_milestone/docs/dependency_graph.md) — Dependency graph docs
- [docs/seq_1.md](_Testing_milestone/docs/seq_1.md) — Sequence diagram 1
- [docs/sequence_diagrams.md](_Testing_milestone/docs/sequence_diagrams.md) — Sequence diagram reference
- [docs/state_machines.md](_Testing_milestone/docs/state_machines.md) — State machine docs
- [test_execution_history.py](_Testing_milestone/test_execution_history.py) — Context compaction tests
- [test_m5_integration.py](_Testing_milestone/test_m5_integration.py) — M5 integration tests
- [test_milestone_2.py](_Testing_milestone/test_milestone_2.py) — Milestone 2 tests
- [test_milestone_3.py](_Testing_milestone/test_milestone_3.py) — Milestone 3 tests
- [test_milestone_4.py](_Testing_milestone/test_milestone_4.py) — Milestone 4 tests
- [test_milestone_4_5.py](_Testing_milestone/test_milestone_4_5.py) — Milestone 4.5 tests
- [test_milestone_5.py](_Testing_milestone/test_milestone_5.py) — Milestone 5 tests
- [test_runtime_concurrency.py](_Testing_milestone/test_runtime_concurrency.py) — Concurrency tests
- [test_runtime_correctness.py](_Testing_milestone/test_runtime_correctness.py) — Correctness tests
- [test_runtime_governance.py](_Testing_milestone/test_runtime_governance.py) — Governance tests
- [test_runtime_performance.py](_Testing_milestone/test_runtime_performance.py) — Performance tests
- [test_runtime_recoverability.py](_Testing_milestone/test_runtime_recoverability.py) — Recovery tests
- [test_runtime_reliability.py](_Testing_milestone/test_runtime_reliability.py) — Reliability tests
