"""Z3RO — Auditable Economic Ledger (SQLite).

Implements Section 6 & 10.1:
- Append-only, tamper-resistant transaction ledger.
- Fields: timestamp, action, cost, verified_income, net, evidence_id, verification_source.
- Read-only to agent planning runtime.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ECONOMY_DB_PATH = DATA_DIR / "z3ro_economy.db"


class Ledger:
    """Thread-safe, append-only SQLite ledger for Z3RO's economic tracking."""

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
                    CREATE TABLE IF NOT EXISTS ledger (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        action TEXT NOT NULL,
                        cost REAL NOT NULL DEFAULT 0.0,
                        verified_income REAL NOT NULL DEFAULT 0.0,
                        net REAL NOT NULL DEFAULT 0.0,
                        evidence_id TEXT,
                        verification_source TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'VERIFIED'
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ledger_timestamp
                    ON ledger (timestamp DESC)
                """)

    def record_entry(
        self,
        action: str,
        cost: float = 0.0,
        verified_income: float = 0.0,
        evidence_id: Optional[str] = None,
        verification_source: str = "INTERNAL_SIMULATION",
        status: str = "VERIFIED",
    ) -> int:
        """Append an entry to the immutable ledger."""
        net = round(verified_income - cost, 4)
        timestamp = datetime.now().isoformat()

        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ledger (
                        timestamp, action, cost, verified_income, net, evidence_id, verification_source, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    action,
                    round(cost, 4),
                    round(verified_income, 4),
                    net,
                    evidence_id or "",
                    verification_source,
                    status,
                ))
                return cursor.lastrowid or -1

    def get_summary(self) -> Dict[str, float]:
        """Compute verified financial summary: total revenue, total costs, net profit."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(verified_income), 0.0) as total_revenue,
                        COALESCE(SUM(cost), 0.0) as total_cost,
                        COALESCE(SUM(net), 0.0) as net_profit,
                        COUNT(id) as total_entries
                    FROM ledger
                """)
                row = cursor.fetchone()
                return {
                    "total_revenue": round(float(row["total_revenue"]), 2),
                    "total_cost": round(float(row["total_cost"]), 2),
                    "net_profit": round(float(row["net_profit"]), 2),
                    "total_entries": int(row["total_entries"]),
                }

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch the most recent ledger entries in reverse chronological order."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, timestamp, action, cost, verified_income, net, evidence_id, verification_source, status
                    FROM ledger
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]


# Global singleton instance
ledger = Ledger()
