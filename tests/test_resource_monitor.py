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

    def test_get_resources_buckets_noisy_values(self):
        with patch.dict("os.environ", {"RESOURCE_PERCENT_BUCKET": "5", "RESOURCE_NETWORK_BUCKET_MBPS": "0.25"}), \
             patch("resource_monitor._cpu_percent", return_value=12.1), \
             patch("resource_monitor._memory_percent", return_value=63.4), \
             patch("resource_monitor._disk_percent", return_value=71.8), \
             patch("resource_monitor._battery_percent", return_value=88.0), \
             patch("resource_monitor._network_mbps", return_value=(1.12, 0.11)):
            resources = resource_monitor.get_resources()

        self.assertEqual(resources["cpu"], 10)
        self.assertEqual(resources["memory"], 65)
        self.assertEqual(resources["disk"], 70)
        self.assertEqual(resources["net_in_mbps"], 1.0)
        self.assertEqual(resources["net_out_mbps"], 0.0)


if __name__ == "__main__":
    unittest.main()
