"""Z3RO — Execution Experiences Store.

Implements Section 7:
- Records raw experiences, observations, tool outcomes, and reflections.
"""

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from z3ro.economy.ledger import ECONOMY_DB_PATH


class ExperienceStore:
    """Stores granular execution traces and tool outcomes."""

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
                    CREATE TABLE IF NOT EXISTS experiences (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        strategy_id TEXT,
                        experiment_id TEXT,
                        tool_name TEXT NOT NULL,
                        action_input TEXT,
                        action_output TEXT,
                        success INTEGER NOT NULL DEFAULT 1,
                        notes TEXT
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_experiences_timestamp
                    ON experiences (timestamp DESC)
                """)

    def record_experience(
        self,
        strategy_id: Optional[str],
        experiment_id: Optional[str],
        tool_name: str,
        action_input: str,
        action_output: str,
        success: bool = True,
        notes: str = "",
    ) -> int:
        timestamp = datetime.now().isoformat()
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO experiences (
                        timestamp, strategy_id, experiment_id, tool_name, action_input, action_output, success, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    strategy_id or "",
                    experiment_id or "",
                    tool_name,
                    action_input[:1000],
                    action_output[:2000],
                    1 if success else 0,
                    notes,
                ))
                return cursor.lastrowid or -1

    def get_recent_experiences(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM experiences
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]


# Global experiences instance
experience_store = ExperienceStore()
