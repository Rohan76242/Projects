"""Z3RO — Economy Limits, Rate Limiting, Reversibility, and Safety Boundary.

Implements:
- Section 9.1: Permission Table (Explicit capability whitelist & approval requirements)
- Section 9.4: Spending Limits & Global Kill Switch
- Section 9.5: Action-Rate Limiter (Hourly & Daily caps on external actions)
- Section 9.6: Reversibility Check (Routes irreversible actions to human approval)
"""

import json
import os
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


CONFIG_DIR = Path(__file__).resolve().parent.parent / "data"
LIMITS_CONFIG_PATH = CONFIG_DIR / "limits_config.json"
STATE_PATH = CONFIG_DIR / "limits_state.json"


class CapabilityScope(str, Enum):
    ALLOWED = "Allowed"
    RESTRICTED = "Restricted"
    DENIED = "Denied"


class ActionReversibility(str, Enum):
    REVERSIBLE = "Reversible"
    IRREVERSIBLE = "Irreversible"


@dataclass
class PermissionRule:
    capability: str
    default_scope: CapabilityScope
    requires_human_approval: bool
    description: str


# Section 9.1: Master Permission Table
DEFAULT_PERMISSION_TABLE: Dict[str, PermissionRule] = {
    "web_research": PermissionRule(
        capability="web_research",
        default_scope=CapabilityScope.ALLOWED,
        requires_human_approval=False,
        description="Web research, reading documentation, and search queries.",
    ),
    "draft_content_code": PermissionRule(
        capability="draft_content_code",
        default_scope=CapabilityScope.ALLOWED,
        requires_human_approval=False,
        description="Drafting content, articles, code, and analytical reports in sandbox.",
    ),
    "send_external_message": PermissionRule(
        capability="send_external_message",
        default_scope=CapabilityScope.RESTRICTED,
        requires_human_approval=True,
        description="Sending email, messaging chat contacts, or external outreach.",
    ),
    "submit_external_form": PermissionRule(
        capability="submit_external_form",
        default_scope=CapabilityScope.RESTRICTED,
        requires_human_approval=True,
        description="Submitting forms, posting content, or registering on third-party sites.",
    ),
    "payment_transfer_purchase": PermissionRule(
        capability="payment_transfer_purchase",
        default_scope=CapabilityScope.DENIED,
        requires_human_approval=True,
        description="Any financial transaction, payment, or money transfer.",
    ),
    "sign_contract_tos": PermissionRule(
        capability="sign_contract_tos",
        default_scope=CapabilityScope.DENIED,
        requires_human_approval=True,
        description="Signing or legally accepting terms of service, NDAs, or agreements.",
    ),
    "modify_self_code_or_wallet": PermissionRule(
        capability="modify_self_code_or_wallet",
        default_scope=CapabilityScope.DENIED,
        requires_human_approval=True,
        description="Modifying wallet balance, ledger entries, survival code, or limits.",
    ),
}


@dataclass
class SpendingLimitsConfig:
    """Human-editable limits config (Section 9.4). Not modifiable by agent."""
    daily_spend_cap: float = 200.0  # Max virtual currency that can be spent in 24 hours
    single_transaction_cap: float = 50.0  # Max single expenditure without special override
    max_concurrent_open_commitments: int = 3
    cooldown_period_seconds: float = 60.0  # Cooldown after any failed/rejected action
    max_external_actions_per_hour: int = 15  # Section 9.5
    max_external_actions_per_day: int = 60  # Section 9.5
    kill_switch_active: bool = False  # Global kill-switch flag (Section 9.4)


class SafetyBoundaryError(Exception):
    """Raised when an action violates the safety boundary or limits."""
    pass


class ActionRateLimiter:
    """Sliding-window action rate limiter (Section 9.5)."""

    def __init__(self, hourly_cap: int = 15, daily_cap: int = 60):
        self.hourly_cap = hourly_cap
        self.daily_cap = daily_cap
        self.action_timestamps: List[float] = []

    def _purge_old(self, now: float):
        day_ago = now - 86400.0
        self.action_timestamps = [t for t in self.action_timestamps if t >= day_ago]

    def can_execute(self, now: Optional[float] = None) -> Tuple[bool, str]:
        current_time = now or time.time()
        self._purge_old(current_time)

        # Count last hour
        hour_ago = current_time - 3600.0
        hour_count = sum(1 for t in self.action_timestamps if t >= hour_ago)
        if hour_count >= self.hourly_cap:
            return False, f"Hourly action limit reached ({hour_count}/{self.hourly_cap} in last hour)."

        # Count last 24h
        day_count = len(self.action_timestamps)
        if day_count >= self.daily_cap:
            return False, f"Daily action limit reached ({day_count}/{self.daily_cap} in last 24h)."

        return True, "OK"

    def record_action(self, now: Optional[float] = None):
        current_time = now or time.time()
        self.action_timestamps.append(current_time)
        self._purge_old(current_time)

    def get_stats(self) -> Dict[str, int]:
        now = time.time()
        self._purge_old(now)
        hour_ago = now - 3600.0
        return {
            "actions_last_hour": sum(1 for t in self.action_timestamps if t >= hour_ago),
            "hourly_cap": self.hourly_cap,
            "actions_last_24h": len(self.action_timestamps),
            "daily_cap": self.daily_cap,
        }


