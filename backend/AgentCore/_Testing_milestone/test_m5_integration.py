"""
Milestone 5 Integration Test
Executes a multi-task mission across a simulated cluster of 3 local runtime workers.
"""

import asyncio
import logging
from AgentCore.orchestration.contracts import AgentDescriptor, AgentStatus
from AgentCore.orchestration.runtime_adapter import RuntimeAdapter
from AgentCore.orchestration.worker_management import (
    AgentCatalog, WorkerDirectory, HeartbeatMonitor, WorkerLifecycle
)
from AgentCore.orchestration.queue_and_dispatch import (
    TaskQueue, LeaseManager, AssignmentTracker, Dispatcher
)
from AgentCore.orchestration.scheduling import (
    CapabilityResolver, LeastBusyPolicy, Scheduler
)
from AgentCore.orchestration.mission_layer import (
    MissionParser, TaskPlanner, TaskGraphBuilder, MissionStateManager, ReadyTaskSelector
)
from AgentCore.orchestration.result_layer import (
    ResultProcessor, MissionStateUpdater
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")
log = logging.getLogger("TestM5Integration")

async def run_mission():
    log.info("=== Initializing M5 Orchestration Cluster ===")
    
    # 1. Worker Layer
    catalog = AgentCatalog()
    directory = WorkerDirectory()
    lifecycle = WorkerLifecycle(directory)
    
    # Register 3 workers
    for i in range(1, 4):
        worker_id = f"worker_00{i}"
        descriptor = AgentDescriptor(
            agent_id=worker_id,
            profile="General_Purpose",
            capabilities=frozenset(["bash", "python"]),
            resource_limits={},
            supported_contract_versions=frozenset(["v1"])
        )
        catalog.register_profile(descriptor)
        
        # Start heartbeats
        hb = HeartbeatMonitor(worker_id, directory)
        asyncio.create_task(hb.run())
        
    await asyncio.sleep(0.1) # Let heartbeats register
        
    runtimes = {
        "worker_001": RuntimeAdapter("worker_001"),
        "worker_002": RuntimeAdapter("worker_002"),
        "worker_003": RuntimeAdapter("worker_003"),
    }
    
    # 2. Queue & Dispatch
    queue = TaskQueue()
    lease_manager = LeaseManager()
    assignment_tracker = AssignmentTracker()
    dispatcher = Dispatcher(runtimes)
    
    # 3. Scheduling Layer
    resolver = CapabilityResolver(catalog)
    policy = LeastBusyPolicy()
    scheduler = Scheduler(resolver, directory, policy, lease_manager, dispatcher, assignment_tracker)
    
    # 4. Mission Layer
    parser = MissionParser()
    planner = TaskPlanner()
    graph_builder = TaskGraphBuilder()
    
    # 5. Result Layer
    state_manager = MissionStateManager()
    
    log.info("=== Submitting Mission ===")
    spec = parser.parse("Build a REST API")
    planned_tasks = planner.plan(spec)
    
    graph = graph_builder.build_graph(planned_tasks)
    state_manager.initialize_from_graph(graph)
    
    selector = ReadyTaskSelector(graph, queue)
    state_updater = MissionStateUpdater(graph, state_manager)
    result_processor = ResultProcessor(lease_manager, state_updater, directory)
    
    log.info("=== Starting Execution Loop ===")
    
    # Simple simulation loop
    active_dispatch_tasks = []
    
    while state_manager.completed_tasks < state_manager.total_tasks:
        # A. Find ready tasks and push to queue
        selector.sweep_and_enqueue()
        
        # B. Schedule and Dispatch
        dispatched_count = await scheduler.run_scheduling_cycle(queue)
        
        # C. Mock collecting results from the active async tasks
        # In a real system, the dispatcher would return Futures, or workers would push results 
        # back to a ResultQueue. We'll simulate fetching results here.
        for assignment in list(lease_manager._leases.values()):
            task_id = assignment.task_id
            worker_id = assignment.worker_id
            
            # Since the adapter is mocked and executes immediately via asyncio.create_task in dispatcher,
            # we can simulate the result arriving shortly after.
            # We'll just fake the successful return for the test loop flow.
            
            # We are injecting a mock result to the result processor
            from AgentCore.orchestration.contracts import RuntimeResult, RuntimeLifecycleStatus
            mock_result = RuntimeResult(
                task_id=task_id,
                status=RuntimeLifecycleStatus.COMPLETED
            )
            result_processor.process_result(mock_result)
            
        await asyncio.sleep(0.1)
        
    log.info("=== Mission Completed Successfully ===")
    
if __name__ == "__main__":
    asyncio.run(run_mission())
