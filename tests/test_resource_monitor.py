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
             patch("resource_monitor._cpu_temperature_celsius", return_value=52.8), \
             patch("resource_monitor._battery_percent", return_value=88.0), \
             patch("resource_monitor._network_mbps", return_value=(1.12, 0.11)):
            resources = resource_monitor.get_resources()

        self.assertEqual(resources["cpu"], 10)
        self.assertEqual(resources["memory"], 65)
        self.assertEqual(resources["disk"], 70)
        self.assertEqual(resources["cpu_temp_c"], 52.8)
        self.assertEqual(resources["net_in_mbps"], 1.0)
        self.assertEqual(resources["net_out_mbps"], 0.0)

    def test_parse_temperature_celsius(self):
        self.assertEqual(resource_monitor._parse_temperature_celsius("53.4 C"), 53.4)
        self.assertEqual(resource_monitor._parse_temperature_celsius("128 F"), 53.3)
        self.assertEqual(
            resource_monitor._parse_temperature_celsius('{"temp":{"cpu_temp_avg":53.31679916381836}}'),
            53.3,
        )
        self.assertEqual(resource_monitor._parse_temperature_celsius("no sensor"), -1.0)

    def test_cpu_temperature_rejects_implausible_sensor_values(self):
        with patch("resource_monitor._run", return_value="0.0 C"):
            self.assertEqual(resource_monitor._cpu_temperature_celsius(), -1.0)


if __name__ == "__main__":
    unittest.main()
