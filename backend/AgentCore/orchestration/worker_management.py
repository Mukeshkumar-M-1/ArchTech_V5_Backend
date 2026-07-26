"""
Worker Management

Handles the static catalog, dynamic directory, lifecycle transitions, and health monitoring
of workers in the orchestration ecosystem.
"""

import logging
import time
import asyncio
from typing import Dict, List, Optional
from AgentCore.orchestration.contracts import AgentDescriptor, AgentHeartbeat, AgentStatus

log = logging.getLogger(__name__)

class AgentCatalog:
    """Stores static metadata for available worker profiles."""
    def __init__(self):
        self.agent_profiles: Dict[str, AgentDescriptor] = {}
        
    def register_profile(self, agent_descriptor: AgentDescriptor):
        self.agent_profiles[agent_descriptor.agent_id] = agent_descriptor             
        log.info(f"[AgentCatalog] Registered static profile for [{agent_descriptor.agent_id}] [({agent_descriptor.agent_profile})]")
        
    def get_profile(self, agent_id: str) -> Optional[AgentDescriptor]:
        return self.agent_profiles.get(agent_id)
        
    def list_all(self) -> List[AgentDescriptor]:
        return list(self.agent_profiles.values())


class WorkerDirectory:
    """Stores dynamic runtime state for active workers."""
    def __init__(self):
        self.agent_heart_beat: Dict[str, AgentHeartbeat] = {}
        
    def update_heartbeat(self, heartbeat: AgentHeartbeat):
        heartbeat.last_seen_timestamp = time.time()
        self.agent_heart_beat[heartbeat.agent_id] = heartbeat
        log.info(f"[WorkerDirectory] Heartbeat received from {heartbeat.agent_id} - Status: {heartbeat.status.name}")
        
    def get_heartbeat(self, agent_id: str) -> Optional[AgentHeartbeat]:
        return self.agent_heart_beat.get(agent_id)
        
    def list_active(self) -> List[AgentHeartbeat]:
        return list(self.agent_heart_beat.values())


class WorkerLifecycle:
    """Manages the operational lifecycle and graceful draining of workers."""
    
    def __init__(self, directory: WorkerDirectory):
        self.directory = directory
        
    def set_status(self, agent_id: str, status: AgentStatus):
        hb = self.directory.get_heartbeat(agent_id)
        if hb:
            hb.status = status
            log.info(f"[WorkerLifecycle] {agent_id} transitioned to {status.name}")
            
    def drain_worker(self, agent_id: str):
        """Instructs the scheduler to stop assigning work, allowing current work to finish."""
        log.warning(f"[WorkerLifecycle] Initiating DRAIN for {agent_id}")
        self.set_status(agent_id, AgentStatus.DRAINING)
        
    def retire_worker(self, agent_id: str):
        log.warning(f"[WorkerLifecycle] Retiring {agent_id}")
        self.set_status(agent_id, AgentStatus.OFFLINE)


class FailureDetector:
    """Detects stalled checkpoints, missed heartbeats, and out-of-memory errors."""
    
    def __init__(self, directory: WorkerDirectory, timeout_seconds: float = 30.0):
        self.directory = directory
        self.timeout_seconds = timeout_seconds
        
    async def monitor_loop(self):
        """Background task checking for dead workers."""
        while True:
            now = time.time()
            for agent_id, hb in self.directory.agent_heart_beat.items():
                if hb.status in [AgentStatus.OFFLINE, AgentStatus.FAILED]:
                    continue
                    
                time_since_last = now - hb.last_seen_timestamp
                if time_since_last > self.timeout_seconds:
                    log.error(f"[FailureDetector] Missed heartbeat from {agent_id}! ({time_since_last:.1f}s ago)")
                    hb.status = AgentStatus.FAILED
                    # Route to FailureClassifier -> RetryManager in integration
            
            await asyncio.sleep(5)


class HeartbeatMonitor:
    """Emulates a worker process emitting heartbeats to the directory."""
    
    def __init__(self, agent_id: str, worker_directory: WorkerDirectory):
        self.agent_id = agent_id
        self.worker_directory = worker_directory
        self.running = False
        
    async def run(self):
        self.running = True
        log.info(f"[HeartbeatMonitor] Started emitting heartbeats for [{self.agent_id}]")
        while self.running:
            agent_heart_beat = AgentHeartbeat(
                agent_id=self.agent_id,
                status=AgentStatus.IDLE, # Ideally derived from adapter status
                cpu_usage_pct=5.0,
                memory_usage_mb=128.0,
                queue_depth=0,
                health_score=1.0
            )
            self.worker_directory.update_heartbeat(heartbeat=agent_heart_beat)
            await asyncio.sleep(10)
