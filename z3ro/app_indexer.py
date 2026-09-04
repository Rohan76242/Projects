"""Z3RO / SOBIA — Windows Application, Driver & Executable Indexer.

Performs an exhaustive system scan to find all installed applications,
desktop programs, driver utilities, and executable files, generating apps.txt.
"""

import os
import sys
import time
import winreg
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# Root and data paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPS_TXT_ROOT = PROJECT_ROOT / "apps.txt"
APPS_TXT_PKG = PROJECT_ROOT / "z3ro" / "apps.txt"

# Common noise files to exclude from primary app indexing
EXCLUDE_FILENAMES = {
    "unins000.exe",
    "uninstall.exe",
    "uninstaller.exe",
    "crashpad_handler.exe",
    "notification_helper.exe",
    "update.exe",
    "installer.exe",
    "setup.exe",
    "vc_redist.x64.exe",
    "vc_redist.x86.exe",
    "vcredist_x64.exe",
    "vcredist_x86.exe",
    "elevate.exe",
    "helper.exe",
}

# Windows System and Driver Utilities
SYSTEM_AND_DRIVER_TOOLS = [
    ("Device Manager (Drivers)", r"C:\Windows\System32\devmgmt.msc"),
    ("DirectX Diagnostic Tool (GPU/Drivers)", r"C:\Windows\System32\dxdiag.exe"),
    ("Task Manager", r"C:\Windows\System32\taskmgr.exe"),
    ("System Information", r"C:\Windows\System32\msinfo32.exe"),
    ("Services Management", r"C:\Windows\System32\services.msc"),
    ("Registry Editor", r"C:\Windows\regedit.exe"),
    ("Control Panel", r"C:\Windows\System32\control.exe"),
    ("Disk Cleanup", r"C:\Windows\System32\cleanmgr.exe"),
    ("Command Prompt", r"C:\Windows\System32\cmd.exe"),
    ("PowerShell", r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"),
    ("Notepad", r"C:\Windows\System32\notepad.exe"),
    ("Calculator", r"C:\Windows\System32\calc.exe"),
    ("Paint", r"C:\Windows\System32\mspaint.exe"),
    ("Sound Device Manager", r"C:\Windows\System32\mmsys.cpl"),
    ("Volume Mixer", r"C:\Windows\System32\sndvol.exe"),
    ("Performance Monitor", r"C:\Windows\System32\perfmon.exe"),
    ("Resource Monitor", r"C:\Windows\System32\resmon.exe"),
    ("Network Connections", r"C:\Windows\System32\ncpa.cpl"),
    ("Hardware & Driver Wizard", r"C:\Windows\System32\hdwwiz.cpl"),
    ("Computer Management", r"C:\Windows\System32\compmgmt.msc"),
    ("Windows Terminal", r"C:\Users\%USERNAME%\AppData\Local\Microsoft\WindowsApps\wt.exe"),
]


def clean_name(name: str) -> str:
    """Normalize and format application display name."""
    # Remove file extensions if present
    for ext in (".exe", ".lnk", ".msc", ".cpl"):
        if name.lower().endswith(ext):
            name = name[:-len(ext)]
    # Replace underscores/dashes with space if needed
    name = name.replace("_", " ").strip()
    return name


class AppIndexer:
    """Discovers installed applications and driver utilities across Windows."""

    def __init__(self):
        self.apps: Dict[str, str] = {}  # {Normalized Name: Full Executable Path}
        self.seen_paths: Set[str] = set()
        self._init_com()

    def _init_com(self):
        """Initialize WScript.Shell COM object for fast .lnk resolution."""
        self.shell = None
        try:
            import win32com.client
            self.shell = win32com.client.Dispatch("WScript.Shell")
        except Exception as e:
            print(f"Warning: win32com not available ({e}). Lnk resolution may be slower.")

    def add_entry(self, name: str, path: str):
        """Record an application entry if valid and existing."""
        if not path or not isinstance(path, str):
            return

        # Expand environment variables
        expanded_path = os.path.expandvars(path).strip().strip('"').strip("'")
        if not expanded_path:
            return

        # Strip arguments if included (e.g. "chrome.exe --profile-directory=Default")
        if ".exe" in expanded_path.lower():
            idx = expanded_path.lower().find(".exe") + 4
            possible_path = expanded_path[:idx]
            if os.path.isfile(possible_path):
                expanded_path = possible_path

        # Validate file existence
        if not os.path.exists(expanded_path):
            return

        # Check exclusion list
        filename = os.path.basename(expanded_path).lower()
        if filename in EXCLUDE_FILENAMES:
            return

        # Normalize key and path
        norm_path = os.path.normpath(expanded_path)
        if norm_path.lower() in self.seen_paths:
            return

        formatted_name = clean_name(name)
        if not formatted_name:
            formatted_name = clean_name(filename)

        self.apps[formatted_name] = norm_path
        self.seen_paths.add(norm_path.lower())

    def scan_start_menu(self):
        """Scan Start Menu directories for .lnk shortcuts."""
        directories = [
            os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
            os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
        ]

        for directory in directories:
            if not os.path.isdir(directory):
                continue

            for root, _, files in os.walk(directory):
                for file in files:
                    if not file.lower().endswith(".lnk"):
                        continue

                    shortcut_path = os.path.join(root, file)
                    target = self._resolve_shortcut(shortcut_path)
                    if target and (target.lower().endswith(".exe") or target.lower().endswith(".msc")):
                        app_name = file[:-4]  # Strip .lnk
                        self.add_entry(app_name, target)

    def _resolve_shortcut(self, lnk_path: str) -> Optional[str]:
        """Resolve a Windows .lnk shortcut to its target path."""
        if self.shell:
            try:
                shortcut = self.shell.CreateShortCut(lnk_path)
                return shortcut.Targetpath
            except Exception:
                pass
        return None

    def scan_registry_app_paths(self):
        """Scan Windows Registry App Paths."""
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        ]

        for hkey, subkey_path in roots:
            try:
                with winreg.OpenKey(hkey, subkey_path) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as app_key:
                                try:
                                    target_path, _ = winreg.QueryValueEx(app_key, "")
                                    if target_path and target_path.lower().endswith(".exe"):
                                        app_name = subkey_name[:-4] if subkey_name.lower().endswith(".exe") else subkey_name
                                        self.add_entry(app_name, target_path)
                                except WindowsError:
                                    pass
                        except WindowsError:
                            continue
            except WindowsError:
                continue

    def scan_registry_uninstall(self):
        """Scan Windows Registry Uninstall keys for installed software suites."""
        roots = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hkey, subkey_path in roots:
            try:
                with winreg.OpenKey(hkey, subkey_path) as key:
                    count = winreg.QueryInfoKey(key)[0]
                    for i in range(count):
                        try:
                            subkey_name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, subkey_name) as app_key:
                                try:
                                    display_name, _ = winreg.QueryValueEx(app_key, "DisplayName")
                                except WindowsError:
                                    continue

                                # Try DisplayIcon
                                try:
                                    icon_path, _ = winreg.QueryValueEx(app_key, "DisplayIcon")
                                    if icon_path and ".exe" in icon_path.lower():
                                        self.add_entry(display_name, icon_path)
                                        continue
                                except WindowsError:
                                    pass

                                # Try InstallLocation
                                try:
                                    install_loc, _ = winreg.QueryValueEx(app_key, "InstallLocation")
                                    if install_loc and os.path.isdir(install_loc):
                                        self._scan_dir_shallow(display_name, install_loc, max_depth=2)
                                except WindowsError:
                                    pass
                        except WindowsError:
                            continue
            except WindowsError:
                continue

    def scan_common_directories(self):
        """Scan standard application installation folders."""
        dirs_to_scan = [
            (os.path.expandvars(r"%LOCALAPPDATA%\Programs"), 3),
            (os.path.expandvars(r"%PROGRAMFILES%"), 2),
            (os.path.expandvars(r"%PROGRAMFILES(X86)%"), 2),
            (os.path.expandvars(r"%USERPROFILE%\Desktop"), 1),
            (os.path.expandvars(r"%USERPROFILE%\Downloads"), 1),
        ]

        for directory, max_depth in dirs_to_scan:
            if not os.path.isdir(directory):
                continue

            base_depth = directory.rstrip(os.path.sep).count(os.path.sep)

            for root, dirs, files in os.walk(directory):
                cur_depth = root.count(os.path.sep) - base_depth
                if cur_depth > max_depth:
                    dirs.clear()
                    continue

                for file in files:
                    if file.lower().endswith(".exe"):
                        full_path = os.path.join(root, file)
                        # Name derives from parent folder or clean file name
                        folder_name = os.path.basename(root)
                        app_name = file[:-4]
                        if len(app_name) < 4 or app_name.lower() in ("app", "main", "launch", "run", "client"):
                            app_name = f"{folder_name} ({file[:-4]})"
                        self.add_entry(app_name, full_path)

    def scan_driver_and_system_tools(self):
        """Register critical driver control suites and Windows system utilities."""
        for name, path in SYSTEM_AND_DRIVER_TOOLS:
            self.add_entry(name, path)

        # Check vendor-specific driver suites in Program Files
        driver_vendors = [
            (r"C:\Program Files\NVIDIA Corporation", 3),
            (r"C:\Program Files (x86)\NVIDIA Corporation", 3),
            (r"C:\Program Files\Realtek", 3),
            (r"C:\Program Files\Intel", 3),
            (r"C:\Program Files\AMD", 3),
        ]

        for path, depth in driver_vendors:
            if os.path.isdir(path):
                self._scan_dir_shallow("Driver Tool", path, max_depth=depth)

    def _scan_dir_shallow(self, fallback_name: str, directory: str, max_depth: int = 2):
        """Helper to scan directory up to a shallow depth for executables."""
        base_depth = directory.rstrip(os.path.sep).count(os.path.sep)
        for root, dirs, files in os.walk(directory):
            cur_depth = root.count(os.path.sep) - base_depth
            if cur_depth > max_depth:
                dirs.clear()
                continue

            for file in files:
                if file.lower().endswith(".exe"):
                    full_path = os.path.join(root, file)
                    app_name = file[:-4]
                    if len(app_name) < 4:
                        app_name = f"{fallback_name} - {file[:-4]}"
                    self.add_entry(app_name, full_path)

    def run_full_scan(self) -> Dict[str, str]:
        """Perform full multi-source indexing and return sorted dictionary."""
        print("Scanning Start Menu shortcuts...")
        self.scan_start_menu()

        print("Scanning Windows Registry App Paths...")
        self.scan_registry_app_paths()

        print("Scanning Installed Programs (Uninstall Registry)...")
        self.scan_registry_uninstall()

        print("Scanning System and Driver Control Tools...")
        self.scan_driver_and_system_tools()

        print("Scanning Common Program & Download Directories...")
        self.scan_common_directories()

        print(f"Scan complete. Total unique applications/tools found: {len(self.apps)}")
        return self.apps

    def save_to_file(self, target_paths: Optional[List[Path]] = None):
        """Write formatted apps.txt file to designated target paths."""
        if not target_paths:
            target_paths = [APPS_TXT_ROOT, APPS_TXT_PKG]

        # Sort alphabetically by application name
        sorted_items = sorted(self.apps.items(), key=lambda x: x[0].lower())

        lines = [
            "# =============================================================================",
            "#                 Z3RO / SOBIA PC APPLICATIONS & DRIVERS REGISTRY",
            "# =============================================================================",
            f"# Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"# Total Indexed Applications & Tools: {len(sorted_items)}",
            "# Format: Application Name | Executable Path",
            "# =============================================================================",
            "",
        ]

        for name, path in sorted_items:
            lines.append(f"{name} | {path}")

        content = "\n".join(lines) + "\n"

        for p in target_paths:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            print(f"Saved {len(sorted_items)} apps to: {p}")


def index_and_generate_apps_txt():
    """Main execution function to index apps and write apps.txt."""
    indexer = AppIndexer()
    indexer.run_full_scan()
    indexer.save_to_file()
    return indexer.apps


if __name__ == "__main__":
    index_and_generate_apps_txt()
