import subprocess
from dataclasses import dataclass
from typing import Callable


@dataclass
class ToolResult:
    success: bool
    output: str


class Tool:
    """A controlled action that Z3RO is allowed to execute."""

    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
    ):
        self.name = name
        self.description = description
        self.function = function

    def execute(self, **kwargs) -> ToolResult:
        try:
            return self.function(**kwargs)
        except Exception as e:
            return ToolResult(
                success=False,
                output=str(e),
            )


def open_app(app: str) -> ToolResult:
    """
    Open a Windows application.

    Examples:
        chrome
        notepad
        calculator
    """

    allowed_apps = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
       "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    }

    app_key = app.lower().strip()

    if app_key not in allowed_apps:
        return ToolResult(
            success=False,
            output=f"Application '{app}' is not in the allowed app list.",
        )

    try:
        subprocess.Popen(
            [allowed_apps[app_key]],
            shell=False,
        )

        return ToolResult(
            success=True,
            output=f"Opened {app_key}.",
        )

    except FileNotFoundError:
        return ToolResult(
            success=False,
            output=f"{app_key} is not installed or could not be found.",
        )


TOOLS = {
    "open_app": Tool(
        name="open_app",
        description="Open an approved Windows application.",
        function=open_app,
    ),
}


def execute_tool(name: str, **kwargs) -> ToolResult:
    """Execute a registered Z3RO tool."""

    tool = TOOLS.get(name)

    if tool is None:
        return ToolResult(
            success=False,
            output=f"Unknown tool: {name}",
        )

    return tool.execute(**kwargs)


if __name__ == "__main__":
    print("================================")
    print("       Z3RO TOOL ENGINE")
    print("================================")
    print()

    result = execute_tool(
        "open_app",
        app="notepad",
    )

    print(result.output)