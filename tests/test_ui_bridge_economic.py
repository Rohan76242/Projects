"""Unit Tests for UI Bridge Telemetry and Economic Controls (Blueprint v2.0)."""

import unittest
from z3ro.dashboard.app import get_full_dashboard_state
from z3ro.economy.limits import limits_manager
from z3ro.tools.communication import approval_queue


class TestUIBridgeEconomic(unittest.TestCase):

    def test_dashboard_state_schema(self):
        """Verify get_full_dashboard_state produces all keys required by UI and blueprint."""
        state = get_full_dashboard_state()
        self.assertIn("wallet", state)
        self.assertIn("survival", state)
        self.assertIn("limits", state)
        self.assertIn("pending_approvals", state)
        self.assertIn("compliance_rejections", state)
        self.assertIn("strategies", state)
        self.assertIn("recent_ledger", state)

        # Wallet fields
        self.assertIn("balance", state["wallet"])
        self.assertIn("net_profit", state["wallet"])

        # Survival fields
        self.assertIn("burn_rate_daily", state["survival"])
        self.assertIn("remaining_hours", state["survival"])
        self.assertIn("status", state["survival"])

        # Limits fields
        self.assertIn("kill_switch_active", state["limits"])
        self.assertIn("daily_spend_cap", state["limits"])
        self.assertIn("hourly_cap", state["limits"])

    def test_kill_switch_toggle(self):
        """Verify kill-switch toggles properly."""
        initial = limits_manager.is_kill_switch_active()
        limits_manager.set_kill_switch(not initial)
        self.assertEqual(limits_manager.is_kill_switch_active(), not initial)
        # Restore
        limits_manager.set_kill_switch(initial)

    def test_approval_queue_enqueue_and_resolve(self):
        """Verify human approvals flow."""
        item = approval_queue.submit_for_approval(
            capability="send_external_message",
            recipient="test@example.com",
            message="Hello external user",
            estimated_cost=0.0,
        )
        self.assertEqual(item.reversibility, "Irreversible")

        pending = approval_queue.get_pending()
        self.assertTrue(any(p["action_id"] == item.action_id for p in pending))

        # Approve
        resolved = approval_queue.resolve_action(item.action_id, approved=True, notes="Test approved")
        self.assertTrue(resolved)

        # No longer pending
        pending_after = approval_queue.get_pending()
        self.assertFalse(any(p["action_id"] == item.action_id for p in pending_after))


if __name__ == "__main__":
    unittest.main()
