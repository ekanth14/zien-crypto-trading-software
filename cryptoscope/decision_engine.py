"""
Zien Crypto — 0-100 Composite Quantitative Scoring, Tiering, and R:R Gatekeeper
"""

from typing import Any, Dict, List, Optional
try:
    from cryptoscope.quant_engine import (
        calculate_ema,
        calculate_wilder_rsi,
        calculate_wilder_atr,
        calculate_cvd_series,
        detect_order_blocks,
        detect_fair_value_gaps,
        classify_funding_oi_regime,
    )
except ImportError:
    from quant_engine import (
        calculate_ema,
        calculate_wilder_rsi,
        calculate_wilder_atr,
        calculate_cvd_series,
        detect_order_blocks,
        detect_fair_value_gaps,
        classify_funding_oi_regime,
    )


def score_crypto_asset(
    symbol: str,
    candles: List[Dict[str, Any]],
    funding_rate: float = 0.0001,
    oi_change_pct: float = 0.0,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Computes deterministic 0-100 quantitative score, institutional trade setup,
    target levels, stop loss, and R:R compliance gate.
    """
    if not candles or len(candles) < 20:
        c_price = float(candles[-1]["c"]) if candles else 0.0
        return {
            "symbol": symbol,
            "status": "failed",
            "score": 50,
            "composite_score": 50,
            "tier": "NEUTRAL",
            "tier_label": "NEUTRAL",
            "direction": "NEUTRAL",
            "action": "WAIT - INSUFFICIENT DATA",
            "reason": "Minimum 20 candles required for statistical validity.",
            "price": c_price,
            "entry": c_price,
            "stop_loss": c_price,
            "target_1": c_price,
            "target_2": c_price,
            "rr_ratio": 1.5,
            "atr": 0.0,
            "cvd": {"regime": "NEUTRAL", "latest_cvd": 0.0, "delta_ratio": 0.0},
            "oi_funding_regime": "BALANCED",
            "category_scores": {"trend": 50, "momentum": 50, "cvd": 50, "derivatives": 50, "structure": 50},
            "trade_signal": {
                "action": "WAIT",
                "direction": "NEUTRAL",
                "entry_price": c_price,
                "stop_loss": c_price,
                "target_1": c_price,
                "target_2": c_price,
                "rr_ratio": 1.5,
                "is_valid": False,
            },
            "metrics": {},
            "order_blocks": {},
            "fvgs": [],
        }
    
    cfg = config or {}
    closes = [float(c["c"]) for c in candles]
    current_price = closes[-1]
    
    # 1. Trend: EMAs
    fast_period = int(cfg.get("fast_ema_period", 9))
    slow_period = int(cfg.get("slow_ema_period", 21))
    ema_fast = calculate_ema(closes, fast_period)
    ema_slow = calculate_ema(closes, slow_period)
    fast_val, slow_val = ema_fast[-1], ema_slow[-1]
    
    # EMA Component (0 to 100)
    ema_spread_pct = ((fast_val - slow_val) / slow_val) * 100.0
    if fast_val >= slow_val and current_price >= fast_val:
        trend_score = min(100.0, 60.0 + ema_spread_pct * 10.0)
    elif fast_val >= slow_val and current_price < fast_val:
        trend_score = 55.0
    elif fast_val < slow_val and current_price > fast_val:
        trend_score = 45.0
    else:
        trend_score = max(0.0, 40.0 + ema_spread_pct * 10.0)
        
    # 2. Momentum: RSI
    rsi_period = int(cfg.get("rsi_period", 14))
    rsi = calculate_wilder_rsi(closes, rsi_period)
    # 50 is neutral, >50 bullish momentum up to 75 (above 80 overbought), <50 bearish
    if 50.0 <= rsi <= 70.0:
        rsi_score = 50.0 + (rsi - 50.0) * 2.0  # 50 to 90
    elif rsi > 70.0:
        rsi_score = max(50.0, 90.0 - (rsi - 70.0) * 2.0)  # overbought exhaustion decay
    elif 30.0 <= rsi < 50.0:
        rsi_score = 50.0 - (50.0 - rsi) * 2.0  # 10 to 50
    else:
        rsi_score = min(50.0, 10.0 + (30.0 - rsi) * 2.0)  # oversold bounce potential
        
    # 3. CVD & Volume Order Flow
    cvd_series, cvd_stats = calculate_cvd_series(candles)
    cvd_div = cvd_stats.get("divergence", "NONE")
    delta_ratio = cvd_stats.get("delta_ratio", 0.0)
    
    if cvd_div == "BULLISH_ABSORPTION":
        cvd_score = 85.0
    elif cvd_div == "BEARISH_EXHAUSTION":
        cvd_score = 15.0
    elif delta_ratio > 0.15:
        cvd_score = 75.0
    elif delta_ratio < -0.15:
        cvd_score = 25.0
    else:
        cvd_score = 50.0 + delta_ratio * 100.0
    cvd_score = max(0.0, min(100.0, cvd_score))
    
    # 4. Derivatives & Funding Skew
    p_change_pct = ((closes[-1] - closes[0]) / closes[0]) * 100.0
    deriv_regime = classify_funding_oi_regime(funding_rate, oi_change_pct, p_change_pct)
    
    deriv_score = 50.0
    if deriv_regime["regime"] == "LONG_BUILDUP":
        deriv_score = 75.0
    elif deriv_regime["regime"] == "SHORT_COVERING":
        deriv_score = 60.0
    elif deriv_regime["regime"] == "SHORT_BUILDUP":
        deriv_score = 25.0
    elif deriv_regime["regime"] == "LONG_LIQUIDATION":
        deriv_score = 30.0
        
    if deriv_regime["squeeze_risk"] == "HIGH_SHORT_SQUEEZE_RISK":
        deriv_score += 15.0  # explosive squeeze upside
    elif deriv_regime["squeeze_risk"] == "HIGH_LONG_SQUEEZE_RISK":
        deriv_score -= 15.0  # long flush risk
    deriv_score = max(0.0, min(100.0, deriv_score))
    
    # 5. Market Structure & Order Blocks
    obs = detect_order_blocks(candles)
    fvgs = detect_fair_value_gaps(candles)
    struct_score = 50.0
    
    bull_ob = obs.get("bullish_ob")
    bear_ob = obs.get("bearish_ob")
    if bull_ob and current_price >= bull_ob["low"]:
        dist_to_ob = abs(current_price - bull_ob["mid"]) / current_price
        if dist_to_ob <= 0.015:  # within 1.5% of bullish order block
            struct_score += 30.0
        elif current_price > bull_ob["high"]:
            struct_score += 15.0
    if bear_ob and current_price <= bear_ob["high"]:
        dist_to_bear = abs(current_price - bear_ob["mid"]) / current_price
        if dist_to_bear <= 0.015:
            struct_score -= 30.0
    struct_score = max(0.0, min(100.0, struct_score))
    
    # Composite Weighted Formula (Sum = 1.0)
    composite_score = (
        0.25 * trend_score +
        0.20 * rsi_score +
        0.25 * cvd_score +
        0.15 * deriv_score +
        0.15 * struct_score
    )
    final_score = int(round(max(0.0, min(100.0, composite_score))))
    
    # Volatility & Levels
    atr_period = int(cfg.get("atr_period", 14))
    atr = calculate_wilder_atr(candles, atr_period)
    min_rr = float(cfg.get("min_rr_ratio", 1.5))
    
    # Determine Trade Plan
    if final_score >= int(cfg.get("score_threshold", 65)):
        direction = "LONG"
        sl = round(current_price - (atr * 1.5), 4)
        risk = current_price - sl
        t1 = round(current_price + (risk * 1.5), 4)
        t2 = round(current_price + (risk * 2.5), 4)
        rr = round((t1 - current_price) / max(0.0001, risk), 2)
        
        tier = "TIER 1 (INSTITUTIONAL BUY)" if final_score >= 80 else "TIER 2 (BULLISH ACCUMULATION)"
        action = f"BUY / LONG ({tier})" if rr >= min_rr else "AVOID - POOR R:R"
    elif final_score <= 35:
        direction = "SHORT"
        sl = round(current_price + (atr * 1.5), 4)
        risk = sl - current_price
        t1 = round(current_price - (risk * 1.5), 4)
        t2 = round(current_price - (risk * 2.5), 4)
        rr = round((current_price - t1) / max(0.0001, risk), 2)
        
        tier = "TIER 5 (LIQUIDATION BREAKDOWN)" if final_score <= 20 else "TIER 4 (BEARISH DISTRIBUTION)"
        action = f"SELL / SHORT ({tier})" if rr >= min_rr else "AVOID - POOR R:R"
    else:
        direction = "NEUTRAL"
        tier = "TIER 3 (CHOP / CONSOLIDATION)"
        action = "MONITOR RANGE BREAKOUT"
        # In chop/consolidation, provide tactical bracket levels based on ATR
        sl = round(current_price - (atr * 1.5), 4)
        risk = current_price - sl
        t1 = round(current_price + (risk * 1.5), 4)
        t2 = round(current_price + (risk * 2.5), 4)
        rr = 1.50
        
    category_scores = {
        "trend": round(trend_score, 1),
        "momentum": round(rsi_score, 1),
        "cvd": round(cvd_score, 1),
        "derivatives": round(deriv_score, 1),
        "structure": round(struct_score, 1),
    }

    trade_signal = {
        "action": action,
        "direction": direction,
        "entry_price": current_price,
        "stop_loss": sl,
        "target_1": t1,
        "target_2": t2,
        "rr_ratio": rr,
        "is_valid": rr >= min_rr,
    }

    return {
        "symbol": symbol,
        "status": "ok",
        "price": current_price,
        "score": final_score,
        "composite_score": final_score,
        "tier": tier,
        "tier_label": tier,
        "direction": direction,
        "action": action,
        "rr_ratio": rr,
        "entry": current_price,
        "stop_loss": sl,
        "target_1": t1,
        "target_2": t2,
        "atr": round(atr, 4),
        "cvd": {
            "regime": cvd_div,
            "latest_cvd": cvd_stats.get("latest_cvd", 0.0),
            "delta_ratio": round(delta_ratio, 4),
        },
        "oi_funding_regime": deriv_regime["regime"],
        "category_scores": category_scores,
        "trade_signal": trade_signal,
        "metrics": {
            "rsi": round(rsi, 2),
            "atr": round(atr, 4),
            "ema_fast": round(fast_val, 4),
            "ema_slow": round(slow_val, 4),
            "cvd": cvd_stats.get("latest_cvd"),
            "cvd_divergence": cvd_div,
            "funding_rate": funding_rate,
            "oi_regime": deriv_regime["regime"],
            "squeeze_risk": deriv_regime["squeeze_risk"],
            "has_bullish_ob": bull_ob is not None,
            "has_bearish_ob": bear_ob is not None,
            "active_fvgs_count": len(fvgs),
        },
        "order_blocks": obs,
        "fvgs": fvgs,
    }
