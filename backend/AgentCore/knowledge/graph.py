"""
Knowledge Graph

Maintains a lightweight semantic relationship store.
In Milestone 2 (V1), this is a simple in-memory dictionary-based graph.
Nodes are entities, Edges are relationships with confidence.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Set

from .observation import Observation

log = logging.getLogger(__name__)

@dataclass
class Edge:
    source_entity: str
    target_entity: str
    relationship: str
    confidence: float
    evidence_observation_id: str


class KnowledgeGraph:
    """A semantic relationship store built from Observations."""
    
    def __init__(self):
        self.nodes: Set[str] = set()
        self.edges: List[Edge] = []
        log.info("[KnowledgeGraph] Initialized empty graph.")
        
    def add_node(self, entity_name: str) -> None:
        self.nodes.add(entity_name)
        
    def add_edge(self, source: str, target: str, relationship: str, confidence: float, obs_id: str) -> None:
        self.add_node(source)
        self.add_node(target)
        edge = Edge(source, target, relationship, confidence, obs_id)
        self.edges.append(edge)
        log.debug(f"[KnowledgeGraph] Added edge: {source} -[{relationship}]-> {target} (Conf: {confidence})")
        
    def query_relationships(self, entity_name: str) -> List[Edge]:
        return [e for e in self.edges if e.source_entity == entity_name or e.target_entity == entity_name]


class KnowledgeUpdater:
    """Consumes Observations and updates the KnowledgeGraph."""
    
    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph
        log.info("[KnowledgeUpdater] Initialized.")

    def process_observation(self, observation: Observation, relationships: List[Dict[str, str]]) -> None:
        """
        In a real scenario, an LLM parses the observation to extract relationships.
        For this V1 stub, we accept the pre-parsed relationships.
        relationships should be dicts with: 'source', 'target', 'relationship'
        """
        for rel in relationships:
            self.graph.add_edge(
                source=rel['source'],
                target=rel['target'],
                relationship=rel['relationship'],
                confidence=observation.confidence,
                obs_id=observation.observation_id
            )
        log.info(f"[KnowledgeUpdater] Processed observation {observation.observation_id}, added {len(relationships)} edges.")
