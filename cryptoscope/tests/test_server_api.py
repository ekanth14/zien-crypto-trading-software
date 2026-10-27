"""
Zien Crypto - End-to-End Server API & Route Integration Tests
"""

import json
import socket
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

from cryptoscope.server import ZienCryptoHandler
from cryptoscope.security import DatabaseManager


class TestServerAPI(unittest.TestCase):
    server: ThreadingHTTPServer
    server_thread: threading.Thread
    port: int

    @classmethod
    def setUpClass(cls):
        # Find free port
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        cls.port = s.getsockname()[1]
        s.close()

        cls.server = ThreadingHTTPServer(("127.0.0.1", cls.port), ZienCryptoHandler)
        cls.server.db_manager = DatabaseManager()
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.3)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=1.0)

    def _get(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15.0) as resp:
            return resp.status, resp.headers.get("Content-Type"), resp.read()

    def _post(self, path: str, payload: dict):
        url = f"http://127.0.0.1:{self.port}{path}"
        raw = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=raw,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=15.0) as resp:
                return resp.status, resp.headers.get("Content-Type"), resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.headers.get("Content-Type"), e.read()

    def test_health_endpoint(self):
        status, ctype, body = self._get("/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["status"], "healthy")
        self.assertIn("Zien Crypto", data["service"])
        self.assertGreaterEqual(data["monitored_assets"], 20)

    def test_bootstrap_endpoint(self):
        status, ctype, body = self._get("/api/bootstrap")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("catalogue", data)
        self.assertIn("BTCUSDT", data["catalogue"])
        self.assertIn("session_info", data)
        self.assertIn("laya_ai", data)

    def test_market_endpoint(self):
        status, ctype, body = self._get("/api/crypto/market?timeframe=5")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("quadrants", data)
        self.assertIn("assets", data)

    def test_quote_endpoint(self):
        status, ctype, body = self._get("/api/crypto/quote?symbol=BTCUSDT&timeframe=5")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["symbol"], "BTCUSDT")
        self.assertGreater(data["price"], 0.0)

    def test_candles_endpoint(self):
        status, ctype, body = self._get("/api/crypto/candles?symbol=BTCUSDT&timeframe=5&limit=20")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data["symbol"], "BTCUSDT")
        self.assertIn("candles", data)
        self.assertGreater(len(data["candles"]), 0)

    def test_flow_endpoint(self):
        status, ctype, body = self._get("/api/crypto/flow?timeframe=5")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("stocks", data)
        self.assertIn("sectors", data)
        self.assertIn("matrix", data)

    def test_static_pages(self):
        status, ctype, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)

        status, ctype, body = self._get("/bloomberg")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)

        status, ctype, body = self._get("/flow")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)

    from unittest.mock import patch

    @patch("cryptoscope.laya_ai.LayaCryptoEngine.chat_copilot", return_value={"reply": "Laya AI institutional audit: BTCUSDT shows bullish accumulation above $68,000 with valid R:R."})
    def test_ai_chat_endpoint(self, mock_chat):
        status, ctype, body = self._post("/api/ai/chat", {
            "prompt": "Summarize current BTC market structure and risk:reward.",
            "context": {
                "symbol": "BTCUSDT",
                "price": 68000.0,
                "quant_analysis": {"composite_score": 78, "action": "BUY / LONG"}
            }
        })
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("reply", data)
        self.assertGreater(len(data["reply"]), 20)

    def test_login_invalid_credentials(self):
        status, ctype, body = self._post("/api/login", {
            "email": "invalid@test.com",
            "password": "wrongpassword123"
        })
        self.assertEqual(status, 401)


if __name__ == "__main__":
    unittest.main()
