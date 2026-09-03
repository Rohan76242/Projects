import json
from dataclasses import dataclass
from typing import Optional


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


@dataclass
class Plan:
    actions: list[PlannedAction]


class Planner:
    """Validate and normalize actions before execution."""

    ALLOWED_ACTIONS = {
        "open_app",
        "focus_window",
        "type_text",
        "press_key",
        "move_mouse",
        "click_mouse",
        "double_click_mouse",
    }

    def parse(self, raw_text: str) -> Plan:

        data = json.loads(raw_text)

        if not isinstance(data, dict):
            raise ValueError("Plan must be a JSON object.")

        raw_actions = data.get("actions")

        if not isinstance(raw_actions, list):
            raise ValueError("Plan must contain an actions list.")

        if len(raw_actions) == 0:
            raise ValueError("Plan contains no actions.")

        if len(raw_actions) > 8:
            raise ValueError("Plan contains too many actions.")

        actions = []

        for item in raw_actions:

            if not isinstance(item, dict):
                raise ValueError("Each action must be an object.")

            action = item.get("action")

            if action not in self.ALLOWED_ACTIONS:
                raise ValueError(
                    f"Unsupported action: {action}"
                )

            x = item.get("x")
            y = item.get("y")

            if x is not None and not isinstance(x, int):
                raise ValueError("Mouse x coordinate must be an integer.")

            if y is not None and not isinstance(y, int):
                raise ValueError("Mouse y coordinate must be an integer.")

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
                )
            )

        return Plan(actions=actions)


def print_plan(plan: Plan):

    print()
    print("PLAN:")

    for index, action in enumerate(plan.actions, start=1):

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
                "action": "focus_window",
                "title": "Notepad"
            },
            {
                "action": "type_text",
                "text": "Hello from Z3RO"
            },
            {
                "action": "move_mouse",
                "x": 500,
                "y": 300
            },
            {
                "action": "click_mouse",
                "button": "left"
            }
        ]
    }
    """

    plan = planner.parse(example)

    print("================================")
    print("       Z3RO PLANNER")
    print("================================")

    print_plan(plan)