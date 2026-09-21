"""Z3RO — Legal & Compliance Filter.

Implements Section 3, 9.2, & 13:
- Placed directly between Planner and Exploration.
- Validates all candidate strategies against jurisdiction rules.
- Strategies that fail are flagged REJECTED_COMPLIANCE and logged.
- Provides data feed for the UI Compliance-Filter Rejections panel.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from z3ro.compliance.jurisdiction_rules import (
    jurisdiction_evaluator,
    ComplianceViolation,
    RuleCategory,
)
from z3ro.economy.ledger import ECONOMY_DB_PATH


class LegalFilter:
    """Evaluates and audits candidate strategies before they reach the experiment stage."""

    def __init__(self, db_path: Path = ECONOMY_DB_PATH):
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
    ) -> Tuple[bool, List[ComplianceViolation]]:
        """Evaluate strategy. If non-compliant, log REJECTED_COMPLIANCE and block execution."""
        violations: List[ComplianceViolation] = []

        # 1. Text description & intent scan
        violations.extend(jurisdiction_evaluator.evaluate_strategy_text(description))
        violations.extend(jurisdiction_evaluator.evaluate_strategy_text(name))

        # 2. Target URLs / platforms check
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
                            v.category.value if hasattr(v.category, "value") else str(v.category),
                            v.rule_id,
                            v.reason,
                            description[:500],
                        ))
            return False, violations

        return True, []

    def get_recent_rejections(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch recent compliance rejections for the UI dashboard panel."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, timestamp, strategy_id, strategy_name, category, rule_id, reason, raw_text, status
                    FROM compliance_rejections
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]

    def get_rejection_stats(self) -> Dict[str, Any]:
        """Aggregate stats on rejections."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(id) as total_rejections FROM compliance_rejections")
                total = cursor.fetchone()["total_rejections"]

                cursor.execute("""
                    SELECT category, COUNT(id) as count 
                    FROM compliance_rejections 
                    GROUP BY category
                """)
                by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

                return {
                    "total_rejections": total,
                    "by_category": by_category,
                }


# Global legal filter instance
legal_filter = LegalFilter()
