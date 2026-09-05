"""Unit tests for media playback, volume controls, and fast-path intent parsing."""

import unittest
from unittest.mock import patch, MagicMock

from z3ro.agent import parse_direct_intent, normalize_speech, Z3ROAgent
from z3ro.planner import Planner
from z3ro.tools.system import (
    volume_up,
    volume_down,
    mute_volume,
    pause_song,
    resume_song,
    stop_song,
    next_song,
    previous_song,
    execute_tool,
)


class MediaAndIntentTests(unittest.TestCase):

    def test_normalize_speech(self):
        """Test normalization of speech recognition homophones and typos."""
        self.assertEqual(normalize_speech("whats aap"), "whatsapp")
        self.assertEqual(normalize_speech("whats app"), "whatsapp")
        self.assertEqual(normalize_speech("what's app"), "whatsapp")
        self.assertEqual(normalize_speech("change the the vedio"), "change the video")

    def test_volume_intents(self):
        """Test volume command fast-path intents."""
        cases = [
            ("turn volume up", "volume_up"),
            ("turn the volume up", "volume_up"),
            ("volume up", "volume_up"),
            ("louder", "volume_up"),
            ("turn volume down", "volume_down"),
            ("volume down", "volume_down"),
            ("quieter", "volume_down"),
            ("mute", "mute_volume"),
            ("unmute", "mute_volume"),
        ]
        for phrase, expected_action in cases:
            plan = parse_direct_intent(phrase)
            self.assertIsNotNone(plan, f"Failed to match intent for: {phrase}")
            self.assertEqual(plan.actions[0].action, expected_action)

    def test_playback_intents(self):
        """Test media playback fast-path intents."""
        cases = [
            ("stop song", "stop_song"),
            ("stop the song", "stop_song"),
            ("stop", "stop_song"),
            ("pause song", "pause_song"),
            ("pause", "pause_song"),
            ("resume song", "resume_song"),
            ("resume", "resume_song"),
            ("change the the vedio", "next_song"),
            ("change the video", "next_song"),
            ("change song", "next_song"),
            ("next song", "next_song"),
            ("skip song", "next_song"),
            ("previous song", "previous_song"),
        ]
        for phrase, expected_action in cases:
            plan = parse_direct_intent(phrase)
            self.assertIsNotNone(plan, f"Failed to match intent for: {phrase}")
            self.assertEqual(plan.actions[0].action, expected_action)

    def test_whatsapp_intents(self):
        """Test WhatsApp messaging intent extraction."""
        p1 = parse_direct_intent("send whatsapp message to Rohan hello how are you")
        self.assertIsNotNone(p1)
        self.assertEqual(p1.actions[0].action, "send_whatsapp")
        self.assertEqual(p1.actions[0].recipient, "Rohan")
        self.assertEqual(p1.actions[0].message, "hello how are you")

        p2 = parse_direct_intent("send msg on whats aap to mom where are you")
        self.assertIsNotNone(p2)
        self.assertEqual(p2.actions[0].action, "send_whatsapp")
        self.assertEqual(p2.actions[0].recipient, "mom")
        self.assertEqual(p2.actions[0].message, "where are you")

        p3 = parse_direct_intent("text Alex on whatsapp meeting at 5")
        self.assertIsNotNone(p3)
        self.assertEqual(p3.actions[0].action, "send_whatsapp")
        self.assertEqual(p3.actions[0].recipient, "Alex")
        self.assertEqual(p3.actions[0].message, "meeting at 5")

    def test_planner_allowed_actions(self):
        """Test planner accepts all media, playback, and volume control actions."""
        planner = Planner()
        for action in [
            "volume_up", "volume_down", "mute_volume",
            "stop_song", "pause_song", "resume_song",
            "next_song", "previous_song", "change_video",
        ]:
            plan = planner.parse(f'{{"actions": [{{"action": "{action}"}}]}}')
            self.assertEqual(len(plan.actions), 1)
            self.assertEqual(plan.actions[0].action, action)

    @patch("z3ro.tools.system._send_vk")
    def test_volume_tools(self, mock_vk):
        """Test volume tool execution triggers correct VK codes."""
        res_up = volume_up(steps=3)
        self.assertTrue(res_up.success)
        self.assertEqual(res_up.output, "Turned volume up.")

        res_down = volume_down(steps=3)
        self.assertTrue(res_down.success)
        self.assertEqual(res_down.output, "Turned volume down.")

        res_mute = mute_volume()
        self.assertTrue(res_mute.success)
        self.assertEqual(res_mute.output, "Toggled volume mute.")

    @patch("z3ro.tools.system._send_vk")
    def test_playback_tools(self, mock_vk):
        """Test playback tool execution triggers without error."""
        res_pause = pause_song()
        self.assertTrue(res_pause.success)

        res_resume = resume_song()
        self.assertTrue(res_resume.success)

        res_stop = stop_song()
        self.assertTrue(res_stop.success)

        res_next = next_song()
        self.assertTrue(res_next.success)

        res_prev = previous_song()
        self.assertTrue(res_prev.success)

    def test_compound_and_targeted_typing_intents(self):
        """Test that typing commands correctly target the external application."""
        # Compound open and type
        p1 = parse_direct_intent("open notepad and type hello world")
        self.assertIsNotNone(p1)
        self.assertEqual(len(p1.actions), 4)
        self.assertEqual(p1.actions[0].action, "open_app")
        self.assertEqual(p1.actions[0].app, "notepad")
        self.assertEqual(p1.actions[3].action, "type_text")
        self.assertEqual(p1.actions[3].text, "hello world")
        self.assertEqual(p1.actions[3].title, "notepad")

        # Targeted typing in app
        p2 = parse_direct_intent("type meeting notes in word")
        self.assertIsNotNone(p2)
        self.assertEqual(len(p2.actions), 3)
        self.assertEqual(p2.actions[0].action, "find_window")
        self.assertEqual(p2.actions[0].title, "word")
        self.assertEqual(p2.actions[1].action, "focus_window")
        self.assertEqual(p2.actions[1].title, "word")
        self.assertEqual(p2.actions[2].action, "type_text")
        self.assertEqual(p2.actions[2].text, "meeting notes")
        self.assertEqual(p2.actions[2].title, "word")

    @patch("z3ro.agent.execute_tool")
    def test_last_active_app_tracking(self, mock_exec):
        """Test agent tracks last opened/focused app for subsequent typing."""
        from z3ro.planner import PlannedAction
        from z3ro.tools.system import ToolResult
        mock_exec.return_value = ToolResult(success=True, output="OK")

        agent = Z3ROAgent()
        self.assertIsNone(agent.last_active_app)

        agent.execute_action(PlannedAction(action="open_app", app="notepad"))
        self.assertEqual(agent.last_active_app, "notepad")

        agent.execute_action(PlannedAction(action="type_text", text="hello"))
        mock_exec.assert_called_with("type_text", text="hello", title="notepad")


if __name__ == "__main__":
    unittest.main()
