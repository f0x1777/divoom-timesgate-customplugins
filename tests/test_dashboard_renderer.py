import unittest

import dashboard_renderer


class DashboardRendererTests(unittest.TestCase):
    def test_usage_values_are_rendered_as_available_capacity(self):
        self.assertEqual(dashboard_renderer._pct(dashboard_renderer._available_from_used(0.08)), "92%")
        self.assertEqual(dashboard_renderer._pct(dashboard_renderer._available_from_used(0.83)), "17%")


if __name__ == "__main__":
    unittest.main()
