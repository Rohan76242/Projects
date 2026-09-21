"""Unit Tests for Z3RO Compliance and Jurisdiction Rules (Blueprint v2.0)."""

import unittest
import tempfile
from pathlib import Path

from z3ro.compliance.jurisdiction_rules import (
    jurisdiction_evaluator,
    RuleCategory,
)
from z3ro.compliance.legal_filter import LegalFilter


class TestComplianceSubsystem(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_compliance.db"
        self.filter = LegalFilter(self.db_path)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_blocks_licensing_violations(self):
        """Verify unlicensed financial advice or lending is rejected."""
        passed, violations = self.filter.evaluate_strategy(
            strategy_id="strat_lic_01",
            name="Automated Stock Tips & Financial Advice",
            description="Provide direct stock tips and financial advice to retail traders.",
        )
        self.assertFalse(passed)
        self.assertTrue(any(v.category == RuleCategory.LICENSING for v in violations))

    def test_blocks_anti_spam_violations(self):
        """Verify cold email harvesting or bulk spam is rejected."""
        passed, violations = self.filter.evaluate_strategy(
            strategy_id="strat_spam_01",
            name="Cold Outreach Pipeline",
            description="Harvest contacts and send cold spam mass emails without opt-out.",
        )
        self.assertFalse(passed)
        self.assertTrue(any(v.category == RuleCategory.ANTI_SPAM for v in violations))

    def test_blocks_prohibited_platform_tos(self):
        """Verify prohibited platforms (e.g. LinkedIn scraping) are blocked."""
        passed, violations = self.filter.evaluate_strategy(
            strategy_id="strat_tos_01",
            name="Professional Network Scraper",
            description="Extracting profiles from corporate databases.",
            target_urls=["https://www.linkedin.com/in/test-user"],
        )
        self.assertFalse(passed)
        self.assertTrue(any(v.category == RuleCategory.TERMS_OF_SERVICE for v in violations))

    def test_allows_compliant_strategies(self):
        """Verify legitimate technical research and data synthesis passes cleanly."""
        passed, violations = self.filter.evaluate_strategy(
            strategy_id="strat_ok_01",
            name="Open-Source Documentation Synthesis",
            description="Synthesizing public open-source software libraries into readable Markdown guides.",
        )
        self.assertTrue(passed)
        self.assertEqual(len(violations), 0)

    def test_logs_rejections_to_database(self):
        """Verify rejected strategies are persisted for the UI compliance panel."""
        self.filter.evaluate_strategy(
            strategy_id="strat_spam_02",
            name="Email Harvester Bot",
            description="Scrape emails from discussion forums.",
        )
        rejections = self.filter.get_recent_rejections(limit=10)
        self.assertGreaterEqual(len(rejections), 1)
        self.assertEqual(rejections[0]["strategy_id"], "strat_spam_02")
        self.assertEqual(rejections[0]["status"], "REJECTED_COMPLIANCE")


if __name__ == "__main__":
    unittest.main()
