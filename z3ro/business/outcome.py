"""Z3RO — Outcome Evaluator & Settlement.

Implements Section 7 & 10:
- Verifies created value through defined external sources.
- Credits verified income to the immutable ledger.
- Updates strategy confidence in memory based on empirical metrics.
"""

from typing import Dict, Any, Optional
from z3ro.autonomy.strategy import Strategy, StrategyLifecycle
from z3ro.business.experiment import ExperimentResult
from z3ro.economy.verifier import verifier
from z3ro.memory.strategies import strategy_memory


class OutcomeProcessor:
    """Evaluates and settles experimental outcomes."""

    def process_outcome(
        self,
        strategy: Strategy,
        exp_result: ExperimentResult,
        simulated_gain: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Verify created value, record in ledger, and update strategy confidence."""
        verified_income = 0.0
        verification_msg = "No verified value created."

        if exp_result.success:
            # In Phase 1 / simulation sandbox, calculate verified gain via Oracle
            gain = simulated_gain if simulated_gain is not None else strategy.estimated_reward
            if gain > 0:
                ok, msg, entry_id = verifier.verify_simulation_experiment_reward(
                    experiment_id=exp_result.experiment_id,
                    simulated_net_gain=gain,
                    oracle_evidence=f"EVAL_SUCCESS_{exp_result.experiment_id}",
                )
                if ok:
                    verified_income = gain
                    verification_msg = msg

        # Update Strategy Memory with measured outcomes (Section 8)
        new_conf = strategy_memory.record_outcome(
            strategy_id=strategy.strategy_id,
            capital_spent=exp_result.actual_cost,
            verified_revenue=verified_income,
            time_spent_seconds=exp_result.time_elapsed_sec,
            success=exp_result.success and (verified_income >= exp_result.actual_cost),
            failure_reason="" if exp_result.success else (exp_result.error or "Experiment failed"),
            evidence_ref=exp_result.artifact_path or exp_result.output_summary,
        )

        strategy.confidence = new_conf
        strategy.state = StrategyLifecycle.EVALUATED

        return {
            "strategy_id": strategy.strategy_id,
            "experiment_id": exp_result.experiment_id,
            "cost": exp_result.actual_cost,
            "verified_income": verified_income,
            "net_gain": round(verified_income - exp_result.actual_cost, 2),
            "new_confidence": new_conf,
            "verification_status": verification_msg,
        }


# Global outcome processor singleton
outcome_processor = OutcomeProcessor()
