from z3ro.brain import LocalBrain, parse_decision
from z3ro.tools.system import execute_tool


class Z3ROAgent:

    def __init__(self):
        self.brain = LocalBrain()

    def handle(self, user_input: str) -> str:

        brain_response = self.brain.think(user_input)
        decision = parse_decision(brain_response)

        if decision.action == "open_app":
            result = execute_tool(
                "open_app",
                app=decision.app,
            )

            return result.output

        if decision.response:
            return decision.response

        return "I couldn't determine what to do."


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

        result = agent.handle(user_input)

        print(f"Z3RO: {result}")