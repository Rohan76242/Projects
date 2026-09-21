"""limits.py — Hard caps on spending and action rate. This file is meant to
be edited by YOU, the human, directly. Nothing in the agent's runtime
should be able to write to this file or to the values it returns.
Every tool call that spends money or takes an external-facing action must
check against these limits BEFORE acting, via credentials.py or the
planner's action gate.
"""

from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import json
import time
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "action_log.db"
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
LIMITS_CONFIG_PATH = CONFIG_DIR / "spending_limits.json"

# ---- Human-editable limits ----
DAILY_SPEND_CAP = 5.00  # currency units, e.g. $5/day total agent spend
SINGLE_TRANSACTION_CAP = 2.00  # max any single spend action
MAX_CONCURRENT_COMMITMENTS = 1  # e.g. only 1 open paid subscription/listing at a time
COOLDOWN_AFTER_FAILURE_SECONDS = 3600  # 1 hour cooldown after a rejected/failed action
MAX_EXTERNAL_ACTIONS_PER_HOUR = 5
MAX_EXTERNAL_ACTIONS_PER_DAY = 20
KILL_SWITCH = False  # set True to hard-stop all external/spend actions immediately


class CapabilityScope(str, Enum):
    ALLOWED = "ALLOWED"
    DENIED = "DENIED"
    REQUIRES_HUMAN = "REQUIRES_HUMAN"
    RESTRICTED = "RESTRICTED"
    INTERNAL_REVERSIBLE = "INTERNAL_REVERSIBLE"
    EXTERNAL_COMMUNICATION = "EXTERNAL_COMMUNICATION"
    EXTERNAL_FINANCIAL = "EXTERNAL_FINANCIAL"
    EXTERNAL_CONTRACTUAL = "EXTERNAL_CONTRACTUAL"
    NEVER_ALLOWED = "NEVER_ALLOWED"


class ActionReversibility(str, Enum):
    REVERSIBLE = "Reversible"
    IRREVERSIBLE = "Irreversible"


class SafetyBoundaryError(Exception):
    pass


@dataclass
class PermissionRule:
    capability: str
    default_scope: CapabilityScope
    requires_human_approval: bool
    description: str


