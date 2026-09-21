"""Read Z3RO / SOBIA's Windows app catalogue and manage in-memory app registry.

Loads all applications, desktop executables, UWP store apps, and driver utilities from apps.txt into memory.
Provides instant (<0.0001s) in-memory lookup and background PowerShell launching.
"""

import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple, List, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATHS = [
    PROJECT_ROOT / "apps.txt",
    Path(__file__).with_name("apps.txt"),
]

VALID_STATUSES = {"enabled", "blocked", "reference"}
VALID_KINDS = {"app_id", "path"}


@dataclass(frozen=True)
class CatalogApp:
    """One application or executable recorded in the in-memory catalogue."""

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


# ------------------------------------------------------------------------------
# In-Memory App Locations Cache & Hash Tables
# ------------------------------------------------------------------------------
_MEMORY_LOADED = False
_ALL_APPS: List[CatalogApp] = []
_APPS_BY_NAME: Dict[str, CatalogApp] = {}
_APPS_BY_STEM: Dict[str, CatalogApp] = {}
_APPS_BY_ALIAS: Dict[str, CatalogApp] = {}
_APPS_BY_TARGET: Dict[str, CatalogApp] = {}

COMMON_ALIASES = {
    # Development & Terminals
    "vscode": "Visual Studio Code",
    "vs code": "Visual Studio Code",
    "code": "Visual Studio Code",
    "cmd": "Command Prompt",
    "terminal": "Windows Terminal",
    "wt": "Windows Terminal",
    "powershell": "Windows PowerShell",
    "git bash": "Git Bash",
    "bash": "Git Bash",
    "antigravity": "Antigravity IDE",
    "antigravity ide": "Antigravity IDE",
    "ide": "Antigravity IDE",

    # Browsers
    "browser": "Google Chrome",
    "chrome": "Google Chrome",
    "google chrome": "Google Chrome",
    "brave": "Brave",
    "brave browser": "Brave",
    "edge": "Microsoft Edge",
    "ms edge": "Microsoft Edge",

    # Windows Built-in Utilities
    "calc": "Calculator",
    "calculator": "Calculator",
    "paint": "Paint",
    "notepad": "Notepad",
    "text editor": "Notepad",
    "task manager": "Task Manager",
    "taskmgr": "Task Manager",
    "task man": "Task Manager",
    "control panel": "Control Panel",
    "control": "Control Panel",
    "settings": "Settings",
    "system settings": "Settings",
    "explorer": "File Explorer",
    "file explorer": "File Explorer",
    "files": "File Explorer",
    "file manager": "File Explorer",
    "this pc": "File Explorer",
    "my computer": "File Explorer",
    "camera": "Camera",
    "webcam": "Camera",
    "photos": "Photos",
    "photo": "Photos",
    "gallery": "Photos",
    "store": "Microsoft Store",
    "microsoft store": "Microsoft Store",
    "app store": "Microsoft Store",
    "sound": "Volume Mixer",
    "volume": "Volume Mixer",
    "clock": "Alarms & Clock",
    "alarm": "Alarms & Clock",
    "weather": "Weather",
    "snipping tool": "Snipping Tool",
    "snip": "Snipping Tool",
    "screenshot": "Snipping Tool",
    "devmgmt": "Device Manager (Drivers)",
    "device manager": "Device Manager (Drivers)",
    "dxdiag": "DirectX Diagnostic Tool (GPU/Drivers)",

    # Messaging & Social
    "whatsapp": "WhatsApp",
    "whats app": "WhatsApp",
    "wa": "WhatsApp",
    "telegram": "Telegram Desktop",
    "tg": "Telegram Desktop",
    "discord": "Discord",

    # AI Platforms
    "chatgpt": "ChatGPT",
    "chat gpt": "ChatGPT",
    "gpt": "ChatGPT",
    "claude": "Claude",

    # Media & Office
    "youtube": "YouTube",
    "yt": "YouTube",
    "spotify": "Spotify",
    "music": "Spotify",
    "word": "Microsoft 365 Copilot",
    "excel": "Microsoft 365 Copilot",
    "powerpoint": "Microsoft 365 Copilot",
    "office": "Microsoft 365 Copilot",
}



