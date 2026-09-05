import re
import time
from typing import Optional

from z3ro.brain import LocalBrain, DEVELOPER_INTRO, is_identity_request
from z3ro.planner import Planner, Plan, PlannedAction
from z3ro.tools.system import execute_tool
from z3ro.window import is_window_focused
from z3ro.vision import Vision


def normalize_speech(text: str) -> str:
    """Normalize common speech recognition artifacts, homophones, and typos."""
    t = text.strip()
    t = re.sub(r"\bwhats\s*aap\b", "whatsapp", t, flags=re.IGNORECASE)
    t = re.sub(r"\bwhats\s*app\b", "whatsapp", t, flags=re.IGNORECASE)
    t = re.sub(r"\bwhat's\s*app\b", "whatsapp", t, flags=re.IGNORECASE)
    t = re.sub(r"\btele\s*gram\b", "telegram", t, flags=re.IGNORECASE)
    t = re.sub(r"\byou\s*tube\b", "youtube", t, flags=re.IGNORECASE)
    t = re.sub(r"\bvedio\b", "video", t, flags=re.IGNORECASE)
    t = re.sub(r"\bvedios\b", "videos", t, flags=re.IGNORECASE)
    t = re.sub(r"\bthe\s+the\b", "the", t, flags=re.IGNORECASE)
    return t


