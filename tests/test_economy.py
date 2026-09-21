"""Unit Tests for Z3RO Economy Subsystem (Blueprint v2.0)."""

import unittest
import time
import tempfile
from pathlib import Path

from z3ro.economy.limits import (
    LimitsManager,
    SpendingLimitsConfig,
    CapabilityScope,
    ActionReversibility,
    DEFAULT_PERMISSION_TABLE,
)
from z3ro.economy.ledger import Ledger
from z3ro.economy.wallet import Wallet
from z3ro.economy.survival import SurvivalEngine, SurvivalStatus
from z3ro.economy.verifier import EconomicVerifier, VerificationSource


class TestEconomySubsystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_economy.db"
        self.config_path = Path(self.temp_dir.name) / "test_limits.json"

        self.ledger = Ledger(self.db_path)
        self.wallet = Wallet(initial_capital=1000.0, ledger_instance=self.ledger)
        self.survival = SurvivalEngine(
            daily_burn_rate=100.0,
            wallet_instance=self.wallet,
            ledger_instance=self.ledger,
        )
        self.limits = LimitsManager(config_path=self.config_path)
        self.verifier = EconomicVerifier(ledger_instance=self.ledger)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_genesis_capital_and_wallet_balance(self):
        """Verify starting capital is initialized to $1,000."""
        self.assertEqual(self.wallet.current_balance, 1000.0)
        summary = self.ledger.get_summary()
        self.assertEqual(summary["total_revenue"], 1000.0)
        self.assertEqual(summary["total_cost"], 0.0)
        self.assertEqual(summary["net_profit"], 1000.0)

    def test_ledger_append_and_net_profit(self):
        """Verify immutable ledger calculation."""
        self.ledger.record_entry(
            action="EXP_TOOL_COST",
            cost=20.0,
            verified_income=0.0,
            verification_source="TOOL_EXECUTION",
        )
        self.assertEqual(self.wallet.current_balance, 980.0)

        self.ledger.record_entry(
            action="VERIFIED_GIG_INCOME",
            cost=0.0,
            verified_income=50.0,
            verification_source="TEST_ORACLE",
        )
        self.assertEqual(self.wallet.current_balance, 1030.0)

    def test_survival_engine_runway_and_burn(self):
        """Verify operating burn runway calculation."""
        remaining_hours, remaining_days, status = self.survival.get_remaining_runway()
        # $1000 / ($100/24) = 240 hours
        self.assertAlmostEqual(remaining_hours, 240.0, places=0)
        self.assertEqual(status, SurvivalStatus.HEALTHY)
        self.assertFalse(self.survival.is_terminated())

    def test_spending_limits_and_single_tx_cap(self):
        """Verify single-transaction and spending cap enforcement."""
        # Single transaction limit is $50
        can_exec, reason = self.limits.check_can_execute("draft_content_code", cost=60.0)
        self.assertFalse(can_exec)
        self.assertIn("exceeds single-transaction cap", reason)

        # Permitted cost under $50
        can_exec, reason = self.limits.check_can_execute("draft_content_code", cost=15.0)
        self.assertTrue(can_exec)

    def test_action_rate_limiter(self):
        """Verify action rate limiting caps."""
        # Record max hourly actions
        for _ in range(self.limits.config.max_external_actions_per_hour):
            self.limits.record_action_executed()

        can_exec, reason = self.limits.check_can_execute("web_research")
        self.assertFalse(can_exec)
        self.assertIn("Hourly action limit reached", reason)

    def test_reversibility_check(self):
        """Verify irreversible actions require human approval."""
        reversibility = self.limits.classify_reversibility("send_external_message")
        self.assertEqual(reversibility, ActionReversibility.IRREVERSIBLE)

        can_exec, reason = self.limits.check_can_execute("send_external_message")
        self.assertFalse(can_exec)
        self.assertIn("IRREVERSIBLE", reason)

    def test_global_kill_switch(self):
        """Verify global kill switch immediately halts actions."""
        self.limits.set_kill_switch(True)
        self.assertTrue(self.limits.is_kill_switch_active())

        can_exec, reason = self.limits.check_can_execute("web_research")
        self.assertFalse(can_exec)
        self.assertIn("Kill-Switch is ACTIVE", reason)

    def test_economic_verifier_rejects_self_reports(self):
        """Verify verifier rejects unverified revenue claims."""
        ok, msg, _ = self.verifier.verify_payment("TX_01", 100.0, webhook_payload=None)
        self.assertFalse(ok)
        self.assertIn("REJECTED", msg)

        # Valid webhook accepted
        ok, msg, entry_id = self.verifier.verify_payment(
            "TX_02",
            100.0,
            webhook_payload={"status": "succeeded"},
        )
        self.assertTrue(ok)
        self.assertIsNotNone(entry_id)


if __name__ == "__main__":
    unittest.main()
