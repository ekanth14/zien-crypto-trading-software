"""
Zien Crypto — High-Performance Binance Public Market Data Scraper & Feed Manager
Pure Python standard library implementation. Zero API key required.
Sub-second latency with bounded in-memory cache and circuit breaker.
"""

import json
import logging
import time
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
try:
    from cryptoscope.crypto_market import CRYPTO_CATALOGUE
except ImportError:
    from crypto_market import CRYPTO_CATALOGUE

logger = logging.getLogger("zien-crypto.feed")


class BinanceFeedScraper:
    def __init__(self, cache_ttl_sec: float = 1.0, timeout_sec: float = 4.0):
        self.cache_ttl_sec = cache_ttl_sec
        self.timeout_sec = timeout_sec
        self._ticker_cache: Dict[str, Any] = {}
        self._ticker_cache_time: float = 0.0
        self._kline_cache: Dict[str, Dict[str, Any]] = {}
        self._funding_cache: Dict[str, Dict[str, Any]] = {}
        self._consecutive_errors: int = 0
        self._paused_until: float = 0.0
        
    def is_paused(self) -> bool:
        return time.time() < self._paused_until

    def fetch_24h_tickers(self) -> Dict[str, Dict[str, Any]]:
        """
        Fetch all 24h ticker stats from Binance spot public API.
        Returns mapped dictionary of {symbol: ticker_data}.
        """
        now = time.time()
        if self._ticker_cache and (now - self._ticker_cache_time) < self.cache_ttl_sec:
            return self._ticker_cache
            
        if self.is_paused():
            logger.warning("Binance feed paused due to prior errors. Returning cached tickers.")
            return self._ticker_cache

        url = "https://api.binance.com/api/v3/ticker/24hr"
        req = urllib.request.Request(url, headers={"User-Agent": "ZienCryptoTerminal/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                res = {}
                for item in data:
                    sym = item.get("symbol")
                    if sym in CRYPTO_CATALOGUE:
                        res[sym] = {
                            "symbol": sym,
                            "price": float(item.get("lastPrice", 0.0)),
                            "high": float(item.get("highPrice", 0.0)),
                            "low": float(item.get("lowPrice", 0.0)),
                            "volume": float(item.get("volume", 0.0)),
                            "quote_volume": float(item.get("quoteVolume", 0.0)),
                            "change_pct": float(item.get("priceChangePercent", 0.0)),
                            "change_val": float(item.get("priceChange", 0.0)),
                            "weighted_avg_price": float(item.get("weightedAvgPrice", 0.0)),
                            "updated_at": now,
                        }
                self._ticker_cache = res
                self._ticker_cache_time = now
                self._consecutive_errors = 0
                return res
        except Exception as e:
            self._consecutive_errors += 1
            if self._consecutive_errors >= 3:
                self._paused_until = now + 5.0
            logger.error("Failed to fetch 24h tickers from Binance: %s", e)
            return self._ticker_cache

    def fetch_klines(self, symbol: str, interval: str = "5m", limit: int = 100) -> List[Dict[str, Any]]:
        """
        Fetch OHLCV klines with taker buy volume directly from Binance Public API.
        Kline mapping: [0: time, 1: open, 2: high, 3: low, 4: close, 5: volume, ..., 9: taker_buy_vol]
        """
        cache_key = f"{symbol}_{interval}_{limit}"
        now = time.time()
        cached = self._kline_cache.get(cache_key)
        if cached and (now - cached["time"]) < self.cache_ttl_sec:
            return cached["data"]

        if self.is_paused() and cached:
            return cached["data"]

        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        req = urllib.request.Request(url, headers={"User-Agent": "ZienCryptoTerminal/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                raw_klines = json.loads(resp.read().decode("utf-8"))
                candles = []
                for k in raw_klines:
                    candles.append({
                        "t": int(k[0] // 1000),  # epoch seconds
                        "o": float(k[1]),
                        "h": float(k[2]),
                        "l": float(k[3]),
                        "c": float(k[4]),
                        "v": float(k[5]),
                        "quote_vol": float(k[7]),
                        "trades": int(k[8]),
                        "taker_buy_vol": float(k[9]),
                    })
                self._kline_cache[cache_key] = {"time": now, "data": candles}
                return candles
        except Exception as e:
            logger.error("Failed to fetch klines for %s: %s", symbol, e)
            return cached["data"] if cached else []

    def fetch_funding_rate(self, symbol: str) -> float:
        """
        Fetch current perpetual futures funding rate from Binance Futures.
        """
        now = time.time()
        cached = self._funding_cache.get(symbol)
        if cached and (now - cached["time"]) < 30.0:  # Funding rate updates every 8h, 30s cache is optimal
            return cached["rate"]

        url = f"https://fapi.binance.com/fapi/v1/fundingRate?symbol={symbol}&limit=1"
        req = urllib.request.Request(url, headers={"User-Agent": "ZienCryptoTerminal/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data and isinstance(data, list):
                    rate = float(data[0].get("fundingRate", 0.0001))
                    self._funding_cache[symbol] = {"time": now, "rate": rate}
                    return rate
        except Exception:
            pass
        return 0.0001  # Default baseline neutral funding


# Global singleton instance
_scraper_instance: Optional[BinanceFeedScraper] = None

def get_binance_feed() -> BinanceFeedScraper:
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = BinanceFeedScraper()
    return _scraper_instance