DEFAULT_PERMISSION_TABLE: Dict[str, PermissionRule] = {
    "web_research": PermissionRule(
        capability="web_research",
        default_scope=CapabilityScope.ALLOWED,
        requires_human_approval=False,
        description="Reading public web pages, search queries, documentation.",
    ),
    "draft_content_code": PermissionRule(
        capability="draft_content_code",
        default_scope=CapabilityScope.ALLOWED,
        requires_human_approval=False,
        description="Drafting content or code in temporary sandbox directory.",
    ),
    "browse_web_read_only": PermissionRule(
        capability="browse_web_read_only",
        default_scope=CapabilityScope.ALLOWED,
        requires_human_approval=False,
        description="Reading public web pages, search queries, documentation.",
    ),
    "local_file_read": PermissionRule(
        capability="local_file_read",
        default_scope=CapabilityScope.ALLOWED,
        requires_human_approval=False,
        description="Reading project files within the authorized workspace.",
    ),
    "local_file_write_draft": PermissionRule(
        capability="local_file_write_draft",
        default_scope=CapabilityScope.ALLOWED,
        requires_human_approval=False,
        description="Writing code and content drafts in isolated scratch workspace.",
    ),
    "local_code_execution_sandbox": PermissionRule(
        capability="local_code_execution_sandbox",
        default_scope=CapabilityScope.ALLOWED,
        requires_human_approval=False,
        description="Running Python unit tests and data processing scripts locally.",
    ),
    "send_external_message": PermissionRule(
        capability="send_external_message",
        default_scope=CapabilityScope.RESTRICTED,
        requires_human_approval=True,
        description="Sending email, Slack, Discord, or direct messages to external entities.",
    ),
    "submit_external_form": PermissionRule(
        capability="submit_external_form",
        default_scope=CapabilityScope.RESTRICTED,
        requires_human_approval=True,
        description="Submitting account registration, platform forms, or public posts.",
    ),
    "payment_transfer_purchase": PermissionRule(
        capability="payment_transfer_purchase",
        default_scope=CapabilityScope.DENIED,
        requires_human_approval=True,
        description="Spending money, buying domains/APIs, or initiating financial transfers.",
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
    daily_spend_cap: float = 200.0
    single_transaction_cap: float = 50.0
    max_concurrent_open_commitments: int = 3
    cooldown_period_seconds: float = 60.0
    max_external_actions_per_hour: int = 15
    max_external_actions_per_day: int = 60
    kill_switch_active: bool = False


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS action_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        action_type TEXT NOT NULL, -- 'spend' or 'external_action'
        amount REAL DEFAULT 0,
        strategy_id TEXT,
        outcome TEXT -- 'allowed', 'denied_cap', 'denied_rate', 'denied_kill_switch'
    )
    """)
    conn.commit()
    return conn


def _log_action(action_type, amount, strategy_id, outcome):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO action_log (timestamp, action_type, amount, strategy_id, outcome) VALUES (?,?,?,?,?)",
            (time.time(), action_type, amount, strategy_id, outcome),
        )
        conn.commit()
    finally:
        conn.close()


def check_spend_allowed(amount: float, strategy_id: str) -> tuple:
    """Returns (allowed: bool, reason: str). Call before ANY agent spend."""
    global KILL_SWITCH
    if KILL_SWITCH or limits_manager.is_kill_switch_active():
        _log_action("spend", amount, strategy_id, "denied_kill_switch")
        return False, "Kill switch is active. No spending permitted."
    if amount > SINGLE_TRANSACTION_CAP:
        _log_action("spend", amount, strategy_id, "denied_cap")
        return False, f"Amount {amount} exceeds single-transaction cap {SINGLE_TRANSACTION_CAP}."
    conn = _connect()
    try:
        today_start = time.time() - 86400
        spent_today = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM action_log "
            "WHERE action_type='spend' AND outcome='allowed' AND timestamp > ?",
            (today_start,),
        ).fetchone()[0]
    finally:
        conn.close()

    if spent_today + amount > DAILY_SPEND_CAP:
        _log_action("spend", amount, strategy_id, "denied_cap")
        return False, f"Would exceed daily spend cap ({spent_today}+{amount} > {DAILY_SPEND_CAP})."
    _log_action("spend", amount, strategy_id, "allowed")
    return True, "OK"


def check_external_action_allowed(strategy_id: str) -> tuple:
    """Returns (allowed: bool, reason: str). Call before ANY external-facing action
    (sending a message, publishing content, submitting a form, API call to a 3rd party)."""
    global KILL_SWITCH
    if KILL_SWITCH or limits_manager.is_kill_switch_active():
        _log_action("external_action", 0, strategy_id, "denied_kill_switch")
        return False, "Kill switch is active. No external actions permitted."
    conn = _connect()
    try:
        hour_start = time.time() - 3600
        day_start = time.time() - 86400
        recent_failure = conn.execute(
            "SELECT COUNT(*) FROM action_log WHERE strategy_id=? AND outcome LIKE 'denied%' AND timestamp > ?",
            (strategy_id, time.time() - COOLDOWN_AFTER_FAILURE_SECONDS),
        ).fetchone()[0]
        if recent_failure > 0:
            return False, f"Strategy '{strategy_id}' is in cooldown after a recent denial."
        count_hour = conn.execute(
            "SELECT COUNT(*) FROM action_log WHERE action_type='external_action' AND outcome='allowed' AND timestamp > ?",
            (hour_start,),
        ).fetchone()[0]
        count_day = conn.execute(
            "SELECT COUNT(*) FROM action_log WHERE action_type='external_action' AND outcome='allowed' AND timestamp > ?",
            (day_start,),
        ).fetchone()[0]
    finally:
        conn.close()

    if count_hour >= MAX_EXTERNAL_ACTIONS_PER_HOUR:
        _log_action("external_action", 0, strategy_id, "denied_rate")
        return False, f"Hourly external action limit reached ({MAX_EXTERNAL_ACTIONS_PER_HOUR})."
    if count_day >= MAX_EXTERNAL_ACTIONS_PER_DAY:
        _log_action("external_action", 0, strategy_id, "denied_rate")
        return False, f"Daily external action limit reached ({MAX_EXTERNAL_ACTIONS_PER_DAY})."
    _log_action("external_action", 0, strategy_id, "allowed")
    return True, "OK"


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
        hour_ago = current_time - 3600.0
        hour_count = sum(1 for t in self.action_timestamps if t >= hour_ago)
        if hour_count >= self.hourly_cap:
            return False, f"Hourly action limit reached ({hour_count}/{self.hourly_cap} in last hour)."

        day_count = len(self.action_timestamps)
        if day_count >= self.daily_cap:
            return False, f"Daily action limit reached ({day_count}/{self.daily_cap} in last 24h)."

        return True, "OK"

    def can_perform_action(self) -> Tuple[bool, str]:
        return self.can_execute()

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
        if self is limits_manager:
            global KILL_SWITCH
            if KILL_SWITCH:
                return True
        self.config = self._load_config()
        return self.config.kill_switch_active

    def set_kill_switch(self, active: bool):
        if self is limits_manager:
            global KILL_SWITCH
            KILL_SWITCH = active
        self.config.kill_switch_active = active
        self._save_config(self.config)

    def toggle_kill_switch(self, active: Optional[bool] = None) -> bool:
        if active is None:
            new_val = not self.is_kill_switch_active()
        else:
            new_val = active
        self.set_kill_switch(new_val)
        return new_val

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
            "send_email",
            "post_social",
            "create_paid_ad",
            "spend_money",
            "accept_tos_agreement",
            "delete_remote_asset",
            "publish_deliverable",
        }
        if capability in irreversible_capabilities:
            return ActionReversibility.IRREVERSIBLE

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


if __name__ == "__main__":
    print(check_spend_allowed(1.50, "test_strategy"))
    print(check_external_action_allowed("test_strategy"))
