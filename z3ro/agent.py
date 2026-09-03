from z3ro.brain import LocalBrain
from z3ro.planner import Planner
from z3ro.tools.system import execute_tool


class Z3ROAgent:

    def __init__(self):
        self.brain = LocalBrain()
        self.planner = Planner()

    def build_plan(self, user_input: str):

        response = self.brain.think(user_input)

        if not response.success:
            return None, response.error

        try:
            plan = self.planner.parse(response.text)
            return plan, None

        except Exception as e:
            return None, str(e)

    def execute_plan(self, plan):

        results = []

        for action in plan.actions:

            if action.action == "open_app":

                result = execute_tool(
                    "open_app",
                    app=action.app,
                )

            elif action.action == "focus_window":

                result = execute_tool(
                    "focus_window",
                    title=action.title,
                )

            elif action.action == "type_text":

                result = execute_tool(
                    "type_text",
                    text=action.text,
                )

            elif action.action == "press_key":

                result = execute_tool(
                    "press_key",
                    key=action.key,
                )

            elif action.action == "move_mouse":

                result = execute_tool(
                    "move_mouse",
                    x=action.x,
                    y=action.y,
                )

            elif action.action == "click_mouse":

                result = execute_tool(
                    "click_mouse",
                    button=action.button or "left",
                )

            elif action.action == "double_click_mouse":

                result = execute_tool(
                    "double_click_mouse",
                )

            else:

                results.append(
                    f"Unsupported action: {action.action}"
                )

                continue

            results.append(result.output)

            if not result.success:
                break

        return results

    def handle(self, user_input: str):

        plan, error = self.build_plan(user_input)

        if error:
            return [f"Planning error: {error}"]

        return self.execute_plan(plan)


if __name__ == "__main__":

    print("================================")
    print("          Z3RO AGENT")
    print("================================")
    print("Type 'exit' to quit.")
    print()

    agent = Z3ROAgent()

    while True:

        user_input = input("You: ").strip()

        if user_input.lower() == "exit":
            print("Z3RO: Shutting down.")
            break

        if not user_input:
            continue

        results = agent.handle(user_input)

        print()

        for result in results:
            print(f"Z3RO: {result}")

        print()