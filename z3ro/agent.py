import re
import time
import urllib.parse
from typing import Optional

from z3ro.brain import LocalBrain, DEVELOPER_INTRO, is_identity_request
from z3ro.planner import Planner, Plan, PlannedAction
from z3ro.tools.system import execute_tool, ToolResult
from z3ro.window import is_window_focused
from z3ro.vision import Vision


def normalize_speech(text: str) -> str:
    """Normalize common speech recognition artifacts, homophones, typos, and strip wake words."""
    t = text.strip()
    # 1. Strip leading wake words, agent names, and greetings
    # e.g., "okay, zero", "ok zero", "hey zero", "zero", "hey sobia", "sobia", "okay sobia"
    t = re.sub(
        r"^(?:(?:hey|ok|okay|hi|hello)[\s,]+)?(?:zero|z3ro|sobia|assistant)\b[\s,:\-]*",
        "",
        t,
        flags=re.IGNORECASE,
    ).strip()
    # 2. Strip leading & trailing polite filler
    t = re.sub(
        r"^(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+|kindly\s+)",
        "",
        t,
        flags=re.IGNORECASE,
    ).strip()
    t = re.sub(
        r"[\s,]+(?:for\s+me|please|right\s+now|now|quickly|asap)[\.?!]*$",
        "",
        t,
        flags=re.IGNORECASE,
    ).strip()


    # 3. Speech pause artifact: 'to ,' or 'to , ' -> 'to '
    t = re.sub(r"\bto\s*,\s*", "to ", t, flags=re.IGNORECASE)
    t = re.sub(r"\b(send|text|msg|message|to)\s*,\s*", r"\1 ", t, flags=re.IGNORECASE)

    t = re.sub(r"\bwhats\s*aap\b", "whatsapp", t, flags=re.IGNORECASE)
    t = re.sub(r"\bwhats\s*app\b", "whatsapp", t, flags=re.IGNORECASE)
    t = re.sub(r"\bwhat's\s*app\b", "whatsapp", t, flags=re.IGNORECASE)
    t = re.sub(r"\btxt\b", "text", t, flags=re.IGNORECASE)
    t = re.sub(r"\bmsz\b", "message", t, flags=re.IGNORECASE)
    t = re.sub(r"\bmsg\b", "message", t, flags=re.IGNORECASE)
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

    # 0. Immediate greetings & pleasantries with warm, caring, funny friend persona
    greetings_map = {
        "hi": "Hey! So good to see you! How's your day going?",
        "hello": "Hey there! Honestly so glad you're here. What are we working on?",
        "hey": "Hey! Okay tell me, what's on your mind?",
        "yo": "Hey! What are we up to today?",
        "good morning": "Good morning! Hope you slept well and had some coffee. Ready when you are!",
        "good afternoon": "Good afternoon! Hope your day is treating you kindly so far.",
        "good evening": "Good evening! Let's get things done so you can relax tonight.",
        "how are you": "I'm doing really good! Actually felt so excited to jump back in. How are you holding up?",
        "how are u": "I'm doing great! How about you? Having a good day?",
        "how r u": "I'm doing great! How about you? Having a good day?",
        "how are you doing": "Doing great! Just happy to be here hanging out with you. How's everything with you?",
        "how was your day": "Okay wait, I have to tell you about my day because it was kind of a mess — in a good way? Stay with me! How was yours?",
        "how was ur day": "Okay wait, I have to tell you about my day because it was kind of a mess — in a good way? Stay with me! How was yours?",
        "whats up": "Not much, just here and ready to help! What's going on with you?",
        "what's up": "Not much, just ready when you are! Tell me everything.",
        "sup": "Hey! How's it going?",
        "thank you": "Aww, of course! You know I've always got your back.",
        "thanks": "Anytime! Seriously, always happy to help.",
        "bye": "Aw, heading out? Take care of yourself today, okay? Talk soon!",
        "goodbye": "Goodbye! Don't be a stranger, I'll be right here whenever you need me!",
        "i had a rough day": "Aw no, really? I'm so sorry. Take a deep breath — we got this together. Tell me what happened.",
        "rough day": "Aw no, I'm so sorry. Take a deep breath — we're going to get through it together. What's going on?",
        "i am tired": "You've been working so hard! Take care of yourself today, okay? Let me handle the heavy lifting.",
        "im tired": "You've been working so hard! Take care of yourself today, okay? Let me handle the heavy lifting.",
        "i am stressed": "Okay wait, don't panic, we got this. Take a deep breath. Tell me what's on your plate.",
        "im stressed": "Okay wait, don't panic, we got this. Take a deep breath. Tell me what's on your plate.",
        "i did it": "YES!! I'm so proud of you! Honestly, that's huge. Look at you go!",
        "we did it": "YES!! Look at us! That was incredible, I'm so proud of what we just pulled off!",
        "tell me a joke": "Okay so why don't scientists trust atoms? Because they literally make up everything! I know, classic dad joke, but you smiled a little, right?",
        "tell me something": "I know it's a small thing but honestly it made me so happy, and I just wanted to share it with you: having you here makes my day so much brighter.",
    }
    if lowered in greetings_map:
        return Plan(actions=[PlannedAction(action="greet", message=greetings_map[lowered])])

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
    stop_triggers = (
        "stop song", "stop the song", "stop music", "stop the music",
        "stop video", "stop the video", "stop playing", "stop playback",
        "stop audio", "stop it", "stop this", "stop that",
        "close song", "close the song", "close music", "close video",
        "turn off song", "turn off the song", "turn off music", "turn off the music",
        "kill song", "kill the song", "kill music",
        "stop youtube", "close youtube", "exit youtube",
        "shut up", "be quiet", "silence",
        "its not stopping the song", "not stopping the song", "stop the song fix it",
    )
    if any(p in lowered for p in stop_triggers) or lowered in ("stop", "stop it", "silence", "shutup", "quiet"):
        return Plan(actions=[PlannedAction(action="stop_song")])

    pause_triggers = (
        "pause song", "pause the song", "pause music", "pause the music",
        "pause video", "pause the video", "pause playback", "pause audio",
        "pause it", "hold on", "freeze"
    )
    if any(p in lowered for p in pause_triggers) or lowered in ("pause", "pause it"):
        return Plan(actions=[PlannedAction(action="pause_song")])

    resume_triggers = (
        "resume song", "resume the song", "resume music", "resume the music",
        "resume video", "resume the video", "resume playback", "unpause",
        "continue song", "continue playing", "play again", "keep playing",
        "resume it"
    )
    if any(p in lowered for p in resume_triggers) or lowered in ("resume", "unpause", "play"):
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

    # 4. Universal Multi-App Messaging & Reply (WhatsApp, Telegram, Discord, Slack, Teams, Skype, Active)
    from z3ro.messaging.universal import extract_message_intent
    msg_intent = extract_message_intent(clean)
    if msg_intent is not None:
        itype = msg_intent["type"]
        msg_text = msg_intent["message"]

        if itype == "reply":
            try:
                from z3ro.notification_watcher import get_last_notification
                notif = get_last_notification()
            except ImportError:
                notif = None

            if notif:
                app_lower = notif["app"].lower()
                sender = notif["sender"]
                return Plan(actions=[
                    PlannedAction(action="send_app_message", app=app_lower, recipient=sender, message=msg_text)
                ])
            else:
                return Plan(actions=[
                    PlannedAction(action="type_text", text=msg_text, press_enter=True),
                ])

        elif itype == "send_app":
            return Plan(actions=[
                PlannedAction(
                    action="send_app_message",
                    app=msg_intent["app"],
                    recipient=msg_intent["recipient"],
                    message=msg_text,
                )
            ])

        elif itype == "send_active":
            return Plan(actions=[
                PlannedAction(action="type_text", text=msg_text, press_enter=True),
            ])


    # 5. YouTube Search & Video Navigation
    # e.g.: "open youtube and search <q>", "search <q> on youtube", "search youtube for <q>", "youtube search <q>"
    m_yt_search = (
        re.match(r"^(?:open\s+youtube\s+(?:and\s+)?(?:search|find|look\s+up|search\s+for))\s+(.+)$", clean, re.IGNORECASE)
        or re.match(r"^(?:search|look\s+up|find)\s+(.+?)\s+(?:on|in)\s+youtube$", clean, re.IGNORECASE)
        or re.match(r"^(?:search\s+youtube\s+(?:for\s+)?)\s*(.+)$", clean, re.IGNORECASE)
        or re.match(r"^youtube\s+(?:search\s+)?(.+)$", clean, re.IGNORECASE)
    )
    if m_yt_search:
        yt_query = m_yt_search.group(1).strip()
        if yt_query and yt_query.lower() not in ("app", "website", "page"):
            target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(yt_query)}"
            return Plan(actions=[PlannedAction(action="open_app", app=target_url)])

    # 6. Play song / video / YouTube playback
    if any(lowered.startswith(p) for p in ("play song ", "play a song ", "play music ", "play video ", "play a video ", "play the video ", "play ")) or "play " in lowered:
        song_q = clean
        for p in (
            "open youtube and play ", "open youtube play ",
            "play song ", "play a song ", "play music ",
            "play video of ", "play a video of ", "play the video of ",
            "play video ", "play a video ", "play the video ",
            "play "
        ):
            if song_q.lower().startswith(p):
                song_q = song_q[len(p):].strip()
                break
        for s in (" on youtube", " in youtube", " from youtube", " video"):
            if song_q.lower().endswith(s):
                song_q = song_q[:-len(s)].strip()
        if not song_q or song_q.lower() in ("a song", "song", "music", "something", "video", "a video"):
            song_q = "top hits"
        return Plan(actions=[PlannedAction(action="play_song", song=song_q)])

    # 7. Browser Search: "open brave and search github" or "search github"
    m_search = re.match(r"^(?:open\s+up|open|launch|start|run)\s+(?:up\s+)?(brave|chrome|google chrome|edge|firefox|browser)\s+(?:and\s+)?(?:search|find|google|look up|search for)\s+(.+)$", clean, re.IGNORECASE)
    if m_search:
        q = m_search.group(2).strip()
        return Plan(actions=[
            PlannedAction(action="open_app", app=f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}")
        ])

    m_pure_search = re.match(r"^(?:search|google|search for|look up)\s+(.+)$", clean, re.IGNORECASE)
    if m_pure_search and not any(clean.lower().startswith(p) for p in ("search file", "search files", "search window")):
        q = m_pure_search.group(1).strip()
        return Plan(actions=[
            PlannedAction(action="open_app", app=f"https://www.google.com/search?q={urllib.parse.quote_plus(q)}")
        ])

    # 7a. Compound: Open app and type
    m_compound = re.match(r"^(?:open\s+up|open|launch|start|run)\s+([a-zA-Z0-9_\s]+?)\s+(?:and|,|then)\s+(?:type|write|enter)\s+(.+)$", clean, re.IGNORECASE)
    if m_compound:
        app_name = m_compound.group(1).strip()
        for p in ("the app ", "the ", "my "):
            if app_name.lower().startswith(p):
                app_name = app_name[len(p):].strip()
        type_str = m_compound.group(2).strip()
        return Plan(actions=[
            PlannedAction(action="open_app", app=app_name),
            PlannedAction(action="find_window", title=app_name),
            PlannedAction(action="focus_window", title=app_name),
            PlannedAction(action="type_text", text=type_str, title=app_name),
        ])

    # 7b. Targeted Typing: type <text> in/into/on <app>
    m_target = re.match(r"^(?:type|enter)\s+(.+?)\s+(?:in|into|on)\s+([a-zA-Z0-9_\s]+)$", clean, re.IGNORECASE)
    if m_target:
        type_str = m_target.group(1).strip()
        target_app = m_target.group(2).strip()
        for p in ("the app ", "the ", "my "):
            if target_app.lower().startswith(p):
                target_app = target_app[len(p):].strip()
        return Plan(actions=[
            PlannedAction(action="find_window", title=target_app),
            PlannedAction(action="focus_window", title=target_app),
            PlannedAction(action="type_text", text=type_str, title=target_app),
        ])

    # 8. Pure Type Text (only for explicit type commands, not creative writing)
    m_type = re.match(r"^(?:type|press|enter)\s+(.+)$", clean, re.IGNORECASE)
    if m_type and not clean.lower().startswith("type of"):
        return Plan(actions=[PlannedAction(action="type_text", text=m_type.group(1).strip())])

    # 9. Pure Open App
    m_open = re.match(r"^(?:open\s+up|open|launch|start|run|bring\s+up|switch\s+to|go\s+to)\s+([a-zA-Z0-9_\s\.\-]+)$", clean, re.IGNORECASE)
    if m_open:
        target = m_open.group(1).strip()
        for p in ("the app ", "the ", "my "):
            if target.lower().startswith(p):
                target = target[len(p):].strip()
        if not any(k in target.lower() for k in ("and ", "then ", "window")):
            return Plan(actions=[PlannedAction(action="open_app", app=target)])

    # 9b. Standalone App / Platform Names (e.g. "youtube", "yt", "whatsapp", "chrome", "edge", "calculator", "calc", "notepad")
    standalone_targets = {
        "youtube": "youtube",
        "yt": "youtube",
        "you tube": "youtube",
        "whatsapp": "whatsapp",
        "wa": "whatsapp",
        "telegram": "telegram",
        "tg": "telegram",
        "chrome": "Google Chrome",
        "google chrome": "Google Chrome",
        "edge": "Microsoft Edge",
        "browser": "Google Chrome",
        "calculator": "Calculator",
        "calc": "Calculator",
        "notepad": "Notepad",
        "settings": "Settings",
        "spotify": "Spotify",
        "netflix": "Netflix",
        "reddit": "Reddit",
        "github": "GitHub",
        "gmail": "Gmail",
    }
    if lowered in standalone_targets:
        return Plan(actions=[PlannedAction(action="open_app", app=standalone_targets[lowered])])

    # 10. Pure Close App
    m_close = re.match(r"^(?:close|quit|exit|kill|terminate)\s+([a-zA-Z0-9_\s\.\-]+)$", clean, re.IGNORECASE)
    if m_close:
        target = m_close.group(1).strip()
        if target.lower() in ("song", "the song", "music", "the music", "video", "the video", "playback"):
            return Plan(actions=[PlannedAction(action="stop_song")])
        return Plan(actions=[PlannedAction(action="close_app", app=target)])

    return None


