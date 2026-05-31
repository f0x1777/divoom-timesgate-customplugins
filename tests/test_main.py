import contextlib
import io
import os
import sys
import types
import unittest
from unittest.mock import patch

import main


class UsageDisplayTests(unittest.TestCase):
    def setUp(self):
        main.CODEX_WAITING_INPUT = False
        main.CODEX_INTERACTION_STATUS = "chilling"
        main.LAST_CODEX_WAITING_INPUT = None
        main.LAST_CODEX_USAGE = None
        main.LAST_CODEX_DISPLAY_SIGNATURE = None
        main.CLAUDE_WAITING_INPUT = False
        main.CLAUDE_INTERACTION_STATUS = "chilling"
        main.LAST_CLAUDE_WAITING_INPUT = None
        main.LAST_CLAUDE_USAGE = None
        main.LAST_LIMIT_ZERO_STATE = {}
        main.LAST_CALENDAR_ALERT_KEYS = set()
        main.LAST_PANEL_DIGESTS = {}
        main.LAST_IMMUTABLE_PANEL_SENDS = set()

    def test_unknown_usage_is_not_known(self):
        usage = {"session": -1.0, "week": -1.0, "design": -1.0}

        self.assertFalse(main.usage_is_known(usage))

    def test_partial_usage_is_known(self):
        usage = {"session": 0.25, "week": -1.0, "design": -1.0}

        self.assertTrue(main.usage_is_known(usage))

    def test_percent_conversion_clamps_unknown_to_zero_for_display(self):
        self.assertEqual(main.to_percent(-1.0), 0)
        self.assertEqual(main.to_percent(0.728), 72)

    def test_normalize_mac_pads_arp_short_octets(self):
        self.assertEqual(main.normalize_mac("44:4f:8e:e9:f:62"), "44:4f:8e:e9:0f:62")

    def test_run_once_does_not_send_when_usage_is_unknown(self):
        claude = {"session": -1.0, "week": -1.0, "design": -1.0}
        codex = {"primary": -1.0, "secondary": -1.0, "context": -1.0}

        with patch("claude_scraper.get_usage", return_value=claude), \
             patch("codex_scraper.get_usage", return_value=codex), \
             patch("main.refresh_codex_interaction_state", return_value=False), \
             patch("main.refresh_claude_interaction_state", return_value=False), \
             patch("main.send_claude_usage") as send_claude_usage, \
             patch("main.send_codex_usage") as send_codex_usage, \
             contextlib.redirect_stdout(io.StringIO()):
            ok = main.run_once(verbose=False, hold_secs=0)

        self.assertFalse(ok)
        send_claude_usage.assert_not_called()
        send_codex_usage.assert_not_called()

    def test_run_once_sends_known_codex_when_claude_is_unknown(self):
        claude = {"session": -1.0, "week": -1.0, "design": -1.0}
        codex = {"primary": 0.12, "secondary": 0.04, "context": 0.20}

        with patch("claude_scraper.get_usage", return_value=claude), \
             patch("codex_scraper.get_usage", return_value=codex), \
             patch("main.refresh_codex_interaction_state", return_value=False), \
             patch("main.refresh_claude_interaction_state", return_value=False), \
             patch("main.send_claude_usage") as send_claude_usage, \
             patch("main.send_codex_usage", return_value=True) as send_codex_usage, \
             patch("main.send_static_panels", return_value=True), \
             contextlib.redirect_stdout(io.StringIO()):
            ok = main.run_once(verbose=False, hold_secs=0)

        self.assertTrue(ok)
        send_claude_usage.assert_not_called()
        send_codex_usage.assert_called_once_with(codex)

    def test_codex_usage_sends_explicit_limit_panels(self):
        fake_divoom = types.SimpleNamespace()
        fake_divoom.calls = []
        fake_divoom.set_brightness = lambda ip, level: fake_divoom.calls.append(("brightness", ip, level)) or True
        fake_divoom.send_image_panel = (
            lambda *args: fake_divoom.calls.append(("panels", args)) or True
        )

        usage = {"primary": 0.32, "secondary": 0.77, "context": 0.33}
        with patch.dict(sys.modules, {"divoom": fake_divoom}), \
             contextlib.redirect_stdout(io.StringIO()):
            ok = main.send_codex_usage(usage)

        self.assertTrue(ok)
        self.assertEqual(fake_divoom.calls[0][0], "brightness")
        self.assertEqual(fake_divoom.calls[1][0], "panels")
        self.assertEqual(fake_divoom.calls[1][1][1:3], (0, "codex.gif"))
        self.assertIsInstance(fake_divoom.calls[1][1][3], bytes)

    def test_send_image_panel_if_changed_skips_identical_payload(self):
        fake_divoom = types.SimpleNamespace()
        fake_divoom.calls = []
        fake_divoom.send_image_panel = lambda *args: fake_divoom.calls.append(args) or True

        with patch.dict(sys.modules, {"divoom": fake_divoom}), \
             contextlib.redirect_stdout(io.StringIO()):
            first = main.send_image_panel_if_changed(2, "center.gif", b"same-panel", "center")
            second = main.send_image_panel_if_changed(2, "center.gif", b"same-panel", "center")
            third = main.send_image_panel_if_changed(2, "center.gif", b"changed-panel", "center")

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertTrue(third)
        self.assertEqual(len(fake_divoom.calls), 2)

    def test_send_image_panel_if_changed_does_not_cache_failed_send(self):
        fake_divoom = types.SimpleNamespace()
        fake_divoom.results = [False, True]
        fake_divoom.calls = []

        def send_image_panel(*args):
            fake_divoom.calls.append(args)
            return fake_divoom.results.pop(0)

        fake_divoom.send_image_panel = send_image_panel

        with patch.dict(sys.modules, {"divoom": fake_divoom}), \
             contextlib.redirect_stdout(io.StringIO()):
            first = main.send_image_panel_if_changed(1, "ops.gif", b"ops-panel", "ops")
            second = main.send_image_panel_if_changed(1, "ops.gif", b"ops-panel", "ops")

        self.assertFalse(first)
        self.assertTrue(second)
        self.assertEqual(len(fake_divoom.calls), 2)

    def test_static_panels_use_configured_layout_slots(self):
        fake_divoom = types.SimpleNamespace()
        fake_divoom.calls = []
        fake_divoom.send_image_panel = (
            lambda *args: fake_divoom.calls.append(args) or True
        )

        previous = (main.SCREEN_1_PANEL, main.SCREEN_2_PANEL, main.SCREEN_3_PANEL)
        main.SCREEN_1_PANEL = "ops"
        main.SCREEN_2_PANEL = "center"
        main.SCREEN_3_PANEL = "calendar"
        try:
            with patch.dict(sys.modules, {"divoom": fake_divoom}), \
                 patch("main.render_static_panel", side_effect=lambda panel: panel.encode()):
                ok = main.send_static_panels()
        finally:
            main.SCREEN_1_PANEL, main.SCREEN_2_PANEL, main.SCREEN_3_PANEL = previous

        self.assertTrue(ok)
        self.assertEqual([call[1:3] for call in fake_divoom.calls], [(1, "ops.gif"), (2, "center.gif"), (3, "calendar.gif")])

    def test_immutable_static_panel_is_sent_once_after_success(self):
        fake_divoom = types.SimpleNamespace()
        fake_divoom.calls = []
        fake_divoom.send_image_panel = (
            lambda *args: fake_divoom.calls.append(args) or True
        )

        with patch.dict(os.environ, {"DIVOOM_IMMUTABLE_PANELS": "center,gengar,mascot"}), \
             patch.dict(sys.modules, {"divoom": fake_divoom}), \
             patch("main.render_static_panel", return_value=b"center") as render_static_panel, \
             contextlib.redirect_stdout(io.StringIO()):
            first = main.send_static_panel(2, "center")
            second = main.send_static_panel(2, "center")

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(len(fake_divoom.calls), 1)
        render_static_panel.assert_called_once_with("center")

    def test_failed_immutable_static_panel_retries_later(self):
        fake_divoom = types.SimpleNamespace()
        fake_divoom.results = [False, True]
        fake_divoom.calls = []

        def send_image_panel(*args):
            fake_divoom.calls.append(args)
            return fake_divoom.results.pop(0)

        fake_divoom.send_image_panel = send_image_panel

        with patch.dict(os.environ, {"DIVOOM_IMMUTABLE_PANELS": "center,gengar,mascot"}), \
             patch.dict(sys.modules, {"divoom": fake_divoom}), \
             patch("main.render_static_panel", return_value=b"center"), \
             contextlib.redirect_stdout(io.StringIO()):
            first = main.send_static_panel(2, "center")
            second = main.send_static_panel(2, "center")

        self.assertFalse(first)
        self.assertTrue(second)
        self.assertEqual(len(fake_divoom.calls), 2)

    def test_static_panel_supports_generic_aliases(self):
        with patch("dashboard_renderer.render_gengar_panel", return_value=b"center") as render_center, \
             patch("dashboard_renderer.render_clauddy_panel", return_value=b"clauddy") as render_clauddy, \
             patch("dashboard_renderer.render_clawd_panel", return_value=b"status") as render_status:
            self.assertEqual(main.render_static_panel("center"), b"center")
            self.assertEqual(main.render_static_panel("clauddy"), b"clauddy")
            self.assertEqual(main.render_static_panel("status"), b"status")

        render_center.assert_called_once()
        render_clauddy.assert_called_once_with("chilling")
        render_status.assert_called_once()

    def test_codex_waiting_transition_beeps_once(self):
        main.CODEX_WAITING_INPUT = False
        main.LAST_CODEX_WAITING_INPUT = False

        with patch.dict(os.environ, {"CODEX_WAITING_AUTO": "1", "BEEP_ON_CODEX_WAITING": "1"}), \
             patch("codex_scraper.get_interaction_state", return_value={"waiting_input": True, "state": "waiting_input"}), \
             patch("main.beep_for_interaction") as beep_for_interaction, \
             contextlib.redirect_stdout(io.StringIO()):
            changed = main.refresh_codex_interaction_state(beep=True)

        self.assertTrue(changed)
        self.assertTrue(main.CODEX_WAITING_INPUT)
        self.assertEqual(main.CODEX_INTERACTION_STATUS, "alerting")
        beep_for_interaction.assert_called_once()

    def test_interaction_status_maps_active_to_working(self):
        main.LAST_CODEX_WAITING_INPUT = False

        with patch.dict(os.environ, {"CODEX_WAITING_AUTO": "1"}), \
             patch("codex_scraper.get_interaction_state", return_value={"waiting_input": False, "state": "active"}), \
             contextlib.redirect_stdout(io.StringIO()):
            changed = main.refresh_codex_interaction_state(beep=False)

        self.assertTrue(changed)
        self.assertFalse(main.CODEX_WAITING_INPUT)
        self.assertEqual(main.CODEX_INTERACTION_STATUS, "working")

    def test_waiting_display_refreshes_on_state_change(self):
        main.CODEX_WAITING_INPUT = True
        main.LAST_CODEX_WAITING_INPUT = False
        main.LAST_CODEX_USAGE = {"primary": 0.2, "secondary": 0.4, "context": 0.1}

        with patch("main.refresh_codex_interaction_state", return_value=True), \
             patch("main.refresh_claude_interaction_state", return_value=False), \
             patch("main.send_codex_usage", return_value=True) as send_codex_usage, \
             patch("main.send_static_panels", return_value=True) as send_static_panels, \
             patch("main.emit_pending_beeps") as emit_pending_beeps:
            ok = main.refresh_waiting_display_if_needed()

        self.assertTrue(ok)
        send_codex_usage.assert_called_once_with(main.LAST_CODEX_USAGE)
        send_static_panels.assert_called_once()
        emit_pending_beeps.assert_called_once_with(True, False)

    def test_waiting_display_beeps_after_panel_refresh(self):
        calls = []
        main.CODEX_WAITING_INPUT = True
        main.LAST_CODEX_WAITING_INPUT = False
        main.LAST_CODEX_USAGE = {"primary": 0.2, "secondary": 0.4, "context": 0.1}

        with patch("main.refresh_codex_interaction_state", return_value=True), \
             patch("main.refresh_claude_interaction_state", return_value=False), \
             patch("main.send_codex_usage", side_effect=lambda usage: calls.append("codex-panel") or True), \
             patch("main.send_static_panels", side_effect=lambda: calls.append("static-panels") or True), \
             patch("main.emit_pending_beeps", side_effect=lambda codex, claude: calls.append((codex, claude))):
            ok = main.refresh_waiting_display_if_needed()

        self.assertTrue(ok)
        self.assertEqual(calls, ["codex-panel", "static-panels", (True, False)])

    def test_claude_waiting_transition_beeps_once(self):
        main.CLAUDE_WAITING_INPUT = False
        main.LAST_CLAUDE_WAITING_INPUT = False

        with patch.dict(os.environ, {"CLAUDE_WAITING_AUTO": "1", "BEEP_ON_CLAUDE_WAITING": "1"}), \
             patch("claude_scraper.get_interaction_state", return_value={"waiting_input": True, "state": "waiting_input"}), \
             patch("main.beep_for_interaction") as beep_for_interaction, \
             contextlib.redirect_stdout(io.StringIO()):
            changed = main.refresh_claude_interaction_state(beep=True)

        self.assertTrue(changed)
        self.assertTrue(main.CLAUDE_WAITING_INPUT)
        self.assertEqual(main.CLAUDE_INTERACTION_STATUS, "alerting")
        beep_for_interaction.assert_called_once_with("CLAUDE")

    def test_claude_waiting_display_refreshes_on_state_change(self):
        main.CLAUDE_WAITING_INPUT = True
        main.LAST_CLAUDE_WAITING_INPUT = False
        main.LAST_CLAUDE_USAGE = {"session": 0.2, "week": 0.4, "design": 0.1}

        with patch("main.refresh_codex_interaction_state", return_value=False), \
             patch("main.refresh_claude_interaction_state", return_value=True), \
             patch("main.send_claude_usage", return_value=True) as send_claude_usage, \
             patch("main.send_static_panels", return_value=True) as send_static_panels, \
             patch("main.emit_pending_beeps") as emit_pending_beeps:
            ok = main.refresh_waiting_display_if_needed()

        self.assertTrue(ok)
        send_claude_usage.assert_called_once_with(main.LAST_CLAUDE_USAGE)
        send_static_panels.assert_called_once()
        emit_pending_beeps.assert_called_once_with(False, True)

    def test_codex_usage_watch_refreshes_when_displayed_usage_changes(self):
        main.LAST_CODEX_DISPLAY_SIGNATURE = (90, 10, 1, 2, False)
        usage = {
            "primary": 0.08,
            "secondary": 0.95,
            "context": 0.3,
            "primary_reset": 1,
            "secondary_reset": 2,
        }

        with patch("main.get_codex_usage", return_value=usage), \
             patch("main.send_codex_usage", return_value=True) as send_codex_usage, \
             patch("main.emit_limit_alerts") as emit_limit_alerts, \
             contextlib.redirect_stdout(io.StringIO()):
            ok = main.refresh_codex_usage_display_if_needed()

        self.assertTrue(ok)
        send_codex_usage.assert_called_once_with(usage)
        emit_limit_alerts.assert_called_once()

    def test_codex_usage_watch_retries_after_failed_send(self):
        usage = {
            "primary": 0.08,
            "secondary": 0.95,
            "context": 0.3,
            "primary_reset": 1,
            "secondary_reset": 2,
        }

        with patch("main.get_codex_usage", return_value=usage), \
             patch("main.send_codex_usage", return_value=False) as send_codex_usage, \
             patch("main.emit_limit_alerts"), \
             contextlib.redirect_stdout(io.StringIO()):
            first = main.refresh_codex_usage_display_if_needed()
            second = main.refresh_codex_usage_display_if_needed()

        self.assertFalse(first)
        self.assertFalse(second)
        self.assertEqual(send_codex_usage.call_count, 2)

    def test_interaction_beep_prefers_divoom_buzzer(self):
        fake_divoom = types.SimpleNamespace()
        fake_divoom.play_buzzer = lambda *args: True

        with patch.dict(
            os.environ,
            {
                "BEEP_ON_CODEX_WAITING": "1",
                "DIVOOM_BEEP": "1",
                "DIVOOM_BEEP_TOTAL_MS": "1200",
                "DIVOOM_BEEP_ACTIVE_MS": "200",
                "DIVOOM_BEEP_OFF_MS": "150",
            },
        ), \
             patch.dict(sys.modules, {"divoom": fake_divoom}), \
             patch("subprocess.run") as subprocess_run, \
             contextlib.redirect_stdout(io.StringIO()):
            main.beep_for_interaction("CODEX")

        subprocess_run.assert_not_called()

    def test_limit_alerts_trigger_when_limit_reaches_zero(self):
        with patch.dict(os.environ, {"BEEP_ON_LIMIT_ALERTS": "1"}):
            initial = main.collect_limit_alerts(
                "codex",
                {"primary": 0.5, "secondary": 0.2, "context": 0.1},
            )
            exhausted = main.collect_limit_alerts(
                "codex",
                {"primary": 1.0, "secondary": 0.2, "context": 0.1},
            )

        self.assertEqual(initial, [])
        self.assertEqual(exhausted, [("codex", "5h", "exhausted")])

    def test_limit_alerts_trigger_when_limit_resets(self):
        main.LAST_LIMIT_ZERO_STATE["claude:week"] = True

        with patch.dict(os.environ, {"BEEP_ON_LIMIT_ALERTS": "1"}):
            events = main.collect_limit_alerts(
                "claude",
                {"session": 0.2, "week": 0.5, "design": 0.3, "sonnet": 0.4},
            )

        self.assertEqual(events, [("claude", "WK", "reset")])

    def test_limit_alerts_can_be_disabled_per_provider(self):
        main.LAST_LIMIT_ZERO_STATE["codex:primary"] = False

        with patch.dict(os.environ, {"BEEP_ON_CODEX_LIMIT_ALERTS": "0"}):
            events = main.collect_limit_alerts(
                "codex",
                {"primary": 1.0, "secondary": 0.2, "context": 0.1},
            )

        self.assertEqual(events, [])

    def test_calendar_event_alerts_beep_once_per_event(self):
        event = {"uid": "event-1", "start": "2026-05-27T10:00:00-03:00", "summary": "Private"}

        with patch.dict(os.environ, {"BEEP_ON_CALENDAR_EVENTS": "1"}), \
             patch("calendar_provider.get_due_events", return_value=[event]):
            first = main.collect_calendar_event_alerts()
            second = main.collect_calendar_event_alerts()

        self.assertEqual(first, [event])
        self.assertEqual(second, [])

    def test_calendar_event_alerts_can_be_disabled(self):
        event = {"uid": "event-1", "start": "2026-05-27T10:00:00-03:00"}

        with patch.dict(os.environ, {"BEEP_ON_CALENDAR_EVENTS": "0"}), \
             patch("calendar_provider.get_due_events", return_value=[event]):
            events = main.collect_calendar_event_alerts()

        self.assertEqual(events, [])


if __name__ == "__main__":
    unittest.main()
