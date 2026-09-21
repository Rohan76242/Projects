"""Z3RO — Sandboxed File and Content Operations Tool.

Implements Section 2 & 9.1:
- Capability: 'draft_content_code' (Allowed, No approval needed).
- Strictly prevents modification of self/wallet/survival/limits code.
"""

import os
from pathlib import Path
from typing import Dict, Any, List, Optional
from z3ro.economy.limits import limits_manager


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SANDBOX_DIR = PROJECT_ROOT / "data" / "sandbox"
SANDBOX_DIR.mkdir(parents=True, exist_ok=True)

FORBIDDEN_FILES = {
    "wallet.py",
    "ledger.py",
    "survival.py",
    "survival_watchdog.py",
    "limits.py",
    "limits_config.json",
    "z3ro_economy.db",
}


class FilesTool:
    """Provides sandboxed file creation, editing, and reading for agent tasks."""

    def __init__(self, root_dir: Path = SANDBOX_DIR):
        self.root_dir = root_dir
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _is_forbidden_target(self, filename: str) -> bool:
        base = os.path.basename(filename).lower()
        return base in FORBIDDEN_FILES or "economy" in filename.lower()

    def write_file(self, filename: str, content: str) -> Dict[str, Any]:
        """Write content or code artifact to sandboxed workspace."""
        allowed, reason = limits_manager.check_can_execute("draft_content_code")
        if not allowed:
            return {"success": False, "error": reason}

        if self._is_forbidden_target(filename):
            limits_manager.record_action_failed_or_rejected()
            return {
                "success": False,
                "error": "HARD BLOCK: Modifying wallet, ledger, survival, or limits code is permanently denied.",
            }

        target_path = self.root_dir / filename
        # Ensure path stays within sandbox
        try:
            target_path.resolve().relative_to(self.root_dir.resolve())
        except ValueError:
            return {"success": False, "error": "Access denied: Path escapes sandbox boundary."}

        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(content)
            limits_manager.record_action_executed()
            return {
                "success": True,
                "path": str(target_path),
                "bytes_written": len(content.encode("utf-8")),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def read_file(self, filename: str) -> Dict[str, Any]:
        """Read a file from the sandboxed workspace."""
        target_path = self.root_dir / filename
        if not target_path.is_file():
            return {"success": False, "error": f"File not found: {filename}"}

        try:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_files(self) -> List[str]:
        """List files currently in the sandbox."""
        if not self.root_dir.is_dir():
            return []
        return [str(p.relative_to(self.root_dir)) for p in self.root_dir.rglob("*") if p.is_file()]


# Global files tool singleton
files_tool = FilesTool()
