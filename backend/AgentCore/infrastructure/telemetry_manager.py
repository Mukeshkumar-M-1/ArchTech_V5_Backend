"""
Telemetry & Cost Tracking

Provides observability over execution metrics. Tracks tokens, API latency,
tool duration, and calculates monetary costs per turn.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any

log = logging.getLogger(__name__)

@dataclass
class TurnMetrics:
    turn_id: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_latency_ms: float = 0.0
    tool_duration_ms: float = 0.0
    total_cost_usd: float = 0.0

class CostTracker:
    def __init__(self):
        # Example pricing: $3.00/1M input, $15.00/1M output
        self.input_cost_per_token = 3.00 / 1_000_000
        self.output_cost_per_token = 15.00 / 1_000_000
        log.info("[CostTracker] Initialized with standard pricing model.")

    def calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        return (prompt_tokens * self.input_cost_per_token) + (completion_tokens * self.output_cost_per_token)

class TelemetryManager:
    def __init__(self, cost_tracker: CostTracker):
        self.cost_tracker = cost_tracker
        self.metrics: Dict[int, TurnMetrics] = {}
        self.total_cost: float = 0.0
        log.info("[TelemetryManager] Initialized.")

    def record_llm_call(self, turn_id: int, prompt_tokens: int, completion_tokens: int, latency_ms: float):
        if turn_id not in self.metrics:
            self.metrics[turn_id] = TurnMetrics(turn_id=turn_id)
            
        metric = self.metrics[turn_id]
        metric.prompt_tokens += prompt_tokens
        metric.completion_tokens += completion_tokens
        metric.llm_latency_ms += latency_ms
        
        turn_cost = self.cost_tracker.calculate_cost(prompt_tokens, completion_tokens)
        metric.total_cost_usd += turn_cost
        self.total_cost += turn_cost
        
        log.info(f"[TelemetryManager] Recorded LLM Call (Turn {turn_id}): {prompt_tokens} in / {completion_tokens} out. Cost: ${turn_cost:.4f}")

    def record_tool_execution(self, turn_id: int, duration_ms: float):
        if turn_id not in self.metrics:
            self.metrics[turn_id] = TurnMetrics(turn_id=turn_id)
            
        self.metrics[turn_id].tool_duration_ms += duration_ms
        log.info(f"[TelemetryManager] Recorded Tool Execution (Turn {turn_id}): {duration_ms:.2f}ms")

    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_turns": len(self.metrics),
            "total_cost_usd": self.total_cost,
            "metrics": self.metrics
        }