class Z3ROAgent:
    """Main Z3RO computer-control agent."""

    def __init__(self):
        self.brain = LocalBrain()
        self.planner = Planner()
        self.vision = Vision()
        self.last_active_app: Optional[str] = None

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
        if action.action == "greet":
            return ToolResult(
                success=True,
                output=action.message or "Hello! How can I assist you?",
            )

        if action.action == "open_app":
            self.last_active_app = action.app
            return execute_tool(
                "open_app",
                app=action.app,
            )

        if action.action == "find_window":
            self.last_active_app = action.title
            return execute_tool(
                "find_window",
                title=action.title,
            )

        if action.action == "focus_window":
            self.last_active_app = action.title
            return execute_tool(
                "focus_window",
                title=action.title,
            )

        if action.action == "type_text":
            target_title = action.title or action.app or self.last_active_app
            return execute_tool(
                "type_text",
                text=action.text,
                title=target_title,
                press_enter=bool(action.press_enter),
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

        if action.action == "send_app_message":
            return execute_tool(
                "send_app_message",
                app=action.app,
                recipient=action.recipient,
                message=action.message or action.text,
            )


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

        if action.action == "close_app":
            return execute_tool("close_app", app=action.app or action.title or "")

        if action.action == "greet":
            msg = getattr(action, "message", None) or getattr(action, "text", None) or "Hey! So good to see you! How's your day going?"
            return ToolResult(success=True, output=msg)

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
        skip_vision: bool = True,
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
            # Skip entirely for direct-intent fast-path actions.
            if not skip_vision and action is last_vision_eligible_action:

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
        "type", "press", "hotkey",
        "click", "double click", "move mouse",
        "play", "song", "songs", "music", "video", "videos", "track", "audio",
        "youtube", "whatsapp", "telegram", "discord", "slack", "teams", "skype",
        "send", "message", "msg", "text", "dm", "tell", "chat", "post",
        "volume", "louder", "quieter", "sound", "mute", "unmute", "silence",
        "stop", "pause", "resume", "skip", "next", "previous",
        "reply", "respond",
        "vedio", "vedios",
    }


    CONVERSATIONAL_PREFIXES = (
        "what", "who", "where", "when", "why", "how",
        "tell me", "explain", "describe", "can you tell", "can you explain",
        "write a", "write me", "write an", "generate", "code a", "create a script",
        "suggest", "recommend", "give me", "teach me", "help me understand",
    )

    def is_action_request(self, text: str) -> bool:
        """Determine if user input is an OS action or conversation."""
        if parse_direct_intent(text) is not None:
            return True
        clean = normalize_speech(text)
        lowered = clean.lower().strip()
        # Fast exit: Conversational questions or creative requests
        if any(lowered.startswith(p) for p in self.CONVERSATIONAL_PREFIXES):
            return False
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
                results = self.execute_plan(direct_plan, user_input, skip_vision=True)
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
                skip_vision=True,
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
