import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import resource_monitor


class ResourceMonitorTests(unittest.TestCase):
    def test_network_mbps_uses_sample_delta(self):
        samples = [
            {"timestamp": 100.0, "ibytes": 1_000_000, "obytes": 2_000_000},
            {"timestamp": 101.0, "ibytes": 2_000_000, "obytes": 2_500_000},
        ]

        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(resource_monitor, "NETWORK_SAMPLE_PATH", Path(tmp) / "network.json"), \
             patch("resource_monitor._network_bytes", side_effect=samples):
            first = resource_monitor._network_mbps()
            second = resource_monitor._network_mbps()

        self.assertEqual(first, (-1.0, -1.0))
        self.assertEqual(second, (8.0, 4.0))


if __name__ == "__main__":
    unittest.main()
