"""Unit Tests for Z3RO Autonomy and Strategy Memory (Blueprint v2.0)."""

import unittest
import tempfile
from pathlib import Path

from z3ro.autonomy.objective import ObjectiveManager
from z3ro.autonomy.strategy import Strategy, StrategyLifecycle
from z3ro.autonomy.evaluator import StrategyEvaluator
from z3ro.business.opportunity_discovery import OpportunityDiscovery
from z3ro.memory.strategies import StrategyMemory
from z3ro.economy.ledger import Ledger
from z3ro.economy.wallet import Wallet
from z3ro.economy.survival import SurvivalEngine
from z3ro.economy.limits import LimitsManager


class TestAutonomySubsystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_autonomy.db"
        self.cfg_path = Path(self.temp_dir.name) / "test_limits.json"

        self.ledger = Ledger(self.db_path)
        self.wallet = Wallet(initial_capital=1000.0, ledger_instance=self.ledger)
        self.survival = SurvivalEngine(wallet_instance=self.wallet, ledger_instance=self.ledger)
        self.limits = LimitsManager(config_path=self.cfg_path)
        self.obj_manager = ObjectiveManager(
            wallet_instance=self.wallet,
            survival_instance=self.survival,
            limits_instance=self.limits,
        )
        self.strat_memory = StrategyMemory(db_path=self.db_path)
        self.evaluator = StrategyEvaluator()
        self.discovery = OpportunityDiscovery()

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_objective_constraints_reading(self):
        constraints = self.obj_manager.get_current_constraints()
        self.assertEqual(constraints.current_capital, 1000.0)
        self.assertTrue(constraints.is_operational)
        self.assertEqual(constraints.recommended_mode, "EXPANSION")

    def test_opportunity_discovery_from_capabilities(self):
        candidates = self.discovery.generate_candidate_strategies(count=2)
        self.assertGreaterEqual(len(candidates), 1)
        for c in candidates:
            self.assertIsNotNone(c.strategy_id)
            self.assertIn(c.target_capability, ["web_research", "draft_content_code"])

    def test_strategy_evaluation(self):
        constraints = self.obj_manager.get_current_constraints()
        strat = Strategy.create(
            name="Documentation Synthesis",
            description="Synthesize technical docs into structured summaries",
            target_capability="draft_content_code",
            estimated_cost=5.0,
            estimated_reward=25.0,
            risk_score=0.2,
        )
        res = self.evaluator.evaluate(strat, constraints)
        self.assertTrue(res["recommended"])
        self.assertGreater(res["expected_net"], 0.0)

    def test_strategy_memory_confidence_update(self):
        strat_id = "strat_test_01"
        self.strat_memory.save_or_update_strategy(
            strategy_id=strat_id,
            name="Test Strategy",
            description="Testing empirical updates",
        )

        # Successful positive ROI outcome updates confidence upwards
        new_conf = self.strat_memory.record_outcome(
            strategy_id=strat_id,
            capital_spent=5.0,
            verified_revenue=25.0,
            time_spent_seconds=10.0,
            success=True,
        )
        self.assertGreater(new_conf, 0.50)

        # Failure outcome penalizes confidence
        penalized_conf = self.strat_memory.record_outcome(
            strategy_id=strat_id,
            capital_spent=10.0,
            verified_revenue=0.0,
            time_spent_seconds=10.0,
            success=False,
            failure_reason="Simulated failure",
        )
        self.assertLess(penalized_conf, new_conf)


if __name__ == "__main__":
    unittest.main()