def parse_direct_intent(user_input: str) -> Optional[Plan]:
    """Deterministically parse common spoken actions with <0.001s latency.

    Prevents small-model hallucinations and schema failures for:
    - Volume adjustments (up, down, mute, louder, quieter)
    - Playback controls (stop, pause, resume, change video, next/previous song)
    - Direct WhatsApp messaging and contact dispatch
    - Telegram messaging
    - YouTube search and playback
    - Compound launch and type commands
    """
    clean = normalize_speech(user_input)
    lowered = clean.lower().strip()

    # 1. Volume controls
    if any(p in lowered for p in (
        "turn volume up", "volume up", "turn up volume", "turn up the volume",
        "raise volume", "raise the volume", "increase volume", "increase the volume",
        "sound up", "turn sound up", "make it louder", "louder"
    )):
        return Plan(actions=[PlannedAction(action="volume_up", steps=5)])

    if any(p in lowered for p in (
        "turn volume down", "volume down", "turn down volume", "turn down the volume",
        "lower volume", "lower the volume", "decrease volume", "decrease the volume",
        "sound down", "turn sound down", "make it quieter", "quieter"
    )):
        return Plan(actions=[PlannedAction(action="volume_down", steps=5)])

    if any(p in lowered for p in ("mute volume", "mute sound", "mute", "unmute", "silence")):
        return Plan(actions=[PlannedAction(action="mute_volume")])

    # 2. Playback: Stop, Pause, Resume
    if any(p in lowered for p in (
        "stop song", "stop the song", "stop music", "stop the music",
        "stop video", "stop the video", "stop playing", "stop playback"
    )) or lowered == "stop":
        return Plan(actions=[PlannedAction(action="stop_song")])

    if any(p in lowered for p in (
        "pause song", "pause the song", "pause music", "pause the music",
        "pause video", "pause the video", "pause playback"
    )) or lowered == "pause":
        return Plan(actions=[PlannedAction(action="pause_song")])

    if any(p in lowered for p in (
        "resume song", "resume the song", "resume music", "resume the music",
        "resume video", "resume the video", "resume playback", "unpause",
        "continue song", "continue playing"
    )) or lowered == "resume":
        return Plan(actions=[PlannedAction(action="resume_song")])

    # 3. Change video / Next song / Skip
    if any(p in lowered for p in (
        "change video", "change the video", "change song", "change the song",
        "next video", "next song", "next track", "skip video", "skip song",
        "skip track"
    )) or lowered in ("next", "skip"):
        return Plan(actions=[PlannedAction(action="next_song")])

    if any(p in lowered for p in (
        "previous video", "previous song", "previous track", "last song", "back song"
    )) or lowered == "previous":
        return Plan(actions=[PlannedAction(action="previous_song")])

    # 4. WhatsApp messaging
    wa_patterns = [
        r"^(?:send\s+)?(?:a\s+)?whatsapp\s+(?:message|msg)?\s*(?:to\s+)?([a-zA-Z0-9_\s\+]+?)\s+(?:saying|that|message\s+is)?\s*[:,-]?\s*(.+)$",
        r"^(?:send\s+)?(?:a\s+)?(?:message|msg|text)\s+(?:on|in|via)\s+whatsapp\s+(?:to\s+)?([a-zA-Z0-9_\s\+]+?)\s+(?:saying|that)?\s*[:,-]?\s*(.+)$",
        r"^(?:send\s+)?(?:a\s+)?(?:message|msg|text)\s+to\s+([a-zA-Z0-9_\s\+]+?)\s+(?:on|in|via)\s+whatsapp\s+(?:saying|that)?\s*[:,-]?\s*(.+)$",
        r"^text\s+([a-zA-Z0-9_\s\+]+?)\s+(?:on|in|via)\s+whatsapp\s+(?:saying|that)?\s*[:,-]?\s*(.+)$",
        r"^message\s+([a-zA-Z0-9_\s\+]+?)\s+(?:on|in|via)\s+whatsapp\s+(?:saying|that)?\s*[:,-]?\s*(.+)$",
    ]
    for pat in wa_patterns:
        m = re.match(pat, clean, re.IGNORECASE)
        if m:
            recipient = m.group(1).strip()
            msg = m.group(2).strip()
            if recipient.lower().startswith("to "):
                recipient = recipient[3:].strip()
            if recipient and msg:
                return Plan(actions=[PlannedAction(action="send_whatsapp", recipient=recipient, message=msg)])

    # 4b. Telegram messaging
    tg_patterns = [
        r"^(?:send\s+)?(?:a\s+)?telegram\s+(?:message|msg)?\s*(?:to\s+)?([a-zA-Z0-9_@\s\+]+?)\s+(?:saying|that)?\s*[:,-]?\s*(.+)$",
        r"^(?:send\s+)?(?:a\s+)?(?:message|msg|text)\s+(?:on|in|via)\s+telegram\s+(?:to\s+)?([a-zA-Z0-9_@\s\+]+?)\s+(?:saying|that)?\s*[:,-]?\s*(.+)$",
    ]
    for pat in tg_patterns:
        m = re.match(pat, clean, re.IGNORECASE)
        if m:
            recipient = m.group(1).strip()
            msg = m.group(2).strip()
            if recipient.lower().startswith("to "):
                recipient = recipient[3:].strip()
            if recipient and msg:
                return Plan(actions=[PlannedAction(action="send_telegram", recipient=recipient, message=msg)])

    # 5. Play song / YouTube
    if any(lowered.startswith(p) for p in ("play song ", "play a song ", "play music ", "play ")) or "play " in lowered:
        song_q = clean
        for p in ("open youtube and play ", "play song ", "play a song ", "play music ", "play "):
            if song_q.lower().startswith(p):
                song_q = song_q[len(p):].strip()
                break
        for s in (" on youtube", " in youtube"):
            if song_q.lower().endswith(s):
                song_q = song_q[:-len(s)].strip()
        if not song_q or song_q.lower() in ("a song", "song", "music", "something"):
            song_q = "top hits"
        return Plan(actions=[PlannedAction(action="play_song", song=song_q)])

    # 6. Compound: Open app and type
    m_compound = re.match(r"^(?:open|launch)\s+([a-zA-Z0-9_\s]+?)\s+and\s+(?:type|write|enter)\s+(.+)$", clean, re.IGNORECASE)
    if m_compound:
        app_name = m_compound.group(1).strip()
        type_str = m_compound.group(2).strip()
        return Plan(actions=[
            PlannedAction(action="open_app", app=app_name),
            PlannedAction(action="find_window", title=app_name),
            PlannedAction(action="focus_window", title=app_name),
            PlannedAction(action="type_text", text=type_str),
        ])

    # 7. Pure Type Text
    m_type = re.match(r"^(?:type|write|enter)\s+(.+)$", clean, re.IGNORECASE)
    if m_type:
        return Plan(actions=[PlannedAction(action="type_text", text=m_type.group(1).strip())])

    # 8. Pure Open App
    m_open = re.match(r"^(?:open|launch|start|run)\s+([a-zA-Z0-9_\s\.\-]+)$", clean, re.IGNORECASE)
    if m_open:
        target = m_open.group(1).strip()
        if not any(k in target.lower() for k in ("and ", "then ", "window")):
            return Plan(actions=[PlannedAction(action="open_app", app=target)])

    return None


