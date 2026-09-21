"""Z3RO — Strategy Memory.

Implements Section 8:
- Persistent SQLite storage for strategy metadata and historical metrics.
- Fields: strategy_id, description, prerequisites, time, capital spent, verified revenue,
  net profit, failure reason, evidence, confidence, attempts, last attempt, compliance status.
- Empirical confidence updating based on measured outcomes rather than LLM predictions.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from z3ro.economy.ledger import ECONOMY_DB_PATH


class StrategyMemory:
    """Stores and updates learned strategy performance metrics."""

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
                    CREATE TABLE IF NOT EXISTS strategies (
                        strategy_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        description TEXT NOT NULL,
                        prerequisites TEXT DEFAULT '',
                        time_spent REAL NOT NULL DEFAULT 0.0,
                        capital_spent REAL NOT NULL DEFAULT 0.0,
                        verified_revenue REAL NOT NULL DEFAULT 0.0,
                        net_profit REAL NOT NULL DEFAULT 0.0,
                        failure_reason TEXT DEFAULT '',
                        evidence_ref TEXT DEFAULT '',
                        confidence REAL NOT NULL DEFAULT 0.50,
                        attempts_count INTEGER NOT NULL DEFAULT 0,
                        last_attempt_at TEXT,
                        compliance_status TEXT NOT NULL DEFAULT 'COMPLIANT',
                        status TEXT NOT NULL DEFAULT 'DISCOVERED'
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_strategies_confidence
                    ON strategies (confidence DESC)
                """)

    def save_or_update_strategy(
        self,
        strategy_id: str,
        name: str,
        description: str,
        prerequisites: str = "",
        compliance_status: str = "COMPLIANT",
        status: str = "DISCOVERED",
    ):
        """Register a new strategy or update its base description."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO strategies (
                        strategy_id, name, description, prerequisites, compliance_status, status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(strategy_id) DO UPDATE SET
                        name=excluded.name,
                        description=excluded.description,
                        prerequisites=excluded.prerequisites,
                        compliance_status=excluded.compliance_status,
                        status=excluded.status
                """, (strategy_id, name, description, prerequisites, compliance_status, status))

    def record_outcome(
        self,
        strategy_id: str,
        capital_spent: float,
        verified_revenue: float,
        time_spent_seconds: float,
        success: bool,
        failure_reason: str = "",
        evidence_ref: str = "",
    ) -> float:
        """Record an empirical experiment outcome and update confidence score (Section 8)."""
        net_profit = round(verified_revenue - capital_spent, 4)
        timestamp = datetime.now().isoformat()

        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM strategies WHERE strategy_id = ?", (strategy_id,))
                row = cursor.fetchone()

                if not row:
                    old_confidence = 0.50
                    old_attempts = 0
                    old_time = 0.0
                    old_capital = 0.0
                    old_rev = 0.0
                    old_net = 0.0
                else:
                    old_confidence = float(row["confidence"])
                    old_attempts = int(row["attempts_count"])
                    old_time = float(row["time_spent"])
                    old_capital = float(row["capital_spent"])
                    old_rev = float(row["verified_revenue"])
                    old_net = float(row["net_profit"])

                if success and net_profit > 0:
                    new_confidence = min(0.98, old_confidence + 0.12)
                    new_status = "ACTIVE"
                elif success and net_profit == 0:
                    new_confidence = min(0.90, old_confidence + 0.02)
                    new_status = "ACTIVE"
                else:
                    new_confidence = max(0.05, old_confidence - 0.18)
                    new_status = "ABANDONED" if new_confidence < 0.20 else "EVALUATED"

                new_attempts = old_attempts + 1
                new_time = old_time + (time_spent_seconds / 3600.0)
                new_capital = round(old_capital + capital_spent, 4)
                new_rev = round(old_rev + verified_revenue, 4)
                new_net = round(old_net + net_profit, 4)

                cursor.execute("""
                    INSERT INTO strategies (
                        strategy_id, name, description, time_spent, capital_spent, verified_revenue,
                        net_profit, failure_reason, evidence_ref, confidence, attempts_count,
                        last_attempt_at, compliance_status, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLIANT', ?)
                    ON CONFLICT(strategy_id) DO UPDATE SET
                        time_spent=excluded.time_spent,
                        capital_spent=excluded.capital_spent,
                        verified_revenue=excluded.verified_revenue,
                        net_profit=excluded.net_profit,
                        failure_reason=excluded.failure_reason,
                        evidence_ref=excluded.evidence_ref,
                        confidence=excluded.confidence,
                        attempts_count=excluded.attempts_count,
                        last_attempt_at=excluded.last_attempt_at,
                        status=excluded.status
                """, (
                    strategy_id,
                    strategy_id,
                    f"Strategy {strategy_id}",
                    new_time,
                    new_capital,
                    new_rev,
                    new_net,
                    failure_reason,
                    evidence_ref,
                    round(new_confidence, 4),
                    new_attempts,
                    timestamp,
                    new_status,
                ))
                return round(new_confidence, 4)

    def get_strategy(self, strategy_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM strategies WHERE strategy_id = ?", (strategy_id,))
                row = cursor.fetchone()
                return dict(row) if row else None

    def get_all_strategies(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch all strategies for UI Strategy Performance table."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM strategies
                    ORDER BY confidence DESC, net_profit DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]

    def get_top_performing_strategies(self, min_confidence: float = 0.50, limit: int = 5) -> List[Dict[str, Any]]:
        """Fetch top strategies for exploitation phase (Section 12)."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM strategies
                    WHERE compliance_status = 'COMPLIANT' 
                      AND confidence >= ? 
                      AND status != 'ABANDONED'
                    ORDER BY confidence DESC, net_profit DESC
                    LIMIT ?
                """, (min_confidence, limit))
                return [dict(row) for row in cursor.fetchall()]


# Global strategy memory instance
strategy_memory = StrategyMemory()
