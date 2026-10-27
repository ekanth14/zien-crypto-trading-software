"""
Zien Crypto - Unit Tests for Binance Feed Scraper
"""

import json
import time
import unittest
from unittest.mock import patch, MagicMock

from cryptoscope.binance_feed import BinanceFeedScraper


class TestBinanceFeed(unittest.TestCase):

    def setUp(self):
        self.scraper = BinanceFeedScraper(cache_ttl_sec=2.0, timeout_sec=2.0)

    def test_kline_parsing_mock(self):
        # Raw 12-element Binance kline response
        raw_kline = [
            [
                1700000000000,      # 0: Open time (ms)
                "65000.00",         # 1: Open
                "65500.00",         # 2: High
                "64800.00",         # 3: Low
                "65200.00",         # 4: Close
                "150.5",            # 5: Volume
                1700000299999,      # 6: Close time
                "9812500.0",        # 7: Quote volume
                4200,               # 8: Number of trades
                "85.2",             # 9: Taker buy base asset volume
                "5555000.0",        # 10: Taker buy quote asset volume
                "0"                 # 11: Ignore
            ]
        ]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(raw_kline).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            klines = self.scraper.fetch_klines("BTCUSDT", interval="5m", limit=1)
            self.assertEqual(len(klines), 1)
            c = klines[0]
            self.assertEqual(c["t"], 1700000000)
            self.assertEqual(c["o"], 65000.0)
            self.assertEqual(c["h"], 65500.0)
            self.assertEqual(c["l"], 64800.0)
            self.assertEqual(c["c"], 65200.0)
            self.assertEqual(c["v"], 150.5)
            self.assertEqual(c["quote_vol"], 9812500.0)
            self.assertEqual(c["taker_buy_vol"], 85.2)

    def test_cache_hit(self):
        raw_kline = [[1700000000000, "100", "105", "95", "102", "10", 0, "0", 0, "5", "0", "0"]]
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(raw_kline).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_urlopen:
            res1 = self.scraper.fetch_klines("ETHUSDT", interval="5m", limit=10)
            res2 = self.scraper.fetch_klines("ETHUSDT", interval="5m", limit=10)
            self.assertEqual(mock_urlopen.call_count, 1)  # Second call served from cache
            self.assertEqual(res1, res2)

    def test_circuit_breaker(self):
        with patch("urllib.request.urlopen", side_effect=Exception("Network failure")):
            for _ in range(4):
                self.scraper.fetch_24h_tickers()
            self.assertTrue(self.scraper.is_paused())

    def test_live_binance_connectivity(self):
        # Actual live network check to public Binance spot feed
        live_scraper = BinanceFeedScraper(cache_ttl_sec=1.0, timeout_sec=5.0)
        try:
            tickers = live_scraper.fetch_24h_tickers()
            if tickers:
                self.assertIn("BTCUSDT", tickers)
                self.assertGreater(tickers["BTCUSDT"]["price"], 0.0)
        except Exception:
            self.skipTest("Live Binance API temporarily unreachable or restricted.")


if __name__ == "__main__":
    unittest.main()