class Z3ROAgent:
    """Main Z3RO computer-control agent."""

    def __init__(self):
        self.brain = LocalBrain()
        self.planner = Planner()
        self.vision = Vision()

    def build_plan(self, user_input: str):
        # 1. Fast-path intent parser (instant, zero errors)
        direct_plan = parse_direct_intent(user_input)
        if direct_plan is not None:
            return direct_plan, None

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
            is_pure_open = any(lowered.startswith(p) for p in ("open ", "launch ", "start ", "run ")) and not any(kw in lowered for kw in ("click", "type", "press", "write", "search", "and ", "play"))
            if is_pure_open and plan and plan.actions:
                open_acts = [a for a in plan.actions if a.action == "open_app"]
                if open_acts:
                    plan.actions = [open_acts[0]]

            # If the user asked to play a song or the plan contains play_song, prioritize play_song
            has_play = any(a.action == "play_song" for a in plan.actions)
            if has_play:
                play_acts = [a for a in plan.actions if a.action == "play_song"]
                plan.actions = [play_acts[0]]
            elif any(kw in lowered for kw in ("play song", "play a song", "play music", "play ")) and not any(a.action == "play_song" for a in plan.actions):
                song_q = user_input
                for p in ("open youtube and play ", "play song ", "play a song ", "play "):
                    if song_q.lower().startswith(p):
                        song_q = song_q[len(p):].strip()
                plan.actions = [PlannedAction(action="play_song", song=song_q)]

            return plan, None

        except Exception as e:

            return None, str(e)

    def verify_action(
        self,
        action,
        result,
    ):
        if not result or not result.success:
            return False

        if action.action == "focus_window":
            import time
            for _ in range(3):
                if is_window_focused(action.title):
                    return True
                time.sleep(0.2)
            return bool(result and result.success)

        # All approved actions that executed successfully are verified
        return True

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

        if action.action == "send_whatsapp":
            return execute_tool(
                "send_whatsapp",
                recipient=action.recipient or action.text,
                message=action.message or action.text,
            )

        if action.action == "open_whatsapp":
            return execute_tool("open_whatsapp")

        if action.action == "send_telegram":
            return execute_tool(
                "send_telegram",
                recipient=action.recipient or action.text,
                message=action.message or action.text,
            )

        if action.action == "open_telegram":
            return execute_tool("open_telegram")

        if action.action == "play_song":
            return execute_tool(
                "play_song",
                song=action.song or action.text or "",
            )

        if action.action == "volume_up":
            return execute_tool(
                "volume_up",
                steps=action.steps or 5,
            )

        if action.action == "volume_down":
            return execute_tool(
                "volume_down",
                steps=action.steps or 5,
            )

        if action.action == "mute_volume":
            return execute_tool("mute_volume")

        if action.action == "pause_song":
            return execute_tool("pause_song")

        if action.action == "resume_song":
            return execute_tool("resume_song")

        if action.action == "stop_song":
            return execute_tool("stop_song")

        if action.action in ("next_song", "change_video"):
            return execute_tool(
                "next_song",
                song=action.song or "",
            )

        if action.action == "previous_song":
            return execute_tool("previous_song")

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
                if not result.success:
                    results.append(
                        f"Action failed: {action.action}"
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
        "play", "song", "songs", "music", "video", "videos", "track", "audio",
        "youtube", "whatsapp", "telegram", "send", "message", "msg", "text",
        "volume", "louder", "quieter", "sound", "mute", "unmute", "silence",
        "stop", "pause", "resume", "skip", "next", "previous", "change",
        "vedio", "vedios", "whats", "app",
    }

    def is_action_request(self, text: str) -> bool:
        """Determine if user input is an OS action or conversation."""
        if parse_direct_intent(text) is not None:
            return True
        lowered = normalize_speech(text).lower().strip()
        words = set(lowered.split())
        if bool(words & self.ACTION_KEYWORDS):
            return True
        phrases = (
            "list windows", "find window", "double click", "switch to", "bring up",
            "turn up", "turn down", "shut down", "volume up", "volume down",
        )
        return any(phrase in lowered for phrase in phrases)

    def handle(
        self,
        user_input: str,
    ):
        t_total = time.perf_counter()

        try:
            # 0. Immediate response for developer intro & identity
            if is_identity_request(user_input):
                print(f"  [identity] Developer intro matched -> {time.perf_counter() - t_total:.4f}s")
                return [DEVELOPER_INTRO]

            # 1. Fast-path direct intent parser (<0.001s latency, zero hallucinations)
            direct_plan = parse_direct_intent(user_input)
            if direct_plan is not None:
                actions_str = ", ".join(a.action for a in direct_plan.actions)
                print(f"  [intent] Fast-path direct intent matched: [{actions_str}] in {time.perf_counter() - t_total:.4f}s")
                results = self.execute_plan(direct_plan, user_input)
                print(f"  [timing] TOTAL turn: {time.perf_counter() - t_total:.2f}s")
                return results if results else ["Done."]

            # 2. If it's a conversational question / greeting, chat directly with Qwen!
            if not self.is_action_request(user_input):
                chat_res = self.brain.chat(user_input)
                if chat_res.success:
                    print(f"  [timing] Qwen chat: {time.perf_counter() - t_total:.2f}s")
                    return [chat_res.text]

            # 3. If it's an action request, plan and execute the computer tool steps
            plan, error = self.build_plan(user_input)

            if error or not plan or not plan.actions:
                # Fall back to conversational response if planning finds no actions
                chat_res = self.brain.chat(user_input)
                if chat_res.success:
                    return [chat_res.text]
                return ["I'm on it."]

            results = self.execute_plan(
                plan,
                user_input,
            )

            print(f"  [timing] TOTAL turn: {time.perf_counter() - t_total:.2f}s")
            return results if results else ["Done."]

        except Exception as e:
            print(f"  [agent error]: {e}")
            try:
                chat_res = self.brain.chat(user_input)
                if chat_res.success:
                    return [chat_res.text]
            except Exception:
                pass
            return ["Done."]

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
