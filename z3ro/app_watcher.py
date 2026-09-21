"""Z3RO / SOBIA — Real-time Download & Application Watcher.

Monitors user Downloads, Desktop, Start Menu, and installation directories.
Automatically detects newly downloaded .exe files or installed apps,
appends them to apps.txt, and reloads Z3RO's app catalogue instantly.
Provides notification callbacks to the UI dynamic island overlay.
"""

import os
import sys
import time
import threading
from pathlib import Path
from typing import Set, Dict, Optional, Callable

from z3ro.app_indexer import (
    APPS_TXT_ROOT,
    APPS_TXT_PKG,
    clean_name,
    EXCLUDE_FILENAMES,
)
from z3ro.app_catalog import reload_catalog, load_catalog
from z3ro.logger import logger


class AppWatcher:
    """Monitors directories for newly downloaded or created .exe and .lnk files."""

    def __init__(
        self,
        check_interval: float = 2.0,
        on_new_app: Optional[Callable[[str, str], None]] = None,
    ):
        self.check_interval = check_interval
        self.on_new_app = on_new_app
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

        self.watch_dirs = [
            os.path.expandvars(r"%USERPROFILE%\Downloads"),
            os.path.expandvars(r"%USERPROFILE%\Desktop"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%LOCALAPPDATA%\Programs"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Chrome Apps"),
        ]

        self.known_files: Set[str] = set()
        self._init_known_files()

    def _init_known_files(self):
        """Populate initial baseline of existing files so only NEW files trigger alerts."""
        for d in self.watch_dirs:
            if not os.path.isdir(d):
                continue
            try:
                for root, _, files in os.walk(d):
                    for f in files:
                        lowered = f.lower()
                        if lowered.endswith(".exe") or lowered.endswith(".lnk"):
                            self.known_files.add(os.path.normpath(os.path.join(root, f)).lower())
            except Exception:
                pass

        # Also register all existing paths from apps.txt
        try:
            catalog = load_catalog()
            for app in catalog:
                self.known_files.add(os.path.normpath(app.target).lower())
        except Exception:
            pass

    def _append_to_apps_txt(self, app_name: str, app_path: str):
        """Append the newly found app to apps.txt in root and package."""
        entry_line = f"{app_name} | {app_path}\n"

        for target in [APPS_TXT_ROOT, APPS_TXT_PKG]:
            try:
                if target.is_file():
                    with open(target, "a", encoding="utf-8") as f:
                        f.write(entry_line)
            except Exception as e:
                logger.error(f"Failed to append to {target}: {e}")

        # Reload in-memory catalogue
        reload_catalog()
        logger.info(f"[App Watcher] Auto-indexed new application: '{app_name}' -> {app_path}")
        print(f"\n[App Watcher] Detected new app! Added to apps.txt: {app_name} ({app_path})\n")

        # Notify callback (e.g. Electron Dynamic Island overlay)
        if self.on_new_app:
            try:
                self.on_new_app(app_name, app_path)
            except Exception as e:
                logger.debug(f"Error in on_new_app callback: {e}")

    def _resolve_shortcut(self, lnk_path: str) -> Optional[str]:
        """Resolve a .lnk file to its destination, preserving web app shortcuts."""
        try:
            import win32com.client
            shell = win32com.client.Dispatch("WScript.Shell")
            shortcut = shell.CreateShortCut(lnk_path)
            target = shortcut.Targetpath
            if not target:
                return None

            lowered = target.lower()
            # If this is a Chrome/Edge PWA (like YouTube standalone app), keep the .lnk
            # because launching chrome_proxy.exe without flags fails, but launching the .lnk works!
            if lowered.endswith("chrome_proxy.exe") or lowered.endswith("msedge_proxy.exe"):
                return lnk_path

            if lowered.endswith(".exe") or lowered.endswith(".msc"):
                return target
        except Exception:
            pass
        return None

    def scan_once(self):
        """Inspect watch directories for any newly added files."""
        for d in self.watch_dirs:
            if not os.path.isdir(d):
                continue

            try:
                for root, _, files in os.walk(d):
                    for file in files:
                        lowered = file.lower()
                        if not (lowered.endswith(".exe") or lowered.endswith(".lnk")):
                            continue

                        full_path = os.path.normpath(os.path.join(root, file))
                        norm_key = full_path.lower()

                        if norm_key in self.known_files:
                            continue

                        # Mark as known to avoid duplicate indexing
                        self.known_files.add(norm_key)

                        # Handle .lnk vs .exe
                        target_exe = full_path
                        if lowered.endswith(".lnk"):
                            resolved = self._resolve_shortcut(full_path)
                            if not resolved:
                                continue
                            target_exe = resolved

                        # Exclude uninstaller or temporary installation files
                        fname = os.path.basename(target_exe).lower()
                        if fname in EXCLUDE_FILENAMES:
                            continue

                        # Generate clean friendly name
                        display_name = clean_name(file)
                        self._append_to_apps_txt(display_name, target_exe)

            except Exception as e:
                logger.debug(f"Watcher scan error in {d}: {e}")

    def _run_loop(self):
        """Background thread execution loop."""
        logger.info("[App Watcher] Real-time download & application watcher started.")
        while not self._stop_event.is_set():
            self.scan_once()
            self._stop_event.wait(self.check_interval)

    def start(self):
        """Start watcher in a background daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="AppWatcherThread")
        self._thread.start()

    def stop(self):
        """Stop background watcher."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None


# Global singleton instance
_watcher_instance: Optional[AppWatcher] = None


def start_app_watcher(on_new_app: Optional[Callable[[str, str], None]] = None) -> AppWatcher:
    """Start the global app watcher service."""
    global _watcher_instance
    if _watcher_instance is None:
        _watcher_instance = AppWatcher(on_new_app=on_new_app)
        _watcher_instance.start()
    elif on_new_app and _watcher_instance.on_new_app is None:
        _watcher_instance.on_new_app = on_new_app
    return _watcher_instance


def set_app_watcher_callback(callback: Callable[[str, str], None]):
    """Register or update callback for detected apps."""
    global _watcher_instance
    if _watcher_instance:
        _watcher_instance.on_new_app = callback


if __name__ == "__main__":
    print("Starting Z3RO App Watcher standalone. Press Ctrl+C to stop.")
    watcher = start_app_watcher()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping watcher...")
        watcher.stop()
