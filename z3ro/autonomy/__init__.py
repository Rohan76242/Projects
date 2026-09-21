"""Z3RO — Autonomy Package.

Provides:
- ObjectiveManager (High-level goal and operational constraint monitoring)
- AutonomousLoopCoordinator (Autonomous discovery loop & exploration/exploitation)
- StrategyEvaluator (Risk, reward, and feasibility scoring)
- Strategy, StrategyLifecycle (Strategy data models)
"""

from z3ro.autonomy.objective import objective_manager, ObjectiveManager, OperationalConstraints
from z3ro.autonomy.strategy import Strategy, StrategyLifecycle
from z3ro.autonomy.evaluator import strategy_evaluator, StrategyEvaluator
from z3ro.autonomy.exploration import loop_coordinator, AutonomousLoopCoordinator

__all__ = [
    "objective_manager",
    "ObjectiveManager",
    "OperationalConstraints",
    "Strategy",
    "StrategyLifecycle",
    "strategy_evaluator",
    "StrategyEvaluator",
    "loop_coordinator",
    "AutonomousLoopCoordinator",
]
