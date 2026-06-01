import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import claude_scraper


class ClaudeScraperTests(unittest.TestCase):
    def test_usage_can_come_from_env(self):
        env = {
            "CLAUDE_SESSION_PCT": "72",
            "CLAUDE_WEEK_PCT": "0.45",
        }

        with patch.dict(os.environ, env, clear=False):
            usage = claude_scraper.get_usage()

        self.assertEqual(usage["session"], 0.72)
        self.assertEqual(usage["week"], 0.45)
        self.assertEqual(usage["design"], -1.0)
        self.assertEqual(usage["sonnet"], -1.0)
        self.assertEqual(usage["source"], "env")

    def test_usage_from_api_data(self):
        data = {
            "five_hour": {"utilization": 12.5, "resets_at": None},
            "seven_day": {"utilization": 34, "resets_at": "2026-05-28T19:00:00+00:00"},
            "seven_day_sonnet": {"utilization": 47, "resets_at": "2026-05-28T19:00:02+00:00"},
        }

        usage = claude_scraper._usage_from_api_data(data, "test")

        self.assertEqual(usage["session"], 0.125)
        self.assertEqual(usage["week"], 0.34)
        self.assertEqual(usage["design"], -1.0)
        self.assertEqual(usage["sonnet"], 0.47)
        self.assertEqual(usage["week_reset"], "2026-05-28T19:00:00+00:00")
        self.assertIsNone(usage["design_reset"])

    def test_extract_json_from_browser_text(self):
        data = claude_scraper._extract_json('{"five_hour":{"utilization":12}}')

        self.assertEqual(data["five_hour"]["utilization"], 12)

    def test_interaction_state_waiting_after_end_turn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "projects" / "-Users-example-test"
            session_dir.mkdir(parents=True)
            path = session_dir / "session.jsonl"
            events = [
                {
                    "timestamp": "2026-05-26T14:00:00.000Z",
                    "type": "assistant",
                    "message": {"stop_reason": "tool_use"},
                },
                {
                    "timestamp": "2026-05-26T14:01:00.000Z",
                    "type": "assistant",
                    "message": {"stop_reason": "end_turn"},
                },
            ]
            path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

            state = claude_scraper.get_interaction_state(claude_home=root)

        self.assertTrue(state["waiting_input"])
        self.assertEqual(state["state"], "waiting_input")

    def test_interaction_state_active_after_human_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "projects" / "-Users-example-test"
            session_dir.mkdir(parents=True)
            path = session_dir / "session.jsonl"
            events = [
                {
                    "timestamp": "2026-05-26T14:00:00.000Z",
                    "type": "assistant",
                    "message": {"stop_reason": "end_turn"},
                },
                {
                    "timestamp": "2026-05-26T14:01:00.000Z",
                    "type": "user",
                    "message": {"role": "user", "content": "continue"},
                },
            ]
            path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

            state = claude_scraper.get_interaction_state(claude_home=root)

        self.assertFalse(state["waiting_input"])
        self.assertEqual(state["state"], "active")


if __name__ == "__main__":
    unittest.main()
