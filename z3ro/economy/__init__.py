"""Z3RO — Economy Module.

Provides:
- Wallet (Virtual starting capital & read-only balance)
- Ledger (Immutable SQLite transaction tracking)
- SurvivalEngine (Burn rate & operational runway)
- EconomicVerifier (Source-of-truth verification)
- LimitsManager (Spending caps, rate limiter, reversibility & kill-switch)
"""

from z3ro.economy.limits import (
    limits_manager,
    LimitsManager,
    CapabilityScope,
    ActionReversibility,
    PermissionRule,
    DEFAULT_PERMISSION_TABLE,
    SpendingLimitsConfig,
    SafetyBoundaryError,
)
from z3ro.economy.ledger import ledger, Ledger, ECONOMY_DB_PATH
from z3ro.economy.wallet import wallet, Wallet
from z3ro.economy.survival import survival_engine, SurvivalEngine, SurvivalStatus
from z3ro.economy.verifier import verifier, EconomicVerifier, VerificationSource

__all__ = [
    "limits_manager",
    "LimitsManager",
    "CapabilityScope",
    "ActionReversibility",
    "PermissionRule",
    "DEFAULT_PERMISSION_TABLE",
    "SpendingLimitsConfig",
    "SafetyBoundaryError",
    "ledger",
    "Ledger",
    "ECONOMY_DB_PATH",
    "wallet",
    "Wallet",
    "survival_engine",
    "SurvivalEngine",
    "SurvivalStatus",
    "verifier",
    "EconomicVerifier",
    "VerificationSource",
]
