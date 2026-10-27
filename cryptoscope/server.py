"""
Zien Crypto — High-Performance Quantitative Trading Terminal HTTP & API Server
Pure Python 3.12+ Standard Library Backend.
"""

from __future__ import annotations
import argparse
import json
import logging
import mimetypes
import os
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("zien-crypto")

# Ensure package import resolution
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

from crypto_market import CRYPTO_CATALOGUE, DEFAULT_CRYPTO_CONFIG
from binance_feed import get_binance_feed
from crypto_archive import get_crypto_archive
from session_manager import get_crypto_session_info, build_crypto_market_snapshot
from decision_engine import score_crypto_asset
from laya_ai import get_laya_crypto_engine
from security import DatabaseManager, RateLimiter, verify_password, verify_totp

STATIC_DIR = Path(__file__).parent / "static"
server_start_time = time.time()

rate_limiter = RateLimiter(limit=120, window_sec=60)
rate_limiter_ai = RateLimiter(limit=15, window_sec=60)
rate_limiter_login = RateLimiter(limit=12, window_sec=60)


class ZienCryptoHandler(BaseHTTPRequestHandler):
    server_version = "ZienCrypto/1.0"

    def setup(self):
        super().setup()
        self.db: DatabaseManager = getattr(self.server, "db_manager", None) or DatabaseManager()

    def _drain_request_body(self) -> None:
        if not hasattr(self, "_cached_json_body"):
            try:
                length = int(self.headers.get("Content-Length", 0)) if hasattr(self, "headers") and self.headers else 0
                if 0 < length <= 65536 and hasattr(self, "rfile") and self.rfile:
                    self.rfile.read(length)
                self._cached_json_body = None
            except Exception:
                pass

    def _send_json(self, data: Any, status: int = 200, cookies: Optional[List[str]] = None) -> None:
        self._drain_request_body()
        raw = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._add_security_headers()
        if cookies:
            for c in cookies:
                self.send_header("Set-Cookie", c)
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _send_text(self, text: str, content_type: str = "text/plain; charset=utf-8", status: int = 200) -> None:
        self._drain_request_body()
        raw = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self._add_security_headers()
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
            pass

    def _add_security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com data:; img-src 'self' data: https://bin.bnbstatic.com; connect-src 'self';",
        )

    def _send_rate_limited(self, retry_after: int = 60, detail: str = "Rate limit exceeded.") -> None:
        self._drain_request_body()
        payload = json.dumps({
            "error": "rate_limit_exceeded",
            "detail": detail,
            "retry_after": retry_after,
        }).encode("utf-8")
        self.send_response(429)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Retry-After", str(retry_after))
        self._add_security_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _get_cookie_token(self) -> Optional[str]:
        if not hasattr(self, "headers") or not self.headers:
            return None
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
            if "crypto_session" in cookie:
                return cookie["crypto_session"].value
        except Exception:
            return None
        return None

    def _get_current_session(self) -> Optional[Dict[str, Any]]:
        token = self._get_cookie_token()
        if not token:
            return None
        return self.db.validate_session(token)

    def _parse_json_body(self, max_bytes: int = 65536) -> Optional[Dict[str, Any]]:
        if hasattr(self, "_cached_json_body") and self._cached_json_body is not None:
            return self._cached_json_body
        try:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0 or length > max_bytes:
                self._cached_json_body = None
                return None
            body = self.rfile.read(length)
            parsed = json.loads(body.decode("utf-8"))
            self._cached_json_body = parsed if isinstance(parsed, dict) else None
            return self._cached_json_body
        except Exception:
            self._cached_json_body = None
            return None

    def _serve_static_file(self, filename: str) -> None:
        target = (STATIC_DIR / filename).resolve()
        if not target.is_relative_to(STATIC_DIR.resolve()) or not target.exists() or not target.is_file():
            self._send_json({"error": "File not found"}, status=404)
            return

        mime_type, _ = mimetypes.guess_type(str(target))
        if not mime_type:
            mime_type = "application/octet-stream"

        try:
            with open(target, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self._add_security_headers()
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self._send_json({"error": f"Error reading file: {str(e)}"}, status=500)

    def do_GET(self) -> None:
        client_ip = self.client_address[0] if getattr(self, "client_address", None) else "127.0.0.1"
        if not rate_limiter.is_allowed(client_ip):
            self._send_rate_limited(retry_after=rate_limiter.retry_after(client_ip), detail="Rate limit exceeded.")
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Static / Page routes
        if path in ("/", "/index.html", "/bloomberg"):
            self._serve_static_file("workspace.html")
        elif path == "/flow":
            self._serve_static_file("flow.html")
        elif path.startswith("/static/"):
            self._serve_static_file(path.replace("/static/", "", 1))
        # API routes
        elif path == "/api/health":
            self._handle_health()
        elif path == "/api/bootstrap":
            self._handle_bootstrap()
        elif path in ("/api/crypto/market", "/api/market"):
            self._handle_crypto_market(query)
        elif path in ("/api/crypto/quote", "/api/stock"):
            self._handle_crypto_quote(query)
        elif path in ("/api/crypto/candles", "/api/candles"):
            self._handle_crypto_candles(query)
        elif path in ("/api/crypto/flow", "/api/flow"):
            self._handle_crypto_flow(query)
        elif path == "/api/session/info":
            self._send_json(get_crypto_session_info())
        else:
            self._send_json({"error": "Not found"}, status=404)

    def do_POST(self) -> None:
        client_ip = self.client_address[0] if getattr(self, "client_address", None) else "127.0.0.1"
        if not rate_limiter.is_allowed(client_ip):
            self._send_rate_limited(retry_after=rate_limiter.retry_after(client_ip), detail="Rate limit exceeded.")
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path in ("/api/ai/chat", "/api/chat"):
            if not rate_limiter_ai.is_allowed(client_ip):
                self._send_rate_limited(retry_after=rate_limiter_ai.retry_after(client_ip), detail="AI rate limit (15 req/min).")
                return
            self._handle_ai_chat()
        elif path in ("/api/ai/analyze", "/api/analyze"):
            self._handle_ai_analyze()
        elif path == "/api/login":
            if not rate_limiter_login.is_allowed(client_ip):
                self._send_rate_limited(retry_after=rate_limiter_login.retry_after(client_ip), detail="Too many login attempts.")
                return
            self._handle_login()
        elif path == "/api/logout":
            self._handle_logout()
        else:
            self._send_json({"error": "Unknown POST route"}, status=404)

    def _handle_health(self) -> None:
        uptime = round(time.time() - server_start_time, 1)
        feed = get_binance_feed()
        self._send_json({
            "status": "healthy",
            "service": "Zien Crypto Terminal",
            "version": "1.0.0",
            "uptime_seconds": uptime,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "feed_status": "ONLINE" if not feed.is_paused() else "PAUSED",
            "monitored_assets": len(CRYPTO_CATALOGUE),
        })

    def _handle_bootstrap(self) -> None:
        session = self._get_current_session()
        has_owner = self.db.has_owner()
        laya_engine = get_laya_crypto_engine()
        self._send_json({
            "service": "Zien Crypto Terminal",
            "version": "1.0.0",
            "has_owner": has_owner,
            "session": {
                "authenticated": session is not None,
                "email": session.get("email") if session else None,
                "role": session.get("role") if session else None,
                "csrf_token": session.get("csrf_token") if session else None,
            },
            "catalogue": CRYPTO_CATALOGUE,
            "session_info": get_crypto_session_info(),
            "laya_ai": {
                "name": "Laya Crypto Intelligence Suite",
                "model": laya_engine.model,
                "ollama_alive": laya_engine.is_ollama_alive(),
            },
        })

    def _handle_crypto_market(self, query: Dict[str, List[str]]) -> None:
        try:
            tf = int(query.get("timeframe", ["5"])[0])
        except (ValueError, TypeError):
            tf = 5
        snap = dict(build_crypto_market_snapshot(timeframe=tf))
        quads = {"long_buildup": 0, "short_buildup": 0, "long_unwinding": 0, "short_covering": 0}
        for s in snap.get("stocks", {}).values():
            reg = str(s.get("metrics", {}).get("oi_regime", "")).lower()
            if "long_buildup" in reg:
                quads["long_buildup"] += 1
            elif "short_buildup" in reg:
                quads["short_buildup"] += 1
            elif "long_liquidation" in reg or "long_unwind" in reg:
                quads["long_unwinding"] += 1
            elif "short_cover" in reg:
                quads["short_covering"] += 1
        snap["quadrants"] = quads
        snap["assets"] = list(snap.get("stocks", {}).values())
        self._send_json(snap)

    def _handle_crypto_quote(self, query: Dict[str, List[str]]) -> None:
        raw_sym = query.get("symbol", ["BTCUSDT"])[0].upper().replace("-", "").replace("/", "")
        sym = raw_sym if raw_sym.endswith("USDT") else f"{raw_sym}USDT"
        feed = get_binance_feed()
        tickers = feed.fetch_24h_tickers()
        item = tickers.get(sym)
        if not item:
            self._send_json({"error": f"Crypto asset {sym} not available in catalogue."}, status=404)
            return
        
        try:
            tf = int(query.get("timeframe", ["5"])[0])
        except (ValueError, TypeError):
            tf = 5
        interval_str = f"{tf}m" if tf < 60 else "1h"
        candles = feed.fetch_klines(sym, interval=interval_str, limit=50)
        funding = feed.fetch_funding_rate(sym)
        scored = score_crypto_asset(sym, candles, funding_rate=funding)
        
        meta = CRYPTO_CATALOGUE.get(sym, {"name": sym, "sector": "Crypto"})
        self._send_json({
            "symbol": sym,
            "name": meta["name"],
            "sector": meta["sector"],
            "price": item["price"],
            "change": item["change_pct"],
            "volume_24h": item["volume"],
            "high_24h": item["high"],
            "low_24h": item["low"],
            "timeframe": tf,
            "count": len(candles),
            "candles": candles,
            "quant_analysis": scored,
            "quant_evaluation": scored,
            "funding_rate": funding,
        })

    def _handle_crypto_candles(self, query: Dict[str, List[str]]) -> None:
        sym = query.get("symbol", ["BTCUSDT"])[0].upper()
        try:
            tf = int(query.get("timeframe", ["5"])[0])
            limit = min(500, max(10, int(query.get("limit", ["100"])[0])))
        except (ValueError, TypeError):
            tf = 5
            limit = 100
        interval_str = f"{tf}m" if tf < 60 else "1h"
        candles = get_binance_feed().fetch_klines(sym, interval=interval_str, limit=limit)
        
        # Archive candles in background
        if candles:
            try:
                get_crypto_archive().archive_candles(sym, tf, candles)
            except Exception:
                pass
                
        self._send_json({
            "symbol": sym,
            "timeframe": tf,
            "count": len(candles),
            "candles": candles,
        })

    def _handle_crypto_flow(self, query: Dict[str, List[str]]) -> None:
        try:
            tf = int(query.get("timeframe", ["5"])[0])
        except (ValueError, TypeError):
            tf = 5
        snap = build_crypto_market_snapshot(timeframe=tf)
        
        # Dual build-up matrix (Long Buildup vs Short Buildup)
        long_buildup = []
        short_buildup = []
        for sym, d in snap["stocks"].items():
            regime = d.get("metrics", {}).get("oi_regime", "NEUTRAL")
            if "LONG" in regime:
                long_buildup.append({"symbol": sym, "score": d["score"], "change": d["change"], "price": d["price"]})
            elif "SHORT" in regime:
                short_buildup.append({"symbol": sym, "score": d["score"], "change": d["change"], "price": d["price"]})
                
        self._send_json({
            "as_of": snap["as_of"],
            "session_state": "LIVE",
            "timeframe": tf,
            "stocks": snap["stocks"],
            "sectors": snap["sectors"],
            "trajectories": snap["trajectories"],
            "counts": snap["counts"],
            "matrix": {
                "long_buildup": long_buildup,
                "short_buildup": short_buildup,
            },
        })

    def _handle_ai_chat(self) -> None:
        body = self._parse_json_body() or {}
        msg = (body.get("message") or body.get("prompt") or "").strip()
        sym = body.get("symbol")
        if not sym and isinstance(body.get("context"), dict):
            sym = body["context"].get("symbol")
        if not msg:
            self._send_json({"error": "Message or prompt parameter is required."}, status=400)
            return

        laya = get_laya_crypto_engine()
        snap = build_crypto_market_snapshot(timeframe=5)
        reply = laya.chat_copilot(msg, market_snapshot=snap, symbol=sym)
        self._send_json(reply)

    def _handle_ai_analyze(self) -> None:
        body = self._parse_json_body() or {}
        sym = body.get("symbol", "BTCUSDT").upper()
        feed = get_binance_feed()
        candles = feed.fetch_klines(sym, interval="5m", limit=50)
        funding = feed.fetch_funding_rate(sym)
        scored = score_crypto_asset(sym, candles, funding_rate=funding)
        
        laya = get_laya_crypto_engine()
        briefing = laya.generate_stock_briefing(scored)
        self._send_json({
            "symbol": sym,
            "briefing": briefing,
            "evaluation": scored,
        })

    def _handle_login(self) -> None:
        body = self._parse_json_body() or {}
        email = str(body.get("email", "")).strip().lower()
        password = str(body.get("password", ""))
        totp_code = str(body.get("totp_code", "")).strip()

        if not email or not password:
            self._send_json({"error": "invalid_credentials", "detail": "Email and password required."}, status=400)
            return

        user = self.db.get_user_by_email(email)
        if not user or not verify_password(password, user["password_hash"]):
            self._send_json({"error": "invalid_credentials", "detail": "Incorrect credentials."}, status=401)
            return

        mfa_step = None
        if user["totp_secret"]:
            if not totp_code:
                self._send_json({"error": "mfa_required", "requires_mfa": True, "detail": "Enter 6-digit 2FA code."}, status=400)
                return
            valid, mfa_step = verify_totp(user["totp_secret"], totp_code, last_step=user.get("totp_last_step"))
            if not valid:
                self._send_json({"error": "invalid_mfa", "requires_mfa": True, "detail": "Invalid or expired 2FA code."}, status=401)
                return

        token, csrf = self.db.create_authenticated_session(user["id"], mfa_step)
        cookie = SimpleCookie()
        cookie["crypto_session"] = token
        cookie["crypto_session"]["httponly"] = True
        cookie["crypto_session"]["samesite"] = "Strict"
        cookie["crypto_session"]["path"] = "/"
        cookie["crypto_session"]["max-age"] = 12 * 3600

        self._send_json(
            {"success": True, "csrf_token": csrf, "user": {"email": user["email"], "role": user["role"]}},
            cookies=[cookie["crypto_session"].OutputString()],
        )

    def _handle_logout(self) -> None:
        token = self._get_cookie_token()
        if token:
            self.db.revoke_session(token)
        cookie = SimpleCookie()
        cookie["crypto_session"] = ""
        cookie["crypto_session"]["httponly"] = True
        cookie["crypto_session"]["samesite"] = "Strict"
        cookie["crypto_session"]["path"] = "/"
        cookie["crypto_session"]["max-age"] = 0
        self._send_json({"success": True}, cookies=[cookie["crypto_session"].OutputString()])


def run_server(host: str = "127.0.0.1", port: int = 8900) -> None:
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, ZienCryptoHandler)
    httpd.db_manager = DatabaseManager()
    print("=" * 60)
    print("   ZIEN CRYPTO QUANTITATIVE TRADING TERMINAL v1.0.0")
    print(f"   Server active at: http://{host}:{port}/")
    print(f"   Bloomberg View:   http://{host}:{port}/bloomberg")
    print(f"   Flow River View:  http://{host}:{port}/flow")
    print(f"   Health check:     http://{host}:{port}/api/health")
    print("=" * 60)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Zien Crypto server...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Zien Crypto Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host address")
    parser.add_argument("--port", type=int, default=8900, help="Port (default: 8900)")
    args = parser.parse_args()
    run_server(args.host, args.port)
