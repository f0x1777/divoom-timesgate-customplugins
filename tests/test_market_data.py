import os
import unittest
from unittest.mock import patch

import market_data


class MarketDataTests(unittest.TestCase):
    def test_parse_assets(self):
        assets = market_data._parse_assets("BTC:crypto:bitcoin,SPY:stooq:spy.us,MEP:dolarapi:bolsa")

        self.assertEqual(
            assets,
            [("BTC", "crypto", "bitcoin"), ("SPY", "stooq", "spy.us"), ("MEP", "dolarapi", "bolsa")],
        )

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

    def test_dolarapi_quote_uses_sale_price(self):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "compra": 1190,
                    "venta": 1210,
                    "casa": "bolsa",
                    "nombre": "Dólar Bolsa",
                    "moneda": "USD",
                    "fechaActualizacion": "2026-05-27T12:00:00.000Z",
                }

        with patch("requests.get", return_value=Response()):
            quote = market_data._dolarapi_quote("MEP", "bolsa")

        self.assertEqual(quote["label"], "MEP")
        self.assertEqual(quote["price"], 1210.0)
        self.assertEqual(quote["buy"], 1190.0)
        self.assertEqual(quote["source"], "dolarapi")


if __name__ == "__main__":
    unittest.main()