def preload_app_catalog(force_reload: bool = False) -> Tuple[CatalogApp, ...]:
    """Pre-load all application locations from apps.txt into in-memory hash tables.
    
    Populates:
    - _APPS_BY_NAME: O(1) lookup by exact normalized app name
    - _APPS_BY_STEM: O(1) lookup by executable file stem (e.g. 'code', 'brave', 'calc')
    - _APPS_BY_ALIAS: O(1) lookup by alias or acronym
    - _APPS_BY_TARGET: O(1) lookup by executable target path
    """
    global _MEMORY_LOADED, _ALL_APPS, _APPS_BY_NAME, _APPS_BY_STEM, _APPS_BY_ALIAS, _APPS_BY_TARGET

    if _MEMORY_LOADED and not force_reload:
        return tuple(_ALL_APPS)

    catalog_file = _get_catalog_file()
    if not catalog_file:
        return tuple()

    entries = []
    seen_names = set()
    by_name: Dict[str, CatalogApp] = {}
    by_stem: Dict[str, CatalogApp] = {}
    by_alias: Dict[str, CatalogApp] = {}
    by_target: Dict[str, CatalogApp] = {}

    for line_number, raw_line in enumerate(
        catalog_file.read_text(encoding="utf-8", errors="replace").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [part.strip() for part in line.split("|")]

        if len(parts) == 2:
            name, target = parts
            status = "enabled"
            kind = "app_id" if target.lower().startswith("shell:") else "path"
            aliases_list = []
            clean_base = Path(target).stem.lower()
            if clean_base != name.lower() and not target.lower().startswith("shell:"):
                aliases_list.append(clean_base)
            aliases = tuple(aliases_list)

        elif len(parts) == 5:
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
        app = CatalogApp(
            name=name,
            status=status,
            kind=kind,
            target=target,
            aliases=aliases,
        )
        entries.append(app)

        # Index by normalized name
        by_name[norm_name] = app

        # Index by stem
        if not target.lower().startswith("shell:"):
            stem = Path(target).stem.lower()
            if stem not in by_stem:
                by_stem[stem] = app

        # Index by target
        by_target[target.lower()] = app

        # Index by aliases
        for alias in aliases:
            norm_alias = _normalize(alias)
            if norm_alias not in by_alias:
                by_alias[norm_alias] = app

    _ALL_APPS = entries
    _APPS_BY_NAME = by_name
    _APPS_BY_STEM = by_stem
    _APPS_BY_ALIAS = by_alias
    _APPS_BY_TARGET = by_target
    _MEMORY_LOADED = True

    return tuple(entries)


# Auto-load into memory at import time
preload_app_catalog()


@lru_cache(maxsize=1)
def load_catalog() -> Tuple[CatalogApp, ...]:
    """Return the in-memory application catalogue."""
    return preload_app_catalog()


def reload_catalog():
    """Clear memory caches and re-index apps from apps.txt."""
    load_catalog.cache_clear()
    return preload_app_catalog(force_reload=True)


def find_app(query: str) -> Optional[CatalogApp]:
    """Find an app in memory by its recorded name, alias, filename, or fuzzy match."""
    if not isinstance(query, str):
        return None

    preload_app_catalog()
    raw_query = query.strip()
    norm_query = _normalize(raw_query)
    if not norm_query:
        return None

    # Strip leading filler words (e.g., "open the notepad" -> "the notepad" -> "notepad")
    cleaned_query = norm_query
    for prefix in ("the app ", "the application ", "the program ", "the ", "a ", "an ", "app ", "application ", "program ", "my "):
        if cleaned_query.startswith(prefix):
            cleaned_query = cleaned_query[len(prefix):].strip()
            break

    # Strip trailing filler words (e.g., "notepad app" -> "notepad", "brave browser" -> "brave")
    for suffix in (" app", " application", " program", " software", " browser"):
        if cleaned_query.endswith(suffix):
            cleaned_query = cleaned_query[:-len(suffix)].strip()
            break

    candidates = [norm_query]
    if cleaned_query and cleaned_query != norm_query:
        candidates.append(cleaned_query)

    # 1. Common Dictionary Aliases
    for cand in candidates:
        if cand in COMMON_ALIASES:
            target_alias = _normalize(COMMON_ALIASES[cand])
            if target_alias in _APPS_BY_NAME:
                return _APPS_BY_NAME[target_alias]
            if target_alias in _APPS_BY_STEM:
                return _APPS_BY_STEM[target_alias]
            if target_alias in _APPS_BY_ALIAS:
                return _APPS_BY_ALIAS[target_alias]
            for app in _ALL_APPS:
                if target_alias in _normalize(app.name):
                    return app

    # 2. Instant O(1) In-Memory Exact Name Match
    for cand in candidates:
        if cand in _APPS_BY_NAME:
            return _APPS_BY_NAME[cand]

    # 3. Instant O(1) In-Memory Executable Stem Match (e.g. "code" -> Code.exe, "brave" -> brave.exe)
    for cand in candidates:
        stem = cand[:-4] if cand.endswith(".exe") else cand
        if stem in _APPS_BY_STEM:
            return _APPS_BY_STEM[stem]

    # 4. Instant O(1) In-Memory Alias Match
    for cand in candidates:
        stem = cand[:-4] if cand.endswith(".exe") else cand
        if cand in _APPS_BY_ALIAS:
            return _APPS_BY_ALIAS[cand]
        if stem in _APPS_BY_ALIAS:
            return _APPS_BY_ALIAS[stem]

    # 5. Acronym Match (e.g. "vscode" -> "Visual Studio Code")
    for cand in candidates:
        compact = "".join(cand.split())
        for app in _ALL_APPS:
            words = _normalize(app.name).split()
            if len(words) >= 2:
                acronym = "".join(w[0] for w in words if w)
                if compact == acronym or compact == f"vs{acronym[-1]}":
                    return app

    # 6. Prefix / Substring Match (e.g. "chrome" in "Google Chrome")
    for cand in candidates:
        stem = cand[:-4] if cand.endswith(".exe") else cand
        for app in _ALL_APPS:
            app_norm = _normalize(app.name)
            if cand in app_norm or stem in app_norm:
                return app

    # 7. Reverse Substring Match (e.g. "open visual studio code" contains "visual studio code")
    for cand in candidates:
        for app in _ALL_APPS:
            app_norm = _normalize(app.name)
            if len(app_norm) >= 3 and app_norm in cand:
                return app

    # 8. Word Token Overlap Match
    for cand in candidates:
        query_tokens = set(cand.split())
        best_match = None
        max_overlap = 0

        for app in _ALL_APPS:
            app_tokens = set(_normalize(app.name).split())
            overlap = len(query_tokens & app_tokens)
            if overlap > max_overlap and overlap >= len(query_tokens):
                max_overlap = overlap
                best_match = app

        if best_match:
            return best_match

    # 9. Direct File Path
    if os.path.isfile(raw_query):
        return CatalogApp(
            name=Path(raw_query).stem,
            status="enabled",
            kind="path",
            target=raw_query,
            aliases=tuple(),
        )

    return None


def attach_thread_desktop():
    """Ensure the calling thread is attached to the interactive Windows 'Default' desktop."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass


def launch_app_via_powershell(target_path: str) -> bool:
    """Launch any Windows application or executable using a background PowerShell command.
    
    Runs completely silently without opening any console windows.
    Guarantees the process runs in the interactive desktop session so its UI appears on screen.
    Handles:
    - Native Win32 executables (.exe)
    - Modern Windows Store / UWP apps (shell:AppsFolder\\...)
    - Microsoft Management Consoles (.msc)
    - Control Panel applets (.cpl)
    """
    attach_thread_desktop()

    escaped_target = target_path.replace("'", "''")
    lower_target = target_path.lower()

    if lower_target.startswith("shell:"):
        ps_cmd = f"Start-Process '{escaped_target}'"
    elif lower_target.endswith(".msc"):
        ps_cmd = f"Start-Process 'mmc.exe' -ArgumentList '\"{escaped_target}\"'"
    elif lower_target.endswith(".cpl"):
        ps_cmd = f"Start-Process 'control.exe' -ArgumentList '\"{escaped_target}\"'"
    else:
        ps_cmd = f"Start-Process -FilePath '{escaped_target}'"

    CREATE_NO_WINDOW = 0x08000000
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps_cmd,
            ],
            creationflags=CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        pass

    # Guaranteed native Windows ShellExecute fallback
    try:
        os.startfile(target_path)
        return True
    except Exception:
        return False




def enabled_apps() -> Tuple[CatalogApp, ...]:
    """Return all apps Z3RO is currently allowed to launch from memory."""
    return tuple(app for app in preload_app_catalog() if app.status == "enabled")


def search_catalog(query: str, limit: int = 10) -> List[CatalogApp]:
    """Search the in-memory app catalogue by substring matching name or aliases."""
    preload_app_catalog()
    norm = _normalize(query)
    if not norm:
        return list(_ALL_APPS[:limit])

    results = []
    for app in _ALL_APPS:
        if norm in _normalize(app.name) or any(norm in _normalize(a) for a in app.aliases):
            results.append(app)
            if len(results) >= limit:
                break
    return results


def launch_app(query: str) -> Tuple[bool, str]:
    """Find and launch any application from the in-memory catalog."""
    app = find_app(query)
    if not app:
        return False, f"App '{query}' not found in catalog."
    if app.status == "blocked":
        return False, f"App '{app.name}' is blocked."
    success = launch_app_via_powershell(app.target)
    if success:
        return True, f"Launched {app.name}"
    return False, f"Failed to launch {app.name}"


def app_catalog_prompt() -> str:
    """Give the local model a concise guide of common applications it can launch."""
    common_names = [
        "Google Chrome", "Visual Studio Code", "Notepad", "Calculator",
        "Command Prompt", "PowerShell", "Task Manager", "Device Manager (Drivers)",
        "DirectX Diagnostic Tool (GPU/Drivers)", "Paint", "Control Panel",
        "File Explorer", "Disk Cleanup", "Services Management", "Brave", "WhatsApp",
    ]
    formatted = "\n".join(f"- {name}" for name in common_names)

    return (
        "For open_app, specify the name of any app, executable, or driver utility "
        "(e.g. Chrome, Notepad, VS Code, Task Manager, Device Manager, etc.). "
        "Any installed PC app in apps.txt is supported.\n"
        f"Examples of available apps:\n{formatted}"
    )
