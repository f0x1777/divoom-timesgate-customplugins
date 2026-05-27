import unittest

import dashboard_renderer


class DashboardRendererTests(unittest.TestCase):
    def test_usage_values_are_rendered_as_available_capacity(self):
        self.assertEqual(dashboard_renderer._pct(dashboard_renderer._available_from_used(0.08)), "92%")
        self.assertEqual(dashboard_renderer._pct(dashboard_renderer._available_from_used(0.83)), "17%")

    def test_ops_panel_renders_bytes(self):
        gif = dashboard_renderer.render_ops_panel(
            [{"label": "BTC", "price": 123456, "change_pct": 1.2}],
            {"cpu": 10, "memory": 20, "disk": 30, "battery": 80},
            [{"summary": "Focus", "start": "2026-05-26T22:00:00-03:00"}],
        )

        self.assertIsInstance(gif, bytes)
        self.assertGreater(len(gif), 100)


if __name__ == "__main__":
    unittest.main()
