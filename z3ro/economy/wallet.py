"""Z3RO — Isolated Virtual Wallet.

Implements Section 6:
- Virtual starting capital: $1,000.00.
- Read-only balance calculated directly from verified ledger entries.
- Agent cannot directly edit balance.
"""

from typing import Dict
from z3ro.economy.ledger import ledger, Ledger


class Wallet:
    """Isolated, read-only wallet reflecting verified economic resources."""

    DEFAULT_INITIAL_CAPITAL: float = 1000.0

    def __init__(self, initial_capital: float = DEFAULT_INITIAL_CAPITAL, ledger_instance: Ledger = ledger):
        self.initial_capital = initial_capital
        self._ledger = ledger_instance
        self._ensure_genesis_deposit()

    def _ensure_genesis_deposit(self):
        """Ensure initial capital is recorded if the ledger is completely empty."""
        summary = self._ledger.get_summary()
        if summary["total_entries"] == 0:
            self._ledger.record_entry(
                action="GENESIS_VIRTUAL_CAPITAL_DEPOSIT",
                cost=0.0,
                verified_income=self.initial_capital,
                evidence_id="GENESIS_001",
                verification_source="SYSTEM_INITIALIZER",
                status="VERIFIED",
            )

    @property
    def current_balance(self) -> float:
        """Read-only balance: initial capital + net earnings from verified transactions."""
        summary = self._ledger.get_summary()
        # Genesis deposit is recorded as verified income, so total net_profit is the exact balance
        return max(0.0, round(summary["net_profit"], 2))

    def get_wallet_state(self) -> Dict[str, float]:
        """Telemetry snapshot for UI and planner."""
        summary = self._ledger.get_summary()
        return {
            "initial_capital": self.initial_capital,
            "current_balance": self.current_balance,
            "verified_revenue": summary["total_revenue"],
            "total_costs": summary["total_cost"],
            "net_profit": summary["net_profit"] - self.initial_capital,  # Profit excluding seed capital
        }


# Global singleton instance
wallet = Wallet()
