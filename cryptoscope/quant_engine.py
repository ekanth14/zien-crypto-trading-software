"""
Zien Crypto — Quantitative Algorithms, SMC Order Blocks, CVD, and Microstructure Indicators
Pure Python standard library implementation with zero external dependencies.
"""

import math
from typing import Any, Dict, List, Optional, Tuple


def calculate_ema(values: List[float], period: int) -> List[float]:
    """Calculate Exponential Moving Average (EMA) with smoothing multiplier."""
    if not values or period <= 0:
        return []
    if len(values) < period:
        return [float(sum(values) / len(values))] * len(values)
    
    k = 2.0 / (period + 1)
    ema = [float(sum(values[:period]) / period)]
    for val in values[period:]:
        ema.append(float(val * k + ema[-1] * (1.0 - k)))
    
    # Pad head so output length matches input
    padding = [ema[0]] * (period - 1)
    return padding + ema


def calculate_wilder_rsi(closes: List[float], period: int = 14) -> float:
    """
    Wilder Smoothed Relative Strength Index (RSI).
    Matches mathematical standard reference (0 to 100).
    """
    if len(closes) < period + 1:
        return 50.0
    
    gains = []
    losses = []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains.append(diff)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(diff))
    
    # Initial Wilder average
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Smooth through remainder
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0 else 50.0
    
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def calculate_wilder_atr(candles: List[Dict[str, Any]], period: int = 14) -> float:
    """
    Wilder Smoothed Average True Range (ATR).
    Expects candles with 'h', 'l', 'c'.
    """
    if len(candles) < 2:
        return 0.0
    
    trs = []
    for i in range(len(candles)):
        h, l = candles[i]["h"], candles[i]["l"]
        if i == 0:
            trs.append(h - l)
        else:
            prev_c = candles[i - 1]["c"]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            trs.append(tr)
    
    if len(trs) < period:
        return round(sum(trs) / len(trs), 4)
    
    atr = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        atr = (atr * (period - 1) + trs[i]) / period
    
    return round(atr, 4)


def calculate_cvd_series(candles: List[Dict[str, Any]]) -> Tuple[List[float], Dict[str, Any]]:
    """
    Calculate Cumulative Volume Delta (CVD) from candles.
    Uses taker_buy_vol (if available) or tick/candle directional volume proxy:
    Delta = 2 * taker_buy - total_volume (if taker given),
    else price position relative to candle range: ((Close - Low) - (High - Close)) / Range * Volume.
    """
    cvd = 0.0
    cvd_series = []
    deltas = []
    
    for c in candles:
        vol = float(c.get("v", 0.0))
        tbv = c.get("taker_buy_vol")
        if tbv is not None:
            # Exact Binance execution delta
            delta = float(tbv) * 2.0 - vol
        else:
            # High-precision intra-candle volume proxy
            rng = c["h"] - c["l"]
            if rng > 0:
                pos = (c["c"] - c["l"]) / rng
                delta = (2.0 * pos - 1.0) * vol
            else:
                delta = 0.0
        
        deltas.append(delta)
        cvd += delta
        cvd_series.append(round(cvd, 2))
    
    # Detect CVD Divergence across last 15 bars
    divergence = "NONE"
    if len(candles) >= 15:
        p_start, p_end = candles[-15]["c"], candles[-1]["c"]
        c_start, c_end = cvd_series[-15], cvd_series[-1]
        
        # Bullish Absorption: Price falling or flat, but CVD aggressively rising
        if p_end < p_start and c_end > c_start:
            divergence = "BULLISH_ABSORPTION"
        # Bearish Exhaustion: Price rising or flat, but CVD aggressively falling
        elif p_end > p_start and c_end < c_start:
            divergence = "BEARISH_EXHAUSTION"
    
    stats = {
        "latest_cvd": cvd_series[-1] if cvd_series else 0.0,
        "latest_delta": round(deltas[-1], 2) if deltas else 0.0,
        "divergence": divergence,
        "delta_ratio": round((deltas[-1] / (candles[-1]["v"] or 1.0)), 3) if candles and candles[-1].get("v") else 0.0,
    }
    return cvd_series, stats


