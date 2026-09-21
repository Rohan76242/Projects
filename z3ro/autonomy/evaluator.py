"""Z3RO — Strategy Evaluator.

Implements Section 7:
- Estimates reward, cost, time, uncertainty, and risk for candidate strategies.
- Computes expected value and feasibility scores under active constraints.
"""

from typing import Dict, Any, Tuple
from z3ro.autonomy.strategy import Strategy
from z3ro.autonomy.objective import OperationalConstraints


class StrategyEvaluator:
    """Evaluates candidate strategies to rank experiment priority."""

    def evaluate(self, strategy: Strategy, constraints: OperationalConstraints) -> Dict[str, Any]:
        """Compute comprehensive evaluation score for a candidate strategy."""
        cost = max(0.01, strategy.estimated_cost)
        reward = strategy.estimated_reward
        risk = min(1.0, max(0.0, strategy.risk_score))

        # Expected Net Return
        expected_net = reward - cost
        # Risk-adjusted Return on Investment (ROI)
        expected_roi = (expected_net / cost) * (1.0 - (risk * 0.7))

        # Capital feasibility: Strategy cost must not exceed 25% of current capital
        capital_affordable = cost <= (constraints.current_capital * 0.25)
        # Action rate feasibility
        rate_affordable = constraints.actions_remaining_hour > 0

        # Survival mode adjustment: heavily penalize high-risk/high-cost in survival mode
        if constraints.recommended_mode == "SURVIVAL_PRESERVATION":
            priority_score = expected_roi * (0.5 if cost > 10 else 1.5) * (1.0 - risk)
        else:
            priority_score = expected_roi

        return {
            "strategy_id": strategy.strategy_id,
            "expected_net": round(expected_net, 2),
            "expected_roi": round(expected_roi, 3),
            "priority_score": round(priority_score, 4),
            "capital_affordable": capital_affordable,
            "rate_affordable": rate_affordable,
            "recommended": capital_affordable and rate_affordable and (priority_score > 0),
        }


# Global strategy evaluator singleton
strategy_evaluator = StrategyEvaluator()
