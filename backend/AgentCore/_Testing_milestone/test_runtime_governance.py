"""
Validation Phase: Runtime Governance

Validates:
1. Policy decisions & Audit trails (REWRITE rule tracking)
2. Cost tracking & Telemetry bounds
"""

import logging
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from AgentCore.infrastructure.policy_manager import PolicyManager, PolicyDecision
from AgentCore.infrastructure.telemetry import TelemetryCollector, CostTracker
from AgentCore.domain.policy import RuntimePolicy

logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("TestRuntimeGovernance")

def test_policy_audit_trails():
    log.info("=== Starting Policy Audit Trails Validation ===")
    
    policy_manager = PolicyManager()
    
    # 1. Action allowed
    safe_req = {"command": "echo 'hello'"}
    log.info(f"Submitting safe request: {safe_req}")
    eval_safe = policy_manager.evaluate("BASH", safe_req)
    
    assert eval_safe.decision == PolicyDecision.ALLOW, "Safe request was not allowed."
    log.info("SUCCESS: Safe request allowed.")
    
    # 2. Action rewritten (Audit trail generated)
    unsafe_req = {"command": "rm -rf /cache"}
    log.info(f"Submitting unsafe request: {unsafe_req}")
    eval_rewrite = policy_manager.evaluate("BASH", unsafe_req)
    
    assert eval_rewrite.decision == PolicyDecision.REWRITE, "Destructive request was not rewritten."
    assert eval_rewrite.rewritten_action == "BASH", "Action type changed unexpectedly."
    assert "mv" in eval_rewrite.rewritten_parameters["command"], "Rewrite did not use 'mv'."
    assert "/tmp/trash" in eval_rewrite.rewritten_parameters["command"], "Rewrite did not specify safe directory."
    
    log.info(f"AUDIT TRAIL:")
    log.info(f"  Original: {unsafe_req['command']}")
    log.info(f"  Decision: {eval_rewrite.decision.name} - {eval_rewrite.reason}")
    log.info(f"  Executed: {eval_rewrite.rewritten_parameters['command']}")
    log.info("SUCCESS: Unsafe action successfully intercepted and rewritten, preserving audit trail.")
    
    log.info("=== Policy Audit Trails Validation Completed Successfully ===\n")

def test_telemetry_and_budgets():
    log.info("=== Starting Telemetry & Budget Validation ===")
    
    # Configure strict runtime limits
    budget_policy = RuntimePolicy(
        max_cost_usd=0.05,
        max_tokens=1000
    )
    
    cost_tracker = CostTracker()
    telemetry = TelemetryCollector(cost_tracker)
    
    # Simulate turn loop accumulating cost
    turn_tokens = 4000
    
    log.info(f"Configured budget: ${budget_policy.max_cost_usd} limit, {budget_policy.max_tokens} tokens")
    
    # Turn 1
    telemetry.record_llm_call(turn_id=1, prompt_tokens=turn_tokens, completion_tokens=500, latency_ms=100)
    assert telemetry.total_cost <= budget_policy.max_cost_usd, "Cost unexpectedly exceeded on Turn 1"
    
    # Turn 2
    telemetry.record_llm_call(turn_id=2, prompt_tokens=turn_tokens, completion_tokens=500, latency_ms=100)
    assert telemetry.total_cost <= budget_policy.max_cost_usd, "Cost unexpectedly exceeded on Turn 2"
    
    # Turn 3 (Should breach budget)
    telemetry.record_llm_call(turn_id=3, prompt_tokens=turn_tokens, completion_tokens=500, latency_ms=100)
    
    cost_breached = telemetry.total_cost > budget_policy.max_cost_usd
    total_tokens_recorded = sum(m.prompt_tokens + m.completion_tokens for m in telemetry.metrics.values())
    token_breached = total_tokens_recorded > budget_policy.max_tokens
    
    log.info(f"Final Telemetry -> Cost: ${telemetry.total_cost:.3f}, Tokens: {total_tokens_recorded}")
    assert cost_breached, "Cost tracker failed to register breach!"
    assert token_breached, "Token tracker failed to register breach!"
    
    log.info("SUCCESS: Telemetry accurately accumulated and flagged budget limits.")
    log.info("=== Telemetry & Budget Validation Completed Successfully ===\n")

def main():
    log.info("Initializing Milestone 4.5 Runtime Governance Test Suite")
    
    test_policy_audit_trails()
    test_telemetry_and_budgets()
    
    log.info("All Runtime Governance validations passed.")

if __name__ == "__main__":
    main()
