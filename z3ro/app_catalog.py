"""Read Z3RO / SOBIA's Windows app catalogue.

Loads all applications, system tools, and driver utilities from apps.txt.
Provides fuzzy matching so Z3RO can open any application or executable on the PC.
"""

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATHS = [
    PROJECT_ROOT / "apps.txt",
    Path(__file__).with_name("apps.txt"),
]

VALID_STATUSES = {"enabled", "blocked", "reference"}
VALID_KINDS = {"app_id", "path"}


@dataclass(frozen=True)
class CatalogApp:
    """One application or executable recorded in the catalogue."""

    name: str
    status: str
    kind: str
    target: str
    aliases: Tuple[str, ...]


def _normalize(value: str) -> str:
    """Return a case-insensitive, whitespace-stable app name."""
    return " ".join(value.casefold().split())


def _get_catalog_file() -> Optional[Path]:
    """Find the active apps.txt file."""
    for p in CATALOG_PATHS:
        if p.is_file():
            return p
    return None


@lru_cache(maxsize=1)
def load_catalog() -> Tuple[CatalogApp, ...]:
    """Load and validate the application catalogue from apps.txt."""
    catalog_file = _get_catalog_file()
    if not catalog_file:
        return tuple()

    entries = []
    seen_names = set()

    for line_number, raw_line in enumerate(
        catalog_file.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        parts = [part.strip() for part in line.split("|")]

        if len(parts) == 2:
            # New standard format: App Name | Executable Path
            name, target = parts
            status = "enabled"
            kind = "path"
            # Auto-generate aliases from name
            aliases_list = []
            clean_base = Path(target).stem.lower()
            if clean_base != name.lower():
                aliases_list.append(clean_base)
            aliases = tuple(aliases_list)

        elif len(parts) == 5:
            # Legacy 5-column format: status | name | kind | target | aliases
            status, name, kind, target, aliases_text = parts
            if status not in VALID_STATUSES:
                status = "enabled"
            if kind not in VALID_KINDS:
                kind = "path"
            aliases = tuple(
                alias.strip()
                for alias in aliases_text.split(",")
                if alias.strip()
            )
        else:
            continue

        if not name or not target:
            continue

        norm_name = _normalize(name)
        if norm_name in seen_names:
            continue

        seen_names.add(norm_name)
        entries.append(
            CatalogApp(
                name=name,
                status=status,
                kind=kind,
                target=target,
                aliases=aliases,
            )
        )

    return tuple(entries)


def reload_catalog():
    """Clear lru_cache and force reload of apps.txt."""
    load_catalog.cache_clear()
    return load_catalog()


COMMON_ALIASES = {
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "cmd": "Command Prompt",
    "terminal": "Windows Terminal",
    "browser": "Google Chrome",
    "chrome": "Google Chrome",
    "edge": "Microsoft Edge",
    "taskmgr": "Task Manager",
    "devmgmt": "Device Manager",
    "dxdiag": "DirectX Diagnostic Tool",
    "calc": "Calculator",
    "paint": "Paint",
    "notepad": "Notepad",
}


def find_app(query: str) -> Optional[CatalogApp]:
    """Find an app by its recorded name, alias, filename, or fuzzy match."""
    if not isinstance(query, str):
        return None

    catalog = load_catalog()
    if not catalog:
        return None

    raw_query = query.strip()
    norm_query = _normalize(raw_query)
    if not norm_query:
        return None

    # Check common dictionary aliases
    if norm_query in COMMON_ALIASES:
        target_name = _normalize(COMMON_ALIASES[norm_query])
        for app in catalog:
            if target_name == _normalize(app.name):
                return app
        for app in catalog:
            if target_name in _normalize(app.name):
                return app


    # Strip .exe if provided in query (e.g. "chrome.exe" -> "chrome")
    query_stem = norm_query[:-4] if norm_query.endswith(".exe") else norm_query

    # 1. Exact Name Match
    for app in catalog:
        if norm_query == _normalize(app.name):
            return app

    # 2. Exact Alias Match
    for app in catalog:
        for alias in app.aliases:
            if norm_query == _normalize(alias) or query_stem == _normalize(alias):
                return app

    # 3. Acronym Match (e.g. "vscode" -> "Visual Studio Code")
    compact_query = "".join(norm_query.split())
    for app in catalog:
        words = _normalize(app.name).split()
        if len(words) >= 2:
            acronym = "".join(w[0] for w in words if w)
            if compact_query == acronym or compact_query == f"vs{acronym[-1]}":
                return app

    # 4. Target Executable Filename Match (e.g. "code" -> "Code.exe", "chrome" -> "chrome.exe")
    for app in catalog:
        target_stem = Path(app.target).stem.lower()
        if query_stem == target_stem:
            return app

    # 5. Prefix / Substring Match (e.g. "chrome" in "Google Chrome", "device manager" in "Device Manager (Drivers)")
    for app in catalog:
        app_norm = _normalize(app.name)
        if norm_query in app_norm or query_stem in app_norm:
            return app

    # 6. Reverse Substring Match (e.g. query is "open visual studio code" -> "Visual Studio Code")
    for app in catalog:
        app_norm = _normalize(app.name)
        if len(app_norm) >= 4 and app_norm in norm_query:
            return app

    # 7. Word Token Overlap Match
    query_tokens = set(norm_query.split())
    best_match = None
    max_overlap = 0

    for app in catalog:
        app_tokens = set(_normalize(app.name).split())
        overlap = len(query_tokens & app_tokens)
        if overlap > max_overlap and overlap >= len(query_tokens):
            max_overlap = overlap
            best_match = app

    if best_match:
        return best_match

    # 8. Check if query is an absolute existing file path
    if os.path.isfile(raw_query):
        return CatalogApp(
            name=Path(raw_query).stem,
            status="enabled",
            kind="path",
            target=raw_query,
            aliases=tuple(),
        )

    return None



def enabled_apps() -> Tuple[CatalogApp, ...]:
    """Return the apps Z3RO is currently allowed to launch."""
    return tuple(
        app for app in load_catalog()
        if app.status == "enabled"
    )


def app_catalog_prompt() -> str:
    """Give the local model a concise guide of common applications it can launch."""
    common_names = [
        "Google Chrome", "Visual Studio Code", "Notepad", "Calculator",
        "Command Prompt", "PowerShell", "Task Manager", "Device Manager (Drivers)",
        "DirectX Diagnostic Tool (GPU/Drivers)", "Paint", "Control Panel",
        "File Explorer", "Disk Cleanup", "Services Management",
    ]
    formatted = "\n".join(f"- {name}" for name in common_names)

    return (
        "For open_app, specify the name of any app, executable, or driver utility "
        "(e.g. Chrome, Notepad, VS Code, Task Manager, Device Manager, etc.). "
        "Any installed PC app in apps.txt is supported.\n"
        f"Examples of available apps:\n{formatted}"
    )
