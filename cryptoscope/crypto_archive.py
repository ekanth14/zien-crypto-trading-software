"""
Zien Crypto — SQLite Candle & Tick Archive
Stores historical candles and snapshots in an ACID-compliant database.
"""

import os
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_ARCHIVE_PATH = os.environ.get(
    "CRYPTO_ARCHIVE_PATH",
    str(Path(__file__).parent.parent / "work" / "runtime" / "crypto_candles.db"),
)


class CryptoCandleArchive:
    def __init__(self, db_path: str = DEFAULT_ARCHIVE_PATH):
        self.db_path = db_path
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS crypto_candles (
                    symbol TEXT NOT NULL,
                    timeframe INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    quote_volume REAL,
                    taker_buy_vol REAL,
                    source TEXT DEFAULT 'binance',
                    PRIMARY KEY (symbol, timeframe, timestamp)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crypto_sym_tf ON crypto_candles(symbol, timeframe, timestamp)")
            conn.commit()

    def archive_candles(self, symbol: str, timeframe: int, candles: List[Dict[str, Any]], source: str = "binance") -> int:
        if not candles:
            return 0
        inserted = 0
        with self._get_connection() as conn:
            for c in candles:
                conn.execute("""
                    INSERT OR REPLACE INTO crypto_candles 
                    (symbol, timeframe, timestamp, open, high, low, close, volume, quote_volume, taker_buy_vol, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    symbol,
                    timeframe,
                    int(c["t"]),
                    float(c["o"]),
                    float(c["h"]),
                    float(c["l"]),
                    float(c["c"]),
                    float(c.get("v", 0.0)),
                    float(c.get("quote_vol", 0.0)),
                    float(c.get("taker_buy_vol", 0.0)),
                    source,
                ))
                inserted += 1
            conn.commit()
        return inserted

    def get_candles(self, symbol: str, timeframe: int, limit: int = 100) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.execute("""
                SELECT timestamp as t, open as o, high as h, low as l, close as c, 
                       volume as v, quote_volume as quote_vol, taker_buy_vol
                FROM crypto_candles
                WHERE symbol = ? AND timeframe = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (symbol, timeframe, limit))
            rows = [dict(r) for r in cur.fetchall()]
            rows.reverse()
            return rows

    def get_candle_count(self, symbol: Optional[str] = None) -> int:
        with self._get_connection() as conn:
            if symbol:
                cur = conn.execute("SELECT count(*) FROM crypto_candles WHERE symbol = ?", (symbol,))
            else:
                cur = conn.execute("SELECT count(*) FROM crypto_candles")
            return int(cur.fetchone()[0])

    def get_archive_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cur = conn.execute("SELECT count(*) FROM crypto_candles")
            total = int(cur.fetchone()[0])
            cur = conn.execute("SELECT symbol, count(*) FROM crypto_candles GROUP BY symbol")
            by_sym = {row[0]: row[1] for row in cur.fetchall()}
            return {"total_candles": total, "by_symbol": by_sym}


_archive_instance: Optional[CryptoCandleArchive] = None

def get_crypto_archive() -> CryptoCandleArchive:
    global _archive_instance
    if _archive_instance is None:
        _archive_instance = CryptoCandleArchive()
    return _archive_instance