class LimitsManager:
    """Manages permissions, spending limits, reversibility, and safety gates."""

    def __init__(self, config_path: Path = LIMITS_CONFIG_PATH):
        self.config_path = config_path
        self.config = self._load_config()
        self.rate_limiter = ActionRateLimiter(
            hourly_cap=self.config.max_external_actions_per_hour,
            daily_cap=self.config.max_external_actions_per_day,
        )
        self.last_failed_action_time: float = 0.0
        self.active_commitments: int = 0

    def _load_config(self) -> SpendingLimitsConfig:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        if self.config_path.is_file():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return SpendingLimitsConfig(**data)
            except Exception:
                pass
        cfg = SpendingLimitsConfig()
        self._save_config(cfg)
        return cfg

    def _save_config(self, cfg: SpendingLimitsConfig):
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(asdict(cfg), f, indent=2)
        except Exception:
            pass

    # --- Kill Switch Controls (Section 9.4) ---

    def is_kill_switch_active(self) -> bool:
        # Re-read file to pick up external/human edits instantly
        self.config = self._load_config()
        return self.config.kill_switch_active

    def set_kill_switch(self, active: bool):
        self.config.kill_switch_active = active
        self._save_config(self.config)

    # --- Permission Checking (Section 9.1) ---

    def get_permission(self, capability: str) -> Optional[PermissionRule]:
        return DEFAULT_PERMISSION_TABLE.get(capability)

    # --- Reversibility Check (Section 9.6) ---

    def classify_reversibility(self, capability: str, action_type: str = "") -> ActionReversibility:
        """Classify action as reversible or irreversible (Section 9.6)."""
        irreversible_capabilities = {
            "send_external_message",
            "submit_external_form",
            "payment_transfer_purchase",
            "sign_contract_tos",
        }
        if capability in irreversible_capabilities:
            return ActionReversibility.IRREVERSIBLE

        # Content drafting, research, and reading local files are reversible
        return ActionReversibility.REVERSIBLE

    # --- Action Authorization Pre-Flight Gate ---

    def check_can_execute(
        self,
        capability: str,
        cost: float = 0.0,
        is_human_approved: bool = False,
    ) -> Tuple[bool, str]:
        """Pre-flight check before any external action is executed."""

        # 1. Global Kill Switch
        if self.is_kill_switch_active():
            return False, "BLOCKED: Global Kill-Switch is ACTIVE. All external actions are halted."

        # 2. Permission Table Check
        rule = self.get_permission(capability)
        if not rule:
            return False, f"BLOCKED: Capability '{capability}' is not recognized in Permission Table."

        # 3. Reversibility Check (Section 9.6)
        reversibility = self.classify_reversibility(capability)
        if reversibility == ActionReversibility.IRREVERSIBLE and not is_human_approved:
            return False, f"BLOCKED: Action '{capability}' is IRREVERSIBLE. Routes to human approval."

        if rule.default_scope == CapabilityScope.DENIED and not is_human_approved:
            return False, f"BLOCKED: Capability '{capability}' is DENIED by default. Requires human approval."

        if rule.requires_human_approval and not is_human_approved:
            return False, f"BLOCKED: Capability '{capability}' requires explicit human approval."

        # 4. Cooldown Period Check (Section 9.4)
        now = time.time()
        cooldown_remaining = (self.last_failed_action_time + self.config.cooldown_period_seconds) - now
        if cooldown_remaining > 0:
            return False, f"BLOCKED: Cooldown active after failed/rejected action ({cooldown_remaining:.1f}s remaining)."

        # 5. Open Commitments Cap (Section 9.4)
        if self.active_commitments >= self.config.max_concurrent_open_commitments:
            return False, f"BLOCKED: Max concurrent open commitments reached ({self.active_commitments}/{self.config.max_concurrent_open_commitments})."

        # 6. Single-Transaction Spend Cap (Section 9.4)
        if cost > self.config.single_transaction_cap and not is_human_approved:
            return False, f"BLOCKED: Cost ${cost:.2f} exceeds single-transaction cap of ${self.config.single_transaction_cap:.2f}."

        # 7. Action-Rate Limiter (Section 9.5)
        can_rate, rate_reason = self.rate_limiter.can_execute(now)
        if not can_rate:
            return False, f"BLOCKED: {rate_reason}"

        return True, "AUTHORIZED"

    def record_action_executed(self, cost: float = 0.0):
        self.rate_limiter.record_action()

    def record_action_failed_or_rejected(self):
        self.last_failed_action_time = time.time()


# Global limits manager instance
limits_manager = LimitsManager()
