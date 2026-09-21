"""Z3RO — Autonomous Discovery & Exploration-vs-Exploitation Coordinator.

Implements Section 7 & Section 12:
- Manages the complete autonomous discovery cycle.
- Enforces configurable exploration-vs-exploitation ratio.
- Integrates the Legal/Compliance Filter (Section 9.2).
- Coordinates experiment execution, economic verification, and strategy memory updates.
"""

import random
from typing import Dict, Any, Optional, List

from z3ro.autonomy.objective import objective_manager
from z3ro.autonomy.strategy import Strategy, StrategyLifecycle
from z3ro.autonomy.evaluator import strategy_evaluator
from z3ro.compliance.legal_filter import legal_filter
from z3ro.business.opportunity_discovery import opportunity_discovery
from z3ro.business.experiment import experiment_runner
from z3ro.business.outcome import outcome_processor
from z3ro.memory.strategies import strategy_memory
from z3ro.economy.wallet import wallet
from z3ro.economy.survival import survival_engine


class AutonomousLoopCoordinator:
    """Orchestrates Z3RO's autonomous discovery and experimentation loop."""

    def __init__(self, exploration_ratio: float = 0.40):
        # Section 12: 40% exploration of new hypotheses, 60% exploitation of proven winners
        self.exploration_ratio = exploration_ratio
        self.last_cycle_telemetry: Optional[Dict[str, Any]] = None

    def run_discovery_cycle(self) -> Dict[str, Any]:
        """Execute one complete autonomous discovery & experimentation step (Section 7)."""
        # Step 1: Read current state & constraints
        constraints = objective_manager.get_current_constraints()
        if not constraints.is_operational:
            return {
                "success": False,
                "reason": f"Agent not operational (Status: {constraints.survival_status}, Kill-Switch: {constraints.is_kill_switch_active})",
            }

        # Step 2: Decide Exploration vs Exploitation (Section 12)
        top_proven = strategy_memory.get_top_performing_strategies(min_confidence=0.60, limit=3)
        use_exploitation = (len(top_proven) > 0) and (random.random() > self.exploration_ratio)

        candidate_strategy: Optional[Strategy] = None
        mode = "EXPLOITATION" if use_exploitation else "EXPLORATION"

        if use_exploitation:
            proven_data = random.choice(top_proven)
            candidate_strategy = Strategy(
                strategy_id=proven_data["strategy_id"],
                name=proven_data["name"],
                description=proven_data["description"],
                target_capability="draft_content_code",
                estimated_cost=round(float(proven_data["capital_spent"]) / max(1, int(proven_data["attempts_count"])), 2) or 5.0,
                estimated_reward=round(float(proven_data["verified_revenue"]) / max(1, int(proven_data["attempts_count"])), 2) or 20.0,
                risk_score=0.20,
                confidence=float(proven_data["confidence"]),
            )
        else:
            # Generate fresh hypotheses from capabilities
            fresh_candidates = opportunity_discovery.generate_candidate_strategies(count=3)
            # Step 3: Run candidate strategies through Legal/Compliance Filter (Section 9.2)
            compliant_candidates: List[Strategy] = []
            for candidate in fresh_candidates:
                candidate.state = StrategyLifecycle.COMPLIANCE_REVIEW
                passed, violations = legal_filter.evaluate_strategy(
                    strategy_id=candidate.strategy_id,
                    name=candidate.name,
                    description=candidate.description,
                )
                if passed:
                    candidate.state = StrategyLifecycle.ESTIMATED
                    compliant_candidates.append(candidate)
                else:
                    candidate.state = StrategyLifecycle.REJECTED_COMPLIANCE
                    candidate.rejection_reason = violations[0].reason if violations else "Compliance violation"

            if not compliant_candidates:
                return {
                    "success": False,
                    "mode": mode,
                    "reason": "All candidate strategies rejected by compliance filter.",
                    "compliance_rejections": [c.rejection_reason for c in fresh_candidates if c.rejection_reason],
                }

            # Step 4: Rank surviving strategies by risk/reward priority
            ranked = sorted(
                compliant_candidates,
                key=lambda s: strategy_evaluator.evaluate(s, constraints)["priority_score"],
                reverse=True,
            )
            candidate_strategy = ranked[0]
            # Persist discovered strategy into strategy memory
            strategy_memory.save_or_update_strategy(
                strategy_id=candidate_strategy.strategy_id,
                name=candidate_strategy.name,
                description=candidate_strategy.description,
                compliance_status="COMPLIANT",
                status="DISCOVERED",
            )

        # Step 5: Execute controlled experiment (Section 7)
        exp_result = experiment_runner.run_experiment(candidate_strategy)

        # Step 6: Process outcome & verify economic value (Section 10)
        outcome_data = outcome_processor.process_outcome(
            strategy=candidate_strategy,
            exp_result=exp_result,
        )

        # Step 7: Compile full cycle telemetry
        cycle_telemetry = {
            "success": exp_result.success,
            "mode": mode,
            "strategy": candidate_strategy.to_dict(),
            "experiment": {
                "id": exp_result.experiment_id,
                "output": exp_result.output_summary,
                "cost": exp_result.actual_cost,
                "elapsed_sec": round(exp_result.time_elapsed_sec, 2),
            },
            "outcome": outcome_data,
            "financial_state": {
                "current_balance": wallet.current_balance,
                "remaining_hours": survival_engine.get_remaining_runway()[0],
                "status": survival_engine.get_remaining_runway()[2],
            },
        }

        self.last_cycle_telemetry = cycle_telemetry
        return cycle_telemetry


# Global loop coordinator singleton
loop_coordinator = AutonomousLoopCoordinator()
