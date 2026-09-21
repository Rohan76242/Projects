"""Z3RO — Dashboard Package.

Provides:
- get_full_dashboard_state (Aggregated real-time telemetry)
- run_dashboard_server (Standalone HTTP & REST API server)
"""

from z3ro.dashboard.app import get_full_dashboard_state, run_dashboard_server

__all__ = [
    "get_full_dashboard_state",
    "run_dashboard_server",
]
