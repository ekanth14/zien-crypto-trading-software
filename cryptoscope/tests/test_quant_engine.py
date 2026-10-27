"""
Zien Crypto - Unit Tests for Quantitative Engine
Covers EMA, Wilder RSI, Wilder ATR, CVD, ICT Order Blocks, FVGs, and OI regimes.
"""

import unittest
from typing import List, Dict, Any

from cryptoscope.quant_engine import (
    calculate_ema,
    calculate_wilder_rsi,
    calculate_wilder_atr,
    calculate_cvd_series,
    detect_fair_value_gaps,
    detect_order_blocks,
    classify_funding_oi_regime,
)


def make_candle(t: int, o: float, h: float, l: float, c: float, v: float = 1000.0, taker_buy_vol: float = 500.0) -> Dict[str, Any]:
    return {
        "t": t,
        "o": o,
        "h": h,
        "l": l,
        "c": c,
        "v": v,
        "taker_buy_vol": taker_buy_vol,
    }


class TestQuantEngine(unittest.TestCase):

    def test_ema_constant_values(self):
        prices = [100.0] * 30
        ema = calculate_ema(prices, period=10)
        self.assertEqual(len(ema), len(prices))
        self.assertAlmostEqual(ema[-1], 100.0, places=4)

    def test_ema_rising_values(self):
        prices = [100.0 + i for i in range(50)]
        ema = calculate_ema(prices, period=9)
        self.assertEqual(len(ema), len(prices))
        self.assertLess(ema[-1], prices[-1])
        self.assertGreater(ema[-1], ema[-2])

    def test_wilder_rsi_bounds(self):
        # Monotonically increasing prices -> RSI should be high
        rising = [100.0 + i * 2.0 for i in range(30)]
        rsi_val = calculate_wilder_rsi(rising, period=14)
        self.assertGreater(rsi_val, 80.0)
        self.assertLessEqual(rsi_val, 100.0)

        # Monotonically falling prices -> RSI should be low
        falling = [200.0 - i * 2.0 for i in range(30)]
        rsi_down = calculate_wilder_rsi(falling, period=14)
        self.assertLess(rsi_down, 20.0)
        self.assertGreaterEqual(rsi_down, 0.0)

    def test_wilder_atr_volatility(self):
        # Low volatility candles
        low_vol_candles = [make_candle(i, 100.0, 101.0, 99.0, 100.0) for i in range(30)]
        atr_low = calculate_wilder_atr(low_vol_candles, period=14)
        self.assertAlmostEqual(atr_low, 2.0, places=1)

        # High volatility candles
        high_vol_candles = [make_candle(i, 100.0, 120.0, 80.0, 100.0) for i in range(30)]
        atr_high = calculate_wilder_atr(high_vol_candles, period=14)
        self.assertGreater(atr_high, atr_low)

    def test_cvd_calculation(self):
        candles = [
            make_candle(1, 100, 105, 95, 102, v=1000, taker_buy_vol=700),  # delta = +400
            make_candle(2, 102, 106, 98, 104, v=1000, taker_buy_vol=800),  # delta = +600
            make_candle(3, 104, 108, 100, 101, v=1000, taker_buy_vol=200), # delta = -600
        ]
        cvd_series, stats = calculate_cvd_series(candles)
        self.assertEqual(len(cvd_series), 3)
        self.assertEqual(cvd_series[0], 400.0)
        self.assertEqual(cvd_series[1], 1000.0)
        self.assertEqual(cvd_series[2], 400.0)
        self.assertEqual(stats["latest_cvd"], 400.0)
        self.assertEqual(stats["latest_delta"], -600.0)

    def test_fvg_detection(self):
        # Bullish FVG: Low of candle 3 > High of candle 1
        candles = [
            make_candle(1, 100, 102, 99, 101),
            make_candle(2, 101, 115, 101, 114),
            make_candle(3, 114, 118, 108, 117), # Low is 108 > High 102
        ]
        fvgs = detect_fair_value_gaps(candles)
        self.assertTrue(len(fvgs) >= 1)
        self.assertEqual(fvgs[0]["type"], "BULLISH_FVG")
        self.assertEqual(fvgs[0]["bottom"], 102)
        self.assertEqual(fvgs[0]["top"], 108)

    def test_order_block_detection(self):
        # Create at least 20 baseline candles so volume average exists
        candles = [make_candle(i, 100, 102, 98, 100, v=100) for i in range(20)]
        # Add last red candle followed by strong green displacement candle with high volume
        candles.append(make_candle(21, 100, 101, 98, 99, v=100)) # Down candle
        candles.append(make_candle(22, 99, 115, 99, 114, v=500)) # Strong bullish displacement (500 > 1.3 * 100)
        candles.append(make_candle(23, 114, 116, 113, 115, v=100))

        obs = detect_order_blocks(candles)
        self.assertIsNotNone(obs["bullish_ob"])
        self.assertEqual(obs["bullish_ob"]["high"], 101)
        self.assertEqual(obs["bullish_ob"]["low"], 98)

    def test_oi_funding_regimes(self):
        r1 = classify_funding_oi_regime(funding_rate=0.0001, oi_change_pct=5.0, price_change_pct=2.5)
        self.assertEqual(r1["regime"], "LONG_BUILDUP")

        r2 = classify_funding_oi_regime(funding_rate=0.0001, oi_change_pct=5.0, price_change_pct=-2.5)
        self.assertEqual(r2["regime"], "SHORT_BUILDUP")

        r3 = classify_funding_oi_regime(funding_rate=0.0001, oi_change_pct=-5.0, price_change_pct=-2.5)
        self.assertEqual(r3["regime"], "LONG_LIQUIDATION")

        r4 = classify_funding_oi_regime(funding_rate=0.0001, oi_change_pct=-5.0, price_change_pct=2.5)
        self.assertEqual(r4["regime"], "SHORT_COVERING")


if __name__ == "__main__":
    unittest.main()