def detect_fair_value_gaps(candles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Detect ICT Fair Value Gaps (FVG) across recent candles.
    Bullish FVG: Low of candle[i] > High of candle[i-2] (gap left unvisited)
    Bearish FVG: High of candle[i] < Low of candle[i-2]
    """
    fvgs = []
    if len(candles) < 3:
        return fvgs
    
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i - 2], candles[i - 1], candles[i]
        
        # Bullish Imbalance
        if c3["l"] > c1["h"]:
            fvgs.append({
                "type": "BULLISH_FVG",
                "top": c3["l"],
                "bottom": c1["h"],
                "midpoint": round((c3["l"] + c1["h"]) / 2.0, 4),
                "timestamp": c2["t"],
                "bar_index": i - 1,
            })
        # Bearish Imbalance
        elif c3["h"] < c1["l"]:
            fvgs.append({
                "type": "BEARISH_FVG",
                "top": c1["l"],
                "bottom": c3["h"],
                "midpoint": round((c1["l"] + c3["h"]) / 2.0, 4),
                "timestamp": c2["t"],
                "bar_index": i - 1,
            })
    
    # Return last 3 active FVGs
    return fvgs[-3:]


def detect_order_blocks(candles: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Algorithmic Order Block (OB) Identification:
    1. Identify displacement impulse candles with volume > 1.4x 20-period volume average.
    2. Identify last opposing candle prior to impulse.
    3. Determine active Bullish and Bearish Order Block zones.
    """
    if len(candles) < 20:
        return {"bullish_ob": None, "bearish_ob": None}
    
    vols = [float(c.get("v", 0.0)) for c in candles]
    avg_vol = sum(vols[-20:]) / 20.0
    
    bullish_ob = None
    bearish_ob = None
    
    for i in range(1, len(candles) - 1):
        c_prev = candles[i - 1]
        c_curr = candles[i]
        c_vol = float(c_curr.get("v", 0.0))
        
        # Bullish displacement: Strong green candle breaking above previous high with high volume
        if c_curr["c"] > c_curr["o"] and c_vol > avg_vol * 1.3:
            if c_prev["c"] < c_prev["o"]:  # Last red candle
                bullish_ob = {
                    "high": c_prev["h"],
                    "low": c_prev["l"],
                    "mid": round((c_prev["h"] + c_prev["l"]) / 2.0, 4),
                    "timestamp": c_prev["t"],
                }
        
        # Bearish displacement: Strong red candle breaking below previous low with high volume
        elif c_curr["c"] < c_curr["o"] and c_vol > avg_vol * 1.3:
            if c_prev["c"] > c_prev["o"]:  # Last green candle
                bearish_ob = {
                    "high": c_prev["h"],
                    "low": c_prev["l"],
                    "mid": round((c_prev["h"] + c_prev["l"]) / 2.0, 4),
                    "timestamp": c_prev["t"],
                }
                
    return {"bullish_ob": bullish_ob, "bearish_ob": bearish_ob}


def classify_funding_oi_regime(funding_rate: float, oi_change_pct: float, price_change_pct: float) -> Dict[str, Any]:
    """
    4-Quadrant Derivatives Momentum & Liquidation Risk Classifier:
    - Quadrant 1: Price Up + OI Up -> Long Build-up (Strong momentum)
    - Quadrant 2: Price Down + OI Up -> Short Build-up (Aggressive selling)
    - Quadrant 3: Price Up + OI Down -> Short Covering (Exhaustion warning)
    - Quadrant 4: Price Down + OI Down -> Long Unwinding / Liquidation Cascade
    """
    if price_change_pct >= 0 and oi_change_pct >= 0:
        regime = "LONG_BUILDUP"
        sentiment = "BULLISH_CONTINUATION"
    elif price_change_pct < 0 and oi_change_pct >= 0:
        regime = "SHORT_BUILDUP"
        sentiment = "BEARISH_EXPANSION"
    elif price_change_pct >= 0 and oi_change_pct < 0:
        regime = "SHORT_COVERING"
        sentiment = "EXHAUSTION_WARNING"
    else:
        regime = "LONG_LIQUIDATION"
        sentiment = "CAPITULATION_FLUSH"
    
    # Squeeze Risk Evaluation
    squeeze_risk = "NORMAL"
    if funding_rate >= 0.0005:  # > 0.05% per 8h
        squeeze_risk = "HIGH_LONG_SQUEEZE_RISK"
    elif funding_rate <= -0.0003:  # < -0.03% per 8h
        squeeze_risk = "HIGH_SHORT_SQUEEZE_RISK"
        
    return {
        "regime": regime,
        "sentiment": sentiment,
        "squeeze_risk": squeeze_risk,
        "funding_rate": funding_rate,
        "funding_rate_annualized": round(funding_rate * 3 * 365 * 100, 2),
        "oi_change_pct": oi_change_pct,
    }
