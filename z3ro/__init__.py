"""Z3RO / SOBIA — Package Initialization.

Ensures environment dependencies and site-packages from the project virtualenv
are always accessible regardless of which Python binary executes the module.
"""

import sys
from pathlib import Path

# Auto-add project virtualenv site-packages if not already in sys.path
_candidate_sites = [
    Path(r"s:\sobia\.venv\Lib\site-packages"),
    Path(r"C:\sobia\.venv\Lib\site-packages"),
    Path(__file__).resolve().parent.parent / ".venv" / "Lib" / "site-packages",
]

for _site in _candidate_sites:
    if _site.is_dir() and str(_site) not in sys.path:
        sys.path.insert(0, str(_site))
