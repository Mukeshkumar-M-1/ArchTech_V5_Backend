"""
Evidence Extractor

Subscribes to the ObservationBus. Extracts semantic facts, edges, and 
symbols from an Observation to feed into the KnowledgeGraph.
"""

import logging
from .observation_manager import ObservationManager
# from .knowledge_manager import KnowledgeGraph

log = logging.getLogger(__name__)

class EvidenceManager:
    def __init__(self):
        log.info("[EvidenceManager] Initialized.")

    def process_observation(self, observation: ObservationManager) -> None:
        """
        Parses the observation evidence for facts.
        e.g., if observation says 'Found WorkflowRunner in orchestration.py',
        this extracts the edge (WorkflowRunner)-[LOCATED_IN]->(orchestration.py).
        """
        log.info(f"[EvidenceManager] Extracting evidence from {observation.observation_id}")
        
        # Simulate extraction logic
        if "WorkflowRunner" in observation.evidence:
            log.info("[EvidenceManager] Extracted Fact: WorkflowRunner exists.")
            # self.knowledge_graph.add_fact(...)
