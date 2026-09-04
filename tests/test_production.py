"""Unit and integration tests for Z3RO/SOBIA production build."""

import unittest
from unittest.mock import patch, MagicMock

from z3ro.config import Config
from z3ro.doctor import SystemDoctor
from z3ro.planner import Planner, extract_json
from z3ro.tools.system import ToolResult


class ProductionBuildTests(unittest.TestCase):

    def test_config_defaults(self):
        """Test configuration defaults are properly populated."""
        cfg = Config()
        self.assertIn(cfg.ASSISTANT_NAME, ["Z3RO", "SOBIA"])
        self.assertEqual(cfg.OLLAMA_HOST, "http://127.0.0.1:11434")
        self.assertEqual(cfg.BRAIN_MODEL, "qwen2.5:1.5b-instruct")
        self.assertEqual(cfg.VISION_MODEL, "moondream:latest")
        self.assertEqual(cfg.AUDIO_SAMPLE_RATE, 16000)

    def test_doctor_python_and_app_catalog(self):
        """Test system doctor checks for python runtime and app catalog."""
        doc = SystemDoctor()
        doc.check_python()
        doc.check_app_catalog()
        doc.check_wakeword()

        results_by_name = {r.name: r for r in doc.results}
        self.assertIn("Python Runtime", results_by_name)
        self.assertTrue(results_by_name["Python Runtime"].passed)
        self.assertIn("App Catalog", results_by_name)
        self.assertTrue(results_by_name["App Catalog"].passed)

    def test_robust_planner_markdown_fences(self):
        """Test planner extract_json with code fences and thinking prefixes."""
        raw_text = """
        Thinking Process:
        1. User wants notepad opened.
        ```json
        {
            "actions": [
                {
                    "action": "open_app",
                    "app": "notepad"
                }
            ]
        }
        ```
        That completes the plan.
        """
        extracted = extract_json(raw_text)
        self.assertIn("actions", extracted)

        planner = Planner()
        plan = planner.parse(raw_text)
        self.assertEqual(len(plan.actions), 1)
        self.assertEqual(plan.actions[0].action, "open_app")
        self.assertEqual(plan.actions[0].app, "notepad")

    @patch("z3ro.agent.Z3ROAgent.execute_action")
    def test_agent_run_alias(self, mock_exec):
        """Test that agent.run() functions as an alias to agent.handle()."""
        from z3ro.agent import Z3ROAgent

        mock_exec.return_value = ToolResult(success=True, output="App opened")

        agent = Z3ROAgent()
        agent.build_plan = MagicMock(
            return_value=(
                MagicMock(actions=[MagicMock(action="open_app", app="notepad")]),
                None,
            )
        )
        agent.verify_action = MagicMock(return_value=True)

        results = agent.run("open notepad")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0], "App opened")

    @patch("z3ro.voice.stt.WhisperModel")
    def test_stt_transcribe(self, mock_whisper_cls):
        """Test STT transcribe handles silence and arrays."""
        import numpy as np
        from z3ro.voice.stt import STT

        mock_instance = MagicMock()
        mock_instance.transcribe.return_value = ([MagicMock(text="hello world")], None)
        mock_whisper_cls.return_value = mock_instance

        stt = STT()
        # Test silence array returns empty string without calling model
        silence = np.zeros(16000, dtype=np.float32)
        self.assertEqual(stt.transcribe(silence), "")

        # Test valid audio array returns transcribed text
        audio = np.ones(16000, dtype=np.float32) * 0.1
        self.assertEqual(stt.transcribe(audio), "hello world")


if __name__ == "__main__":
    unittest.main()
