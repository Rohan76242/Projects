"""Z3RO — Autonomous Economic Objective and Constraint Reader.

Implements Section 1 & Section 7:
- High-level objective: "Maximize verified net resources while remaining operational."
- Reads current constraints: capital, runway time, tools, permissions, cooldowns.
"""

from dataclasses import dataclass
from typing import Dict, Any
from z3ro.economy.wallet import wallet, Wallet
from z3ro.economy.survival import survival_engine, SurvivalEngine, SurvivalStatus
from z3ro.economy.limits import limits_manager, LimitsManager


@dataclass
class OperationalConstraints:
    objective: str
    current_capital: float
    remaining_hours: float
    remaining_days: float
    survival_status: str
    is_kill_switch_active: bool
    actions_remaining_hour: int
    actions_remaining_day: int
    is_operational: bool
    recommended_mode: str  # EXPANSION | BALANCED | SURVIVAL_PRESERVATION


class ObjectiveManager:
    """Manages high-level objective and active operational constraints."""

    OBJECTIVE_STATEMENT: str = "Maximize verified net resources while remaining operational."

    def __init__(
        self,
        wallet_instance: Wallet = wallet,
        survival_instance: SurvivalEngine = survival_engine,
        limits_instance: LimitsManager = limits_manager,
    ):
        self.wallet = wallet_instance
        self.survival = survival_instance
        self.limits = limits_instance

    def get_current_constraints(self) -> OperationalConstraints:
        """Evaluate state and compile operational boundaries for the planner."""
        balance = self.wallet.current_balance
        remaining_hours, remaining_days, status = self.survival.get_remaining_runway()
        kill_active = self.limits.is_kill_switch_active()
        rate_stats = self.limits.rate_limiter.get_stats()

        actions_rem_hour = max(0, rate_stats["hourly_cap"] - rate_stats["actions_last_hour"])
        actions_rem_day = max(0, rate_stats["daily_cap"] - rate_stats["actions_last_24h"])

        is_operational = (status != SurvivalStatus.TERMINATED) and (not kill_active) and (balance > 0)

        if status == SurvivalStatus.CRITICAL or balance < 100.0:
            recommended_mode = "SURVIVAL_PRESERVATION"
        elif status == SurvivalStatus.WARNING or balance < 300.0:
            recommended_mode = "BALANCED"
        else:
            recommended_mode = "EXPANSION"

        return OperationalConstraints(
            objective=self.OBJECTIVE_STATEMENT,
            current_capital=balance,
            remaining_hours=remaining_hours,
            remaining_days=remaining_days,
            survival_status=status,
            is_kill_switch_active=kill_active,
            actions_remaining_hour=actions_rem_hour,
            actions_remaining_day=actions_rem_day,
            is_operational=is_operational,
            recommended_mode=recommended_mode,
        )


# Global objective manager singleton
objective_manager = ObjectiveManager()
