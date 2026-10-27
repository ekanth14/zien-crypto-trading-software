"""
Zien Crypto — 24/7 Continuous Session & Rolling Market Snapshot Engine
Crypto operates 24/7/365. Sessions track rolling 24-hour windows and 8-hour funding epochs.
"""

import concurrent.futures
from datetime import datetime, timezone
import time
from typing import Any, Dict, List, Optional
try:
    from cryptoscope.crypto_market import CRYPTO_CATALOGUE, DEFAULT_CRYPTO_CONFIG
    from cryptoscope.binance_feed import get_binance_feed
    from cryptoscope.quant_engine import calculate_cvd_series
    from cryptoscope.decision_engine import score_crypto_asset
except ImportError:
    from crypto_market import CRYPTO_CATALOGUE, DEFAULT_CRYPTO_CONFIG
    from binance_feed import get_binance_feed
    from quant_engine import calculate_cvd_series
    from decision_engine import score_crypto_asset

_snapshot_cache: Dict[int, Dict[str, Any]] = {}
_snapshot_time: Dict[int, float] = {}


def get_crypto_session_info() -> Dict[str, Any]:
    """Returns current continuous 24/7 session metadata and next funding epoch."""
    now_utc = datetime.now(timezone.utc)
    current_epoch_hour = (now_utc.hour // 8) * 8
    next_epoch_hour = (current_epoch_hour + 8) % 24
    
    return {
        "status": "LIVE_24_7",
        "market": "Global Crypto Spot & Perpetuals",
        "timestamp": now_utc.isoformat(),
        "funding_epoch_utc": f"{current_epoch_hour:02d}:00:00",
        "next_funding_utc": f"{next_epoch_hour:02d}:00:00",
        "is_open": True,
    }


def build_crypto_market_snapshot(
    timeframe: int = 5,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Builds the complete multi-asset quantitative snapshot across all monitored crypto pairs.
    Optimized with parallel execution and short-lived caching.
    """
    now = time.time()
    if timeframe in _snapshot_cache and (now - _snapshot_time.get(timeframe, 0)) < 2.5:
        return _snapshot_cache[timeframe]

    cfg = config or DEFAULT_CRYPTO_CONFIG
    monitored = cfg.get("monitored_symbols", list(CRYPTO_CATALOGUE.keys())[:15])
    feed = get_binance_feed()
    
    tickers = feed.fetch_24h_tickers()
    interval_str = f"{timeframe}m" if timeframe < 60 else "1h"
    
    stocks_data = {}
    scored_list = []
    bullish_count = 0
    bearish_count = 0
    trajectories = []

    def _fetch_asset(symbol: str):
        meta = CRYPTO_CATALOGUE.get(symbol, {"name": symbol, "sector": "Crypto", "precision": 2})
        candles = feed.fetch_klines(symbol, interval=interval_str, limit=50)
        if not candles:
            return None
        ticker = tickers.get(symbol, {})
        price = ticker.get("price", candles[-1]["c"] if candles else 0.0)
        p_change = ticker.get("change_pct", 0.0)
        funding = feed.fetch_funding_rate(symbol)
        scored = score_crypto_asset(symbol, candles, funding_rate=funding, config=cfg)
        base_c = candles[0]["c"]
        points = [round(((c["c"] - base_c) / base_c) * 100.0, 2) for c in candles]
        return {
            "symbol": symbol,
            "meta": meta,
            "ticker": ticker,
            "price": price,
            "p_change": p_change,
            "funding": funding,
            "scored": scored,
            "points": points,
        }

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(_fetch_asset, monitored))

    for res in results:
        if not res:
            continue
        symbol = res["symbol"]
        meta = res["meta"]
        ticker = res["ticker"]
        price = res["price"]
        p_change = res["p_change"]
        funding = res["funding"]
        scored = res["scored"]
        points = res["points"]

        scored_list.append(scored)
        if scored["score"] >= 60:
            bullish_count += 1
        elif scored["score"] <= 40:
            bearish_count += 1

        trajectories.append({"symbol": symbol, "points": points})
        stocks_data[symbol] = {
            "symbol": symbol,
            "name": meta["name"],
            "sector": meta["sector"],
            "price": price,
            "change": round(p_change, 2),
            "volume_24h": ticker.get("volume", 0.0),
            "quote_volume_24h": ticker.get("quote_volume", 0.0),
            "high_24h": ticker.get("high", 0.0),
            "low_24h": ticker.get("low", 0.0),
            "score": scored["score"],
            "composite_score": scored["score"],
            "tier": scored["tier"],
            "tier_label": scored["tier"],
            "regime": scored.get("metrics", {}).get("oi_regime", "BALANCED"),
            "direction": scored["direction"],
            "action": scored["action"],
            "rr_ratio": scored["rr_ratio"],
            "entry": scored["entry"],
            "stop_loss": scored["stop_loss"],
            "target_1": scored["target_1"],
            "target_2": scored["target_2"],
            "atr": scored.get("atr", 0.0),
            "cvd": scored.get("cvd", {}),
            "category_scores": scored.get("category_scores", {}),
            "trade_signal": scored.get("trade_signal", {}),
            "metrics": scored["metrics"],
            "funding_rate": funding,
        }

    # Sector averages
    sectors: Dict[str, List[float]] = {}
    for sym, item in stocks_data.items():
        sec = item["sector"]
        sectors.setdefault(sec, []).append(item["change"])
    sectors_avg = {k: round(sum(v) / len(v), 2) for k, v in sectors.items()}

    daily_ranking = sorted(scored_list, key=lambda x: x["score"], reverse=True)

    snapshot = {
        "as_of": datetime.now(timezone.utc).strftime("%H:%M:%S UTC"),
        "session_state": "LIVE",
        "data_mode": "LIVE_BINANCE",
        "timeframe": timeframe,
        "stocks": stocks_data,
        "daily_ranking": daily_ranking,
        "sectors": sectors_avg,
        "trajectories": trajectories,
        "counts": {
            "bullish": bullish_count,
            "bearish": bearish_count,
            "neutral": len(stocks_data) - bullish_count - bearish_count,
            "total": len(stocks_data),
        },
    }
    _snapshot_cache[timeframe] = snapshot
    _snapshot_time[timeframe] = now
    return snapshot
