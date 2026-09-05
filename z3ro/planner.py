import json
import re
from dataclasses import dataclass
from typing import Optional


def extract_json(raw_text: str) -> dict:
    """Extract the first valid JSON object from model output.

    Handles common issues with small-model output:
    - Markdown code fences (```json ... ```)
    - Thinking preamble before the JSON
    - Trailing explanation after the JSON
    """

    text = raw_text.strip()

    # Strip markdown fences.
    text = re.sub(
        r"```(?:json)?\s*",
        "",
        text,
    )

    # Find the first '{' and the last matching '}'.
    start = text.find("{")

    if start == -1:
        raise ValueError(
            "No JSON object found in model output."
        )

    # Walk forward from start, counting braces.
    depth = 0
    end = start

    for i in range(start, len(text)):

        if text[i] == "{":
            depth += 1

        elif text[i] == "}":
            depth -= 1

            if depth == 0:
                end = i
                break

    if depth != 0:
        raise ValueError(
            "Unbalanced braces in model output."
        )

    return json.loads(text[start : end + 1])


@dataclass
class PlannedAction:
    action: str
    app: Optional[str] = None
    title: Optional[str] = None
    text: Optional[str] = None
    key: Optional[str] = None
    x: Optional[int] = None
    y: Optional[int] = None
    button: Optional[str] = None
    recipient: Optional[str] = None
    message: Optional[str] = None
    song: Optional[str] = None
    steps: Optional[int] = None


@dataclass
class Plan:
    actions: list[PlannedAction]


class Planner:
    """Validate and normalize Z3RO actions."""

    ALLOWED_ACTIONS = {
        "open_app",
        "find_window",
        "focus_window",
        "type_text",
        "press_key",
        "move_mouse",
        "click_mouse",
        "double_click_mouse",
        "send_whatsapp",
        "open_whatsapp",
        "send_telegram",
        "open_telegram",
        "play_song",
        "pause_song",
        "resume_song",
        "stop_song",
        "next_song",
        "previous_song",
        "change_video",
        "volume_up",
        "volume_down",
        "mute_volume",
    }

    def parse(self, raw_text: str) -> Plan:

        data = extract_json(raw_text)

        if not isinstance(data, dict):
            raise ValueError(
                "Plan must be a JSON object."
            )

        raw_actions = data.get("actions")

        if not isinstance(raw_actions, list):
            raise ValueError(
                "Plan must contain an actions list."
            )

        if len(raw_actions) == 0:
            raise ValueError(
                "Plan contains no actions."
            )

        if len(raw_actions) > 8:
            raise ValueError(
                "Plan contains too many actions."
            )

        actions = []

        for item in raw_actions:

            if not isinstance(item, dict):
                raise ValueError(
                    "Each action must be an object."
                )

            action = item.get("action")

            if action not in self.ALLOWED_ACTIONS:
                raise ValueError(
                    f"Unsupported action: {action}"
                )

            x = item.get("x")
            y = item.get("y")

            if x is not None and not isinstance(x, int):
                raise ValueError(
                    "Mouse x coordinate must be an integer."
                )

            if y is not None and not isinstance(y, int):
                raise ValueError(
                    "Mouse y coordinate must be an integer."
                )

            actions.append(
                PlannedAction(
                    action=action,
                    app=item.get("app"),
                    title=item.get("title"),
                    text=item.get("text"),
                    key=item.get("key"),
                    x=x,
                    y=y,
                    button=item.get("button"),
                    recipient=item.get("recipient") or item.get("to") or item.get("contact"),
                    message=item.get("message") or item.get("body") or item.get("text"),
                    song=item.get("song") or item.get("query") or item.get("title"),
                    steps=item.get("steps"),
                )
            )

        return Plan(
            actions=actions
        )


def print_plan(plan: Plan):

    print()
    print("PLAN:")

    for index, action in enumerate(
        plan.actions,
        start=1,
    ):

        print(
            f"{index}. "
            f"{action.action} "
            f"app={action.app!r} "
            f"title={action.title!r} "
            f"text={action.text!r} "
            f"key={action.key!r} "
            f"x={action.x!r} "
            f"y={action.y!r} "
            f"button={action.button!r}"
        )


if __name__ == "__main__":

    planner = Planner()

    example = """
    {
        "actions": [
            {
                "action": "open_app",
                "app": "notepad"
            },
            {
                "action": "find_window",
                "title": "Notepad"
            },
            {
                "action": "focus_window",
                "title": "Notepad"
            },
            {
                "action": "type_text",
                "text": "Hello from Z3RO"
            }
        ]
    }
    """

    plan = planner.parse(
        example
    )

    print("================================")
    print("       Z3RO PLANNER")
    print("================================")

    print_plan(plan)