import time

from z3ro.brain import LocalBrain
from z3ro.planner import Planner
from z3ro.tools.system import execute_tool
from z3ro.window import is_window_focused
from z3ro.vision import Vision


class Z3ROAgent:
    """Main Z3RO computer-control agent."""

    def __init__(self):
        self.brain = LocalBrain()
        self.planner = Planner()
        self.vision = Vision()

    def build_plan(self, user_input: str):

        t0 = time.perf_counter()
        response = self.brain.think(user_input)
        print(f"  [timing] brain.think: {time.perf_counter() - t0:.2f}s")

        if not response.success:
            return None, response.error

        try:

            plan = self.planner.parse(
                response.text
            )

            # Prevent hallucinations: If user only asked to open an app/website,
            # prune any unrequested dangling mouse click or keystroke.
            lowered = user_input.lower().strip()
            is_pure_open = any(lowered.startswith(p) for p in ("open ", "launch ", "start ", "run ")) and not any(kw in lowered for kw in ("click", "type", "press", "write", "search", "and "))
            if is_pure_open and plan and plan.actions:
                open_acts = [a for a in plan.actions if a.action == "open_app"]
                if open_acts:
                    plan.actions = [open_acts[0]]

            return plan, None

        except Exception as e:

            return None, str(e)

    def verify_action(
        self,
        action,
        result,
    ):

        if not result.success:
            return False

        if action.action == "open_app":
            return True

        if action.action == "find_window":
            return True

        if action.action == "focus_window":

            return is_window_focused(
                action.title
            )

        if action.action == "type_text":
            return True

        if action.action == "press_key":
            return True

        if action.action == "move_mouse":
            return True

        if action.action == "click_mouse":
            return True

        if action.action == "double_click_mouse":
            return True

        return False

    def execute_action(
        self,
        action,
    ):

        if action.action == "open_app":

            return execute_tool(
                "open_app",
                app=action.app,
            )

        if action.action == "find_window":

            return execute_tool(
                "find_window",
                title=action.title,
            )

        if action.action == "focus_window":

            return execute_tool(
                "focus_window",
                title=action.title,
            )

        if action.action == "type_text":

            return execute_tool(
                "type_text",
                text=action.text,
            )

        if action.action == "press_key":

            return execute_tool(
                "press_key",
                key=action.key,
            )

        if action.action == "move_mouse":

            return execute_tool(
                "move_mouse",
                x=action.x,
                y=action.y,
            )

        if action.action == "click_mouse":

            return execute_tool(
                "click_mouse",
                button=action.button or "left",
            )

        if action.action == "double_click_mouse":

            return execute_tool(
                "double_click_mouse",
            )

        return None

    def vision_check(
        self,
        user_input,
        action,
    ):

        prompt = f"""
You are Z3RO's visual verification system.

The user asked:
{user_input}

Z3RO just performed:
{action.action}

Determine whether the screen appears consistent
with the action having happened.

Return exactly one of:

VERIFIED: yes

VERIFIED: no

VERIFIED: unknown

No explanation.
"""

        t0 = time.perf_counter()
        result = self.vision.analyze(
            prompt=prompt
        )
        print(f"  [timing] vision.analyze: {time.perf_counter() - t0:.2f}s")

        if not result.success:

            print(
                "Z3RO Vision: unavailable - "
                f"{result.error}"
            )

            return "unknown"

        response = (
            result.response
            .lower()
            .strip()
        )

        if "verified: yes" in response:
            return "yes"

        if "verified: no" in response:
            return "no"

        return "unknown"

    def execute_plan(
        self,
        plan,
        user_input,
    ):

        results = []

        # Only run ONE vision check for the whole plan,
        # after the LAST qualifying action - not once per
        # action. This is the main fix: a 3-step plan used
        # to trigger 3 separate ~3 sec vision calls.
        vision_actions = {
            "open_app",
            "focus_window",
            "type_text",
            "press_key",
            "click_mouse",
            "double_click_mouse",
        }

        last_vision_eligible_action = None

        for action in plan.actions:
            if action.action in vision_actions:
                last_vision_eligible_action = action

        for action in plan.actions:

            print()
            print(
                f"Z3RO: Executing "
                f"{action.action}..."
            )

            t0 = time.perf_counter()
            result = self.execute_action(
                action
            )
            print(f"  [timing] execute_action: {time.perf_counter() - t0:.2f}s")

            if result is None:

                results.append(
                    f"Unsupported action: "
                    f"{action.action}"
                )

                break

            results.append(
                result.output
            )

            if not self.verify_action(
                action,
                result,
            ):

                results.append(
                    f"Verification failed: "
                    f"{action.action}"
                )

                break

            # Only fire vision check once, on the last
            # qualifying action in the whole plan.
            if action is last_vision_eligible_action:

                print(
                    "Z3RO: Checking screen "
                    "with vision..."
                )

                vision_result = (
                    self.vision_check(
                        user_input,
                        action,
                    )
                )

                print(
                    "Z3RO Vision: "
                    f"{vision_result}"
                )

        return results

    ACTION_KEYWORDS = {
        "open", "launch", "start", "run",
        "close", "quit", "exit", "kill",
        "focus", "switch", "bring up",
        "minimize", "maximize", "restore",
        "find", "show windows", "list windows",
        "type", "write", "enter",
        "press", "hotkey",
        "click", "double click", "move mouse",
    }

    def is_action_request(self, text: str) -> bool:
        """Determine if user input is an OS action or conversation."""
        lowered = text.lower().strip()
        words = set(lowered.split())
        if bool(words & self.ACTION_KEYWORDS):
            return True
        phrases = ("list windows", "find window", "double click", "switch to", "bring up")
        return any(phrase in lowered for phrase in phrases)

    def handle(
        self,
        user_input: str,
    ):
        t_total = time.perf_counter()

        # 1. If it's a conversational question / greeting, chat directly with Qwen!
        if not self.is_action_request(user_input):
            chat_res = self.brain.chat(user_input)
            if chat_res.success:
                print(f"  [timing] Qwen chat: {time.perf_counter() - t_total:.2f}s")
                return [chat_res.text]

        # 2. If it's an action request, plan and execute the computer tool steps
        plan, error = self.build_plan(user_input)

        if error or not plan or not plan.actions:
            # Fall back to conversational response if planning finds no actions
            chat_res = self.brain.chat(user_input)
            if chat_res.success:
                return [chat_res.text]
            return [f"Planning error: {error}"] if error else ["I'm not sure how to do that on your computer."]

        results = self.execute_plan(
            plan,
            user_input,
        )

        print(f"  [timing] TOTAL turn: {time.perf_counter() - t_total:.2f}s")
        return results

    def run(self, user_input: str):
        """Execute a user instruction (alias for handle)."""
        return self.handle(user_input)


if __name__ == "__main__":

    print("================================")
    print("          Z3RO AGENT")
    print("================================")
    print()
    print("Brain: Qwen 2.5 1.5B Instruct")
    print("Vision: Moondream")
    print("Windows grounding: ENABLED")
    print("Type 'exit' to quit.")
    print()

    agent = Z3ROAgent()

    while True:

        user_input = input(
            "You: "
        ).strip()

        if user_input.lower() == "exit":

            print(
                "Z3RO: Shutting down."
            )

            break

        if not user_input:
            continue

        results = agent.handle(
            user_input
        )

        print()

        for result in results:

            print(
                f"Z3RO: {result}"
            )

        print()
