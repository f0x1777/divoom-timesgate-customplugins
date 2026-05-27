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

    def test_ops_panel_renders_bytes(self):
        gif = dashboard_renderer.render_ops_panel(
            [{"label": "BTC", "price": 123456, "change_pct": 1.2}],
            {"cpu": 10, "memory": 20, "disk": 30, "battery": 80},
            [{"summary": "Focus", "start": "2026-05-26T22:00:00-03:00"}],
        )

        self.assertIsInstance(gif, bytes)
        self.assertGreater(len(gif), 100)

    def test_openai_logo_spin_generates_multiple_frames(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "logo.gif"
            img = Image.new("RGB", (64, 64), "#FFFFFF")
            for x in range(18, 46):
                for y in range(28, 36):
                    img.putpixel((x, y), (0, 0, 0))
            img.save(path, format="GIF")

            with patch.dict(
                "os.environ",
                {
                    "OPENAI_LOGO_GIF_PATH": str(path),
                    "OPENAI_LOGO_ANIMATION": "spin",
                    "OPENAI_LOGO_SPIN_FRAMES": "8",
                },
            ):
                gif = dashboard_renderer.render_openai_logo_panel()

        self.assertIsInstance(gif, bytes)
        self.assertGreater(len(gif), 100)
        with TemporaryDirectory() as tmp:
            rendered = Path(tmp) / "rendered.gif"
            rendered.write_bytes(gif)
            result = Image.open(rendered)
            try:
                self.assertEqual(result.n_frames, 8)
            finally:
                result.close()


if __name__ == "__main__":
    unittest.main()
