import os
import unittest
from unittest.mock import patch

import market_data


class MarketDataTests(unittest.TestCase):
    def test_parse_assets(self):
        assets = market_data._parse_assets("BTC:crypto:bitcoin,SPY:stooq:spy.us")

        self.assertEqual(assets, [("BTC", "crypto", "bitcoin"), ("SPY", "stooq", "spy.us")])

    def test_crypto_quotes(self):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {"bitcoin": {"usd": 12345, "usd_24h_change": 1.5}}

        with patch("requests.get", return_value=Response()):
            quotes = market_data._crypto_quotes([("BTC", "crypto", "bitcoin")])

        self.assertEqual(quotes[0]["label"], "BTC")
        self.assertEqual(quotes[0]["price"], 12345.0)
        self.assertEqual(quotes[0]["change_pct"], 1.5)


if __name__ == "__main__":
    unittest.main()
