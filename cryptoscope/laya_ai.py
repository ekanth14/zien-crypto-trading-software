"""
Zien Crypto — Laya AI Quantitative Decision & Chat Copilot Engine
Integrates with local Ollama LLM (Gemma 4 / Laya-Crypto) with deterministic fallback.
"""

import json
import logging
import os
import re
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional

logger = logging.getLogger("zien-crypto.laya_ai")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "laya-crypto:latest")


CRYPTO_QUANT_SYSTEM_PROMPT = """You are LAYA-CRYPTO, an institutional quantitative crypto trading copilot and risk officer.
You analyze cryptocurrency spot and perpetual futures markets using:
1. ICT Smart Money Concepts: Order Blocks (OB), Fair Value Gaps (FVG), Liquidity Pool Sweeps.
2. Volume Order Flow: Cumulative Volume Delta (CVD), aggressive taker absorption vs exhaustion.
3. Derivatives Skew: Perpetual Funding Rate (annualized), Open Interest 4-quadrant leverage analysis.
4. Volatility: Wilder Smoothed ATR (14) dynamic stop-loss and take-profit calculation (minimum R:R >= 1.5).

Rules:
- Never invent prices or levels. All cited support, resistance, and targets must align within 0.2% of the provided data.
- Provide institutional, disciplined analysis with actionable trade parameters (Entry, Stop Loss, Target 1, Target 2, R:R).
- If the risk-reward ratio is below 1.5, explicitly declare "AVOID - POOR R:R".
- Maintain a concise, technical, and objective Bloomberg-style tone.
"""


class LayaCryptoEngine:
    def __init__(self, ollama_host: str = OLLAMA_HOST, model: str = DEFAULT_MODEL, timeout_sec: float = 35.0):
        host = ollama_host.strip().rstrip("/")
        if not host.startswith("http://") and not host.startswith("https://"):
            host = f"http://{host}"
        self.ollama_host = host
        self.model = model
        self.timeout_sec = timeout_sec

    def is_ollama_alive(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_available_models(self) -> List[str]:
        try:
            req = urllib.request.Request(f"{self.ollama_host}/api/tags")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m.get("name") for m in data.get("models", [])]
        except Exception:
            return []

    def _call_ollama(self, prompt: str, system: Optional[str] = None) -> Optional[str]:
        url = f"{self.ollama_host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": system or CRYPTO_QUANT_SYSTEM_PROMPT,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9,
                "num_ctx": 4096,
            }
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res.get("response", "").strip()
        except urllib.error.HTTPError as e:
            # Fallback to gemma4:12b or laya-quant:latest if custom crypto model not built yet
            if e.code == 404 or e.code == 400:
                payload["model"] = "laya-quant:latest"
                try:
                    req2 = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req2, timeout=self.timeout_sec) as resp2:
                        return json.loads(resp2.read().decode("utf-8")).get("response", "").strip()
                except Exception:
                    pass
            return None
        except Exception:
            return None

    def generate_stock_briefing(self, scored_asset: Dict[str, Any]) -> str:
        """Generates deterministic quant briefing with LLM enhancement if reachable."""
        sym = scored_asset.get("symbol", "CRYPTO")
        price = scored_asset.get("price", 0.0)
        score = scored_asset.get("score", 50)
        tier = scored_asset.get("tier", "NEUTRAL")
        action = scored_asset.get("action", "WAIT")
        m = scored_asset.get("metrics", {})
        
        rules_text = (
            f"[{sym}] Current Price: ${price:,.2f} | Score: {score}/100 ({tier})\n"
            f"Directional Setup: {action} | R:R Ratio: {scored_asset.get('rr_ratio', 0.0)}:1\n"
            f"CVD State: {m.get('cvd_divergence', 'NONE')} | RSI(14): {m.get('rsi', 50.0)}\n"
            f"Funding Rate: {m.get('funding_rate', 0.0):.4%} (Regime: {m.get('oi_regime', 'NEUTRAL')})\n"
            f"Order Blocks: Bullish OB = {'ACTIVE' if m.get('has_bullish_ob') else 'NONE'}, Bearish OB = {'ACTIVE' if m.get('has_bearish_ob') else 'NONE'}."
        )
        
        prompt = (
            f"Provide an institutional quantitative market summary for {sym} based on the following verified snapshot:\n"
            f"{rules_text}\n"
            f"Detail entry, stop loss (${scored_asset.get('stop_loss', 0.0)}), and target (${scored_asset.get('target_1', 0.0)}) with reasoning."
        )
        
        llm_reply = self._call_ollama(prompt)
        if llm_reply and len(llm_reply) > 50:
            return llm_reply
        return rules_text

    def chat_copilot(self, message: str, market_snapshot: Optional[Dict[str, Any]] = None, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Interactive terminal copilot inquiry."""
        clean_msg = message.strip()
        context = ""
        if symbol and market_snapshot and "stocks" in market_snapshot:
            stock_info = market_snapshot["stocks"].get(symbol.upper())
            if stock_info:
                context = (
                    f"Selected Asset Context: {symbol}\n"
                    f"Price: ${stock_info.get('price', 0.0):,.2f} | 24h Change: {stock_info.get('change', 0.0)}%\n"
                    f"Quant Score: {stock_info.get('score')}/100 | Action: {stock_info.get('action')}\n"
                    f"Funding: {stock_info.get('funding_rate', 0.0):.4%} | CVD: {stock_info.get('metrics', {}).get('cvd_divergence')}\n"
                )
                
        prompt = f"{context}\nTrader Query: {clean_msg}\nResponse:"
        llm_reply = self._call_ollama(prompt)
        if llm_reply:
            return {
                "reply": llm_reply,
                "backend": "ollama",
                "model": self.model,
                "symbol": symbol,
            }
        
        # Rule-based fallback
        fallback = f"Laya Crypto Quant rules response for {symbol or 'market'}: Quant engine active. Market running 24/7 continuous stream."
        return {
            "reply": fallback,
            "backend": "rules",
            "model": "deterministic_quant_rules",
            "symbol": symbol,
        }


_laya_instance: Optional[LayaCryptoEngine] = None

def get_laya_crypto_engine() -> LayaCryptoEngine:
    global _laya_instance
    if _laya_instance is None:
        _laya_instance = LayaCryptoEngine()
    return _laya_instance
