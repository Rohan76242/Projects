"""Z3RO — Compliance Module.

Provides:
- LegalFilter (Pre-experiment compliance gating & rejection audit)
- JurisdictionRulesEvaluator (Licensing, anti-spam, ToS, robots.txt, consumer protection)
"""

from z3ro.compliance.jurisdiction_rules import (
    jurisdiction_evaluator,
    JurisdictionRulesEvaluator,
    ComplianceViolation,
    RuleCategory,
)
from z3ro.compliance.legal_filter import legal_filter, LegalFilter

__all__ = [
    "jurisdiction_evaluator",
    "JurisdictionRulesEvaluator",
    "ComplianceViolation",
    "RuleCategory",
    "legal_filter",
    "LegalFilter",
]
