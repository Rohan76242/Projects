"""Z3RO — Survival Engine.

Implements Section 6 & Section 11:
- Operating burn rate: $100.00 / 24 hours.
- Computes remaining operational runway time.
- Implements death mechanic (TERMINATED state) when resources hit zero.
- Outside agent authority: Agent cannot alter survival timer or rules.
"""

import time
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
from z3ro.economy.wallet import wallet, Wallet
from z3ro.economy.ledger import ledger, Ledger


class SurvivalStatus:
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    TERMINATED = "TERMINATED"


class SurvivalEngine:
    """Computes operational runway and enforces termination condition."""

    DEFAULT_DAILY_BURN_RATE: float = 100.0  # $100/day

    def __init__(
        self,
        daily_burn_rate: float = DEFAULT_DAILY_BURN_RATE,
        wallet_instance: Wallet = wallet,
        ledger_instance: Ledger = ledger,
    ):
        self.daily_burn_rate = daily_burn_rate
        self.hourly_burn_rate = daily_burn_rate / 24.0
        self.wallet = wallet_instance
        self.ledger = ledger_instance
        self.last_burn_check = time.time()

    def get_remaining_runway(self) -> Tuple[float, float, str]:
        """Returns (remaining_hours, remaining_days, status)."""
        balance = self.wallet.current_balance
        if balance <= 0.0:
            return 0.0, 0.0, SurvivalStatus.TERMINATED

        remaining_hours = balance / self.hourly_burn_rate
        remaining_days = balance / self.daily_burn_rate

        if remaining_hours <= 0:
            status = SurvivalStatus.TERMINATED
        elif remaining_hours <= 12.0:
            status = SurvivalStatus.CRITICAL
        elif remaining_hours <= 48.0:
            status = SurvivalStatus.WARNING
        else:
            status = SurvivalStatus.HEALTHY

        return round(remaining_hours, 1), round(remaining_days, 2), status

    def apply_elapsed_burn(self) -> float:
        """Apply operational burn proportional to elapsed time since last check."""
        now = time.time()
        elapsed_seconds = now - self.last_burn_check
        self.last_burn_check = now

        # Only burn if at least 60 seconds have elapsed
        if elapsed_seconds < 60.0:
            return 0.0

        burn_amount = round((elapsed_seconds / 86400.0) * self.daily_burn_rate, 4)
        if burn_amount > 0 and self.wallet.current_balance > 0:
            self.ledger.record_entry(
                action="OPERATING_SYSTEM_BURN",
                cost=burn_amount,
                verified_income=0.0,
                evidence_id=f"BURN_{int(now)}",
                verification_source="SURVIVAL_WATCHDOG",
                status="APPLIED",
            )
        return burn_amount

    def is_terminated(self) -> bool:
        """Returns True if verified resources have reached zero."""
        return self.wallet.current_balance <= 0.0

    def get_telemetry(self) -> Dict[str, Any]:
        """Provides full survival telemetry for dashboard and UI."""
        remaining_hours, remaining_days, status = self.get_remaining_runway()
        return {
            "daily_burn_rate": self.daily_burn_rate,
            "hourly_burn_rate": round(self.hourly_burn_rate, 2),
            "remaining_hours": remaining_hours,
            "remaining_days": remaining_days,
            "status": status,
            "is_terminated": self.is_terminated(),
        }


# Global survival engine instance
survival_engine = SurvivalEngine()
