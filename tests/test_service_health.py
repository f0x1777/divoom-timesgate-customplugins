import unittest
from unittest.mock import Mock, patch

import service_health


class ServiceHealthTests(unittest.TestCase):
    def test_parse_checks_allows_urls_with_colons(self):
        checks = service_health._parse_checks("WEB:http:http://localhost:3000,DB:tcp:localhost:5432")

        self.assertEqual(
            checks,
            [
                ("WEB", "http", "http://localhost:3000"),
                ("DB", "tcp", "localhost:5432"),
            ],
        )

    def test_http_check_uses_status_code(self):
        response = Mock(status_code=204)

        with patch("requests.get", return_value=response):
            result = service_health.check_service("API", "http", "http://localhost:8000/health")

        self.assertTrue(result["ok"])
        self.assertEqual(result["detail"], "204")

    def test_tailscale_missing_is_reported(self):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = service_health.tailscale_status()

        self.assertTrue(result["enabled"])
        self.assertFalse(result["ok"])
        self.assertEqual(result["state"], "missing")


if __name__ == "__main__":
    unittest.main()
