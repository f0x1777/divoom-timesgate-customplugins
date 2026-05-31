import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image

import dashboard_renderer


class DashboardRendererTests(unittest.TestCase):
    def test_usage_values_are_rendered_as_available_capacity(self):
        self.assertEqual(dashboard_renderer._pct(dashboard_renderer._available_from_used(0.08)), "92%")
        self.assertEqual(dashboard_renderer._pct(dashboard_renderer._available_from_used(0.83)), "17%")

    def test_dolarapi_price_is_not_k_abbreviated(self):
        self.assertEqual(dashboard_renderer._short_price(1435.9, {"source": "dolarapi"}), "1436")

    def test_ops_panel_renders_bytes(self):
        gif = dashboard_renderer.render_ops_panel(
            [{"label": "BTC", "price": 123456, "change_pct": 1.2}],
            {"cpu": 10, "memory": 20, "cpu_temp_c": 53.2, "net_in_mbps": 1.2, "net_out_mbps": 0.4},
            [],
        )

        self.assertIsInstance(gif, bytes)
        self.assertGreater(len(gif), 100)

    def test_usage_panels_show_single_frame_waiting_overlay(self):
        usage = {"primary": 0.1, "secondary": 0.2, "primary_reset": "2026-05-27T15:00:00-03:00"}
        normal = dashboard_renderer.render_codex_panel(usage, waiting=False)
        codex = dashboard_renderer.render_codex_panel(
            {"primary": 0.1, "secondary": 0.2, "primary_reset": "2026-05-27T15:00:00-03:00"},
            waiting=True,
        )
        claude = dashboard_renderer.render_claude_panel(
            {"session": 0.1, "week": 0.2, "design": 0.3, "sonnet": 0.4},
            waiting=True,
        )

        self.assertEqual(self._gif_frame_count(codex), 1)
        self.assertEqual(self._gif_frame_count(claude), 1)
        self.assertNotEqual(normal, codex)

    def test_usage_panel_status_badge_changes_render(self):
        usage = {"primary": 0.1, "secondary": 0.2}

        idle = dashboard_renderer.render_codex_panel(usage, status="chilling")
        working = dashboard_renderer.render_codex_panel(usage, status="working")

        self.assertNotEqual(idle, working)

    def test_resource_bar_width_is_clamped(self):
        self.assertEqual(dashboard_renderer._bar_fill_width(-1, 68), 0)
        self.assertEqual(dashboard_renderer._bar_fill_width(50, 68), 34)
        self.assertEqual(dashboard_renderer._bar_fill_width(150, 68), 68)

    def test_temp_metric_formats_celsius(self):
        self.assertEqual(dashboard_renderer._temp_value(-1), "--C")
        self.assertEqual(dashboard_renderer._temp_value(53.2), "53C")

    def test_temp_bar_uses_30_to_100_default_range(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(dashboard_renderer._temp_fill_width(30, 70), 0)
            self.assertEqual(dashboard_renderer._temp_fill_width(65, 70), 35)
            self.assertEqual(dashboard_renderer._temp_fill_width(100, 70), 70)

    def test_health_panel_renders_bytes(self):
        gif = dashboard_renderer.render_health_panel(
            {
                "checks": [
                    {"label": "WEB", "ok": True, "detail": "200"},
                    {"label": "API", "ok": False, "detail": "timeout"},
                ],
                "tailscale": {"ok": True, "state": "running", "peers": 3},
            }
        )

        self.assertIsInstance(gif, bytes)
        self.assertGreater(len(gif), 100)

    def test_calendar_panel_renders_bytes(self):
        gif = dashboard_renderer.render_calendar_panel(
            [{"summary": "Deep work block", "start": "2026-05-27T15:30:00-03:00"}]
        )

        self.assertIsInstance(gif, bytes)
        self.assertGreater(len(gif), 100)

    def test_compact_count_formats_large_tailscale_peer_counts(self):
        self.assertEqual(dashboard_renderer._compact_count(-1), "--")
        self.assertEqual(dashboard_renderer._compact_count(42), "42")
        self.assertEqual(dashboard_renderer._compact_count(1351), "1.4K")

    def test_openai_logo_spin_generates_multiple_frames(self):
        gif = self._render_test_logo({"OPENAI_LOGO_ANIMATION": "spin", "OPENAI_LOGO_SPIN_FRAMES": "8"})

        self.assertIsInstance(gif, bytes)
        self.assertGreater(len(gif), 100)
        self.assertEqual(self._gif_frame_count(gif), 8)

    def test_openai_logo_spin_on_wait_is_static_until_waiting(self):
        normal = self._render_test_logo({"OPENAI_LOGO_ANIMATION": "spin-on-wait", "OPENAI_LOGO_SPIN_FRAMES": "8"})
        waiting = self._render_test_logo(
            {"OPENAI_LOGO_ANIMATION": "spin-on-wait", "OPENAI_LOGO_SPIN_FRAMES": "8"},
            waiting=True,
        )

        self.assertEqual(self._gif_frame_count(normal), 1)
        self.assertEqual(self._gif_frame_count(waiting), 8)

    def _render_test_logo(self, env: dict[str, str], waiting: bool = False) -> bytes:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "logo.gif"
            img = Image.new("RGB", (64, 64), "#FFFFFF")
            for x in range(18, 46):
                for y in range(28, 36):
                    img.putpixel((x, y), (0, 0, 0))
            img.save(path, format="GIF")

            merged_env = {"OPENAI_LOGO_GIF_PATH": str(path)}
            merged_env.update(env)
            with patch.dict(
                "os.environ",
                merged_env,
            ):
                return dashboard_renderer.render_openai_logo_panel(waiting=waiting)

    def _gif_frame_count(self, gif: bytes) -> int:
        with TemporaryDirectory() as tmp:
            rendered = Path(tmp) / "rendered.gif"
            rendered.write_bytes(gif)
            result = Image.open(rendered)
            try:
                return result.n_frames
            finally:
                result.close()


if __name__ == "__main__":
    unittest.main()
