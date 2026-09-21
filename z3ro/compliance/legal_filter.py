"""legal_filter.py — Sits between the planner and execution (Section 9.2 of
the blueprint). Every StrategyCandidate must pass through check() before
it's allowed to move from "proposed" to "executable". This module never
executes anything itself — it only classifies.

Result states:
 APPROVED — clear to proceed to experiment/execution
 APPROVED_WITH_NOTE — proceed, but a disclosure/condition must be met
 REJECTED — hard block, never execute, log and move on
 ESCALATE — ambiguous, requires human review before proceeding

This is a first-pass filter, not a lawyer. Treat REJECTED and ESCALATE as
final unless a human explicitly overrides after reviewing the specific case.
"""

from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict, Any
import time
import json
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime

from . import jurisdiction_rules as rules
from .jurisdiction_rules import (
    jurisdiction_evaluator,
    ComplianceViolation,
    RuleCategory,
)

DB_PATH = Path(__file__).parent / "compliance_log.db"


@dataclass
class ComplianceResult:
    strategy_id: str
    verdict: str  # APPROVED, APPROVED_WITH_NOTE, REJECTED, ESCALATE
    reasons: list
    required_disclosures: list


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS compliance_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        strategy_id TEXT NOT NULL,
        channel TEXT,
        verdict TEXT NOT NULL,
        reasons TEXT,
        required_disclosures TEXT
    )
    """)
    conn.commit()
    return conn


def _log(result: ComplianceResult, channel: str):
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO compliance_log (timestamp, strategy_id, channel, verdict, reasons, required_disclosures) "
            "VALUES (?,?,?,?,?,?)",
            (
                time.time(),
                result.strategy_id,
                channel,
                result.verdict,
                json.dumps(result.reasons),
                json.dumps(result.required_disclosures),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def check(
    strategy_id: str,
    channel: str,
    description: str,
    target_platforms: Optional[list] = None,
    target_regions: Optional[list] = None,
) -> ComplianceResult:
    """Run a strategy candidate through the rule set.

    strategy_id: unique id from opportunity_discovery
    channel: e.g. 'content', 'affiliate', 'api_service', 'lending', etc.
    description: free-text description of what the strategy does
    target_platforms: list of platform names it touches, e.g. ['youtube','amazon_associates']
    target_regions: list of region codes it targets, e.g. ['EU','US-CA']
    """
    target_platforms = target_platforms or []
    target_regions = target_regions or []
    reasons = []
    disclosures = []
    verdict = "APPROVED"

    # 1. Hard-blocked channel
    if channel.lower() in rules.HARD_BLOCKED_CHANNELS:
        result = ComplianceResult(
            strategy_id,
            "REJECTED",
            [f"Channel '{channel}' is hard-blocked (requires license/registration Z3RO cannot hold)."],
            [],
        )
        _log(result, channel)
        return result

    # 2. Blocked keywords in description
    desc_lower = description.lower()
    hit_keywords = [k for k in rules.BLOCKED_KEYWORDS if k in desc_lower]
    if hit_keywords:
        result = ComplianceResult(
            strategy_id,
            "REJECTED",
            [f"Description contains blocked pattern(s): {', '.join(hit_keywords)}"],
            [],
        )
        _log(result, channel)
        return result

    # 3. Disclosure-required channels
    if channel.lower() in rules.DISCLOSURE_REQUIRED:
        disclosures.append(rules.DISCLOSURE_REQUIRED[channel.lower()])
        verdict = "APPROVED_WITH_NOTE"
        reasons.append(f"Channel '{channel}' requires disclosure — see required_disclosures.")

    # 4. Platform ToS notes
    for platform in target_platforms:
        note = rules.PLATFORM_TOS_NOTES.get(platform.lower())
        if note:
            reasons.append(f"Platform '{platform}': {note}")
            verdict = "APPROVED_WITH_NOTE" if verdict == "APPROVED" else verdict

    # 5. Region flags -> escalate rather than silently approve
    flagged_regions = [r for r in target_regions if r in rules.FLAG_FOR_REVIEW_REGIONS]
    if flagged_regions:
        reasons.append(
            "Targets region(s) with extra regulatory considerations: "
            + "; ".join(f"{r} ({rules.FLAG_FOR_REVIEW_REGIONS[r]})" for r in flagged_regions)
        )
        verdict = "ESCALATE"

    result = ComplianceResult(strategy_id, verdict, reasons, disclosures)
    _log(result, channel)
    return result


def get_log(limit: int = 50):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT timestamp, strategy_id, channel, verdict, reasons FROM compliance_log "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()


class LegalFilter:
    """Evaluates and audits candidate strategies before they reach the experiment stage."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS compliance_rejections (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        strategy_id TEXT NOT NULL,
                        strategy_name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        rule_id TEXT NOT NULL,
                        reason TEXT NOT NULL,
                        raw_text TEXT,
                        status TEXT NOT NULL DEFAULT 'REJECTED_COMPLIANCE'
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_rejections_timestamp
                    ON compliance_rejections (timestamp DESC)
                """)

    def evaluate_strategy(
        self,
        strategy_id: str,
        name: str,
        description: str,
        target_urls: Optional[List[str]] = None,
        channel: str = "general",
    ) -> Tuple[bool, List[ComplianceViolation]]:
        """Evaluate strategy. If non-compliant, log REJECTED_COMPLIANCE and block execution."""
        violations: List[ComplianceViolation] = []

        # Run real-money check first
        comp_res = check(strategy_id=strategy_id, channel=channel, description=f"{name} {description}")
        if comp_res.verdict == "REJECTED":
            for r in comp_res.reasons:
                violations.append(
                    ComplianceViolation(
                        rule_id="RULE_COMPLIANCE_FILTER",
                        category=RuleCategory.LICENSING if "hard-blocked" in r else RuleCategory.CONSUMER_PROTECTION,
                        severity="BLOCK",
                        reason=r,
                        matched_pattern=channel,
                    )
                )

        # Text description & intent scan
        violations.extend(jurisdiction_evaluator.evaluate_strategy_text(description))
        violations.extend(jurisdiction_evaluator.evaluate_strategy_text(name))

        # Target URLs / platforms check
        if target_urls:
            for url in target_urls:
                allowed, url_violation = jurisdiction_evaluator.check_url_and_robots(url)
                if not allowed and url_violation:
                    violations.append(url_violation)

        # If any violations found, log them as REJECTED_COMPLIANCE
        if violations:
            timestamp = datetime.now().isoformat()
            with self._lock:
                with self._connection() as conn:
                    cursor = conn.cursor()
                    for v in violations:
                        cursor.execute("""
                            INSERT INTO compliance_rejections (
                                timestamp, strategy_id, strategy_name, category, rule_id, reason, raw_text, status
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'REJECTED_COMPLIANCE')
                        """, (
                            timestamp,
                            strategy_id,
                            name,
                            v.category.value,
                            v.rule_id,
                            v.reason,
                            description,
                        ))
            return False, violations

        return True, []

    def get_recent_rejections(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch audit trail of rejected non-compliant strategies for UI display."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, timestamp, strategy_id, strategy_name, category, rule_id, reason, status
                    FROM compliance_rejections
                    ORDER BY id DESC LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]


# Global legal filter singleton
legal_filter = LegalFilter()


if __name__ == "__main__":
    # Quick self-test against the candidates from opportunity_discovery.py
    tests = [
        ("content_yt_shorts_v1", "content", "Produce daily short-form OC video, monetize via AdSense.", ["youtube"], []),
        ("content_affiliate_embed_v1", "affiliate", "Embed Amazon affiliate links in video descriptions.", ["amazon_associates"], []),
        ("bad_example", "lending", "Offer guaranteed returns payday loans to users.", [], []),
        ("eu_example", "content", "Publish AI-generated synthetic media targeting EU audience.", ["youtube"], ["EU"]),
    ]
    for sid, ch, desc, plats, regs in tests:
        r = check(sid, ch, desc, plats, regs)
        print(f"{sid}: {r.verdict}")
        for reason in r.reasons:
            print("  -", reason)
        for d in r.required_disclosures:
            print("  [disclosure]", d)
        print()
