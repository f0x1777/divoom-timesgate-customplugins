import json
import tempfile
import unittest
from pathlib import Path

import codex_scraper


class CodexScraperTests(unittest.TestCase):
    def test_reads_latest_token_count_rate_limits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "sessions" / "2026" / "05" / "26"
            session_dir.mkdir(parents=True)
            path = session_dir / "rollout.jsonl"

            event = {
                "timestamp": "2026-05-26T14:00:00.000Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "info": {
                        "total_token_usage": {"total_tokens": 250},
                        "model_context_window": 1000,
                    },
                    "rate_limits": {
                        "primary": {
                            "used_percent": 18.0,
                            "window_minutes": 300,
                            "resets_at": 1779845065,
                        },
                        "secondary": {
                            "used_percent": 6.0,
                            "window_minutes": 10080,
                            "resets_at": 1780175992,
                        },
                    },
                },
            }
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")

            usage = codex_scraper.get_usage(codex_home=root)

        self.assertEqual(usage["primary"], 0.18)
        self.assertEqual(usage["secondary"], 0.06)
        self.assertEqual(usage["primary_reset"], 1779845065)
        self.assertEqual(usage["secondary_reset"], 1780175992)
        self.assertEqual(usage["primary_window_minutes"], 300)
        self.assertEqual(usage["secondary_window_minutes"], 10080)
        self.assertEqual(usage["context"], 0.25)

    def test_interaction_state_waiting_after_task_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            session_dir = root / "sessions" / "2026" / "05" / "26"
            session_dir.mkdir(parents=True)
            path = session_dir / "rollout.jsonl"
            events = [
                {
                    "timestamp": "2026-05-26T14:00:00.000Z",
                    "type": "event_msg",
                    "payload": {"type": "task_started"},
                },
                {
                    "timestamp": "2026-05-26T14:01:00.000Z",
                    "type": "event_msg",
                    "payload": {"type": "task_complete"},
                },
            ]
            path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

            state = codex_scraper.get_interaction_state(codex_home=root)

        self.assertTrue(state["waiting_input"])
        self.assertEqual(state["state"], "waiting_input")


if __name__ == "__main__":
    unittest.main()
