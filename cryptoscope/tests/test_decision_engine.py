"""
Zien Crypto - Unit Tests for Decision Engine & R:R Gatekeeper
"""

import unittest
from cryptoscope.decision_engine import score_crypto_asset


def make_candle(t: int, o: float, h: float, l: float, c: float, v: float = 1000.0, taker_buy_vol: float = 500.0):
    return {
        "t": t,
        "o": o,
        "h": h,
        "l": l,
        "c": c,
        "v": v,
        "taker_buy_vol": taker_buy_vol,
    }


class TestDecisionEngine(unittest.TestCase):

    def test_insufficient_candles(self):
        candles = [make_candle(i, 100, 101, 99, 100) for i in range(10)]
        res = score_crypto_asset("BTCUSDT", candles)
        self.assertEqual(res["status"], "failed")
        self.assertEqual(res["tier"], "NEUTRAL")
        self.assertIn("INSUFFICIENT", res["action"])

    def test_bullish_market_scoring(self):
        # Monotonically rising candles with aggressive taker buy volume
        candles = []
        for i in range(35):
            p = 100.0 + i * 2.0
            candles.append(make_candle(i, p, p + 2.0, p - 1.0, p + 1.8, v=2000.0, taker_buy_vol=1600.0))

        res = score_crypto_asset("BTCUSDT", candles, funding_rate=0.0001, oi_change_pct=5.0)
        self.assertEqual(res["status"], "ok")
        self.assertGreaterEqual(res["score"], 65)
        self.assertEqual(res["direction"], "LONG")
        self.assertTrue(res["action"].startswith("BUY / LONG"))
        self.assertGreaterEqual(res["rr_ratio"], 1.5)
        self.assertIsNotNone(res["entry"])
        self.assertIsNotNone(res["stop_loss"])
        self.assertIsNotNone(res["target_1"])
        self.assertIsNotNone(res["target_2"])
        self.assertLess(res["stop_loss"], res["entry"])
        self.assertGreater(res["target_1"], res["entry"])

    def test_bearish_market_scoring(self):
        # Monotonically falling candles with heavy selling
        candles = []
        for i in range(35):
            p = 300.0 - i * 2.0
            candles.append(make_candle(i, p, p + 1.0, p - 2.5, p - 2.0, v=2000.0, taker_buy_vol=400.0))

        res = score_crypto_asset("ETHUSDT", candles, funding_rate=-0.0001, oi_change_pct=5.0)
        self.assertEqual(res["status"], "ok")
        self.assertLessEqual(res["score"], 35)
        self.assertEqual(res["direction"], "SHORT")
        self.assertTrue(res["action"].startswith("SELL / SHORT"))
        self.assertGreaterEqual(res["rr_ratio"], 1.5)
        self.assertIsNotNone(res["entry"])
        self.assertIsNotNone(res["stop_loss"])
        self.assertIsNotNone(res["target_1"])
        self.assertGreater(res["stop_loss"], res["entry"])
        self.assertLess(res["target_1"], res["entry"])

    def test_rr_gatekeeper_enforcement(self):
        # When required min_rr_ratio is set unrealistically high (e.g., 5.0)
        candles = [make_candle(i, 100.0 + i, 102.0 + i, 99.0 + i, 101.5 + i, v=2000.0, taker_buy_vol=1500.0) for i in range(35)]
        res = score_crypto_asset("SOLUSDT", candles, config={"min_rr_ratio": 5.0})
        if res["score"] >= 65:
            self.assertEqual(res["action"], "AVOID - POOR R:R")


if __name__ == "__main__":
    unittest.main()
