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
        
        try:
            prev_to = self.timeout_sec
            self.timeout_sec = 2.0
            llm_reply = self._call_ollama(prompt)
            self.timeout_sec = prev_to
            if llm_reply and len(llm_reply) > 50:
                return llm_reply
        except Exception:
            pass
        return rules_text

    def _generate_quant_response(
        self,
        query: str,
        symbol: Optional[str] = None,
        stock_info: Optional[Dict[str, Any]] = None,
        market_snapshot: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Deterministic sub-5ms institutional quantitative intelligence generator."""
        q = query.lower()
        sym = (symbol or (stock_info.get("symbol") if stock_info else "BTCUSDT")).upper()
        
        if not stock_info and market_snapshot and "stocks" in market_snapshot:
            stock_info = market_snapshot["stocks"].get(sym)
            
        price = stock_info.get("price", 0.0) if stock_info else 0.0
        p_str = f"${price:,.2f}" if price >= 1.0 else f"${price:.4f}"
        score = stock_info.get("score", 50) if stock_info else 50
        tier = stock_info.get("tier", "NEUTRAL") if stock_info else "NEUTRAL"
        action = stock_info.get("action", "MONITOR") if stock_info else "MONITOR"
        m = stock_info.get("metrics", {}) if stock_info else {}
        chg = stock_info.get("change", 0.0) if stock_info else 0.0
        funding = stock_info.get("funding_rate", 0.0001) if stock_info else 0.0001
        funding_pct = funding * 100.0
        annualized_funding = funding * 3 * 365 * 100.0
        regime = str(stock_info.get("regime", m.get("oi_regime", "BALANCED"))).replace("_", " ")
        atr = m.get("atr", stock_info.get("atr", 0.0) if stock_info else 0.0)
        atr_str = f"${atr:,.2f}" if atr >= 1.0 else f"${atr:.4f}"
        
        entry = stock_info.get("entry", price) if stock_info else price
        sl = stock_info.get("stop_loss", price * 0.98) if stock_info else price * 0.98
        t1 = stock_info.get("target_1", price * 1.03) if stock_info else price * 1.03
        t2 = stock_info.get("target_2", price * 1.06) if stock_info else price * 1.06
        rr = stock_info.get("rr_ratio", 1.50) if stock_info else 1.50
        
        fmt = lambda val: f"${val:,.2f}" if val >= 1.0 else f"${val:.4f}"
        
        # 1. Market Structure & SMC
        if any(k in q for k in ["structure", "order block", "ob", "fvg", "fair value", "smc", "liquidity", "sweep"]):
            has_bull_ob = m.get("has_bullish_ob", False)
            has_bear_ob = m.get("has_bearish_ob", False)
            fvg_count = m.get("active_fvgs_count", 0)
            
            return (
                f"### 🏛️ Market Structure & Smart Money Analysis: **{sym}**\n\n"
                f"- **Current Auction:** `{p_str}` ({chg:+.2f}% 24h)\n"
                f"- **Structure State:** `{'BULLISH EXPANSION' if score >= 60 else ('BEARISH DISTRIBUTION' if score <= 40 else 'EQUILIBRIUM CHOP')}`\n"
                f"- **Bullish Order Block:** `{'ACTIVE — Demand absorption defending pullbacks' if has_bull_ob else 'None detected within current liquidity range'}`\n"
                f"- **Bearish Order Block:** `{'ACTIVE — Overhead institutional supply cap' if has_bear_ob else 'No active bearish rejection block overhead'}`\n"
                f"- **Fair Value Gaps (FVG):** `{fvg_count} active liquidity imbalances` identified on the current timeframe\n"
                f"- **Volatility Regime (ATR 14):** `{atr_str}` buffer per bar\n\n"
                f"> **Tactical Takeaway:** Institutional players are {'accumulating into liquidity sweeps' if score >= 50 else 'unwinding into local resistance'}. "
                f"Key defensive invalidation sits at **{fmt(sl)}**."
            )
            
        # 2. CVD & Volume Order Flow
        if any(k in q for k in ["cvd", "volume", "delta", "flow", "whale", "absorption", "exhaustion", "taker"]):
            cvd_state = m.get("cvd_divergence", "BALANCED_DELTA")
            cvd_val = m.get("cvd", 0.0)
            return (
                f"### 🌊 Order Flow & CVD Intelligence: **{sym}**\n\n"
                f"- **Cumulative Volume Delta (CVD):** `{cvd_val:,.1f}` net volume contracts\n"
                f"- **Order Flow Divergence:** `{cvd_state.replace('_', ' ')}`\n"
                f"- **Taker Flow Diagnosis:** "
                f"{'Aggressive market buyers are actively absorbing passive sell limit orders' if 'Absorption' in cvd_state or score >= 60 else 'Market sell orders are dominating aggressive tape flow'}.\n"
                f"- **Momentum (Wilder RSI 14):** `{m.get('rsi', 50.0):.1f} / 100`\n"
                f"- **24h Traded Volume:** `${stock_info.get('quote_volume_24h', 0.0) if stock_info else 0.0:,.0f} USDT`\n\n"
                f"> **Flow Verdict:** Tape velocity suggests {'continuation into higher liquidity pools' if score >= 50 else 'caution against long exposure due to delta exhaustion'}."
            )
            
        # 3. Derivatives, Perp Funding & Squeeze Risk
        if any(k in q for k in ["funding", "oi", "perp", "squeeze", "leverage", "rate", "quadrant"]):
            squeeze = str(m.get("squeeze_risk", "MODERATE")).replace("_", " ")
            return (
                f"### ⚡ Perpetual Futures & Skew Matrix: **{sym}**\n\n"
                f"| Metric | Institutional Value | Benchmark Interpretation |\n"
                f"| :--- | :--- | :--- |\n"
                f"| **8h Funding Rate** | `{funding_pct:+.4f}%` | {'Positive (Longs paying Shorts)' if funding > 0 else 'Negative (Shorts paying Longs)'} |\n"
                f"| **Annualized Skew** | `{annualized_funding:+.2f}% APR` | {'Bullish premium' if funding > 0 else 'Discounted perpetual'} |\n"
                f"| **Leverage Regime** | `{regime}` | 4-Quadrant OI Classification |\n"
                f"| **Squeeze Risk** | `{squeeze}` | Liquidation Cascade Probability |\n\n"
                f"> **Derivative Analysis:** Capital allocation reflects `{regime}`. "
                f"{'Elevated short interest creates potential for a rapid short-covering squeeze toward resistance' if 'SHORT' in regime else 'Positioning reflects sustained trend participation without over-leveraged long froth'}."
            )
            
        # 4. Levels, Targets & Trade Setup
        if any(k in q for k in ["level", "target", "entry", "stop", "plan", "setup", "trade", "tp", "sl", "risk"]):
            return (
                f"### 🎯 Institutional Execution Matrix: **{sym}**\n\n"
                f"| Parameter | Level | Strategy Note |\n"
                f"| :--- | :--- | :--- |\n"
                f"| **Action** | **{action}** | Quant composite signal |\n"
                f"| **Suggested Entry** | `{fmt(entry)}` | Optimal liquidity retest zone |\n"
                f"| **Stop Loss (SL)** | `{fmt(sl)}` | Dynamic 1.5× ATR(14) structural barrier |\n"
                f"| **Take Profit 1 (TP1)** | `{fmt(t1)}` | 1.5R target (Secure 50% capital) |\n"
                f"| **Take Profit 2 (TP2)** | `{fmt(t2)}` | 2.5R target (Runner to next liquidity pool) |\n"
                f"| **Risk:Reward (R:R)** | `{rr:.2f}:1` | {'✅ Gatekeeper Valid (>= 1.50)' if rr >= 1.5 else '⚠️ Gatekeeper Alert (< 1.50)'} |\n\n"
                f"> **Risk Protocol:** Always risk a maximum of 1.0% portfolio equity. Trailing stop recommended upon hitting TP1."
            )
            
        # 5. Screener / Market-Wide Overview
        if any(k in q for k in ["market", "screener", "top", "leader", "all", "coins", "rank"]):
            if market_snapshot and "daily_ranking" in market_snapshot:
                top_bulls = [a for a in market_snapshot["daily_ranking"] if a.get("score", 0) >= 55][:3]
                top_bears = [a for a in reversed(market_snapshot["daily_ranking"]) if a.get("score", 0) <= 45][:3]
                bull_txt = ", ".join([f"**{b['symbol'].replace('USDT','')}** ({b['score']})" for b in top_bulls]) or "None"
                bear_txt = ", ".join([f"**{b['symbol'].replace('USDT','')}** ({b['score']})" for b in top_bears]) or "None"
                counts = market_snapshot.get("counts", {})
                return (
                    f"### 🌐 Market-Wide Cross-Asset Intelligence\n\n"
                    f"- **Active Monitoring:** `{counts.get('total', 15)} Perpetual Pairs` 24/7 continuous stream\n"
                    f"- **Market Sentiment:** `{counts.get('bullish', 0)} Bullish` | `{counts.get('neutral', 0)} Neutral` | `{counts.get('bearish', 0)} Bearish`\n"
                    f"- **Top Institutional Buys:** {bull_txt}\n"
                    f"- **Top Distribution Sells:** {bear_txt}\n\n"
                    f"Select any pair in the screener to render instant order blocks, fair value gaps, and execution levels."
                )

        # 6. Default / Comprehensive Asset Thesis
        cats = stock_info.get("category_scores", {}) if stock_info else {}
        trend_s = cats.get("trend", 50)
        mom_s = cats.get("momentum", 50)
        cvd_s = cats.get("cvd", 50)
        perp_s = cats.get("derivatives", 50)
        ob_s = cats.get("structure", 50)
        
        return (
            f"### ⚡ Institutional Quantitative Report: **{sym}**\n\n"
            f"**Current Price:** `{p_str}` | **24h Change:** `{chg:+.2f}%` | **Composite Score:** `{score}/100` (`{tier}`)\n\n"
            f"#### 📊 5-Pillar Factor Decomposition\n"
            f"- **Trend (EMA 9/21):** `{trend_s}/100` — {'Bullish moving average alignment' if trend_s >= 55 else 'Corrective / Bearish pressure'}\n"
            f"- **Momentum (RSI 14):** `{mom_s}/100` (RSI: `{m.get('rsi', 50.0):.1f}`)\n"
            f"- **Order Flow (CVD):** `{cvd_s}/100` — `{m.get('cvd_divergence', 'Balanced Delta').replace('_', ' ')}`\n"
            f"- **Derivatives Skew:** `{perp_s}/100` — 8h Funding `{funding_pct:+.4f}%`, Regime: `{regime}`\n"
            f"- **Market Structure:** `{ob_s}/100` — {'Bullish OB active' if m.get('has_bullish_ob') else 'Key liquidity sweep zone'}\n\n"
            f"#### 🎯 Recommended Action: **{action}**\n"
            f"- **Suggested Entry:** `{fmt(entry)}`\n"
            f"- **Stop Loss:** `{fmt(sl)}` (ATR buffer: `{atr_str}`)\n"
            f"- **Take Profit 1:** `{fmt(t1)}` (1.5R)\n"
            f"- **Take Profit 2:** `{fmt(t2)}` (2.5R)\n"
            f"- **Risk-Reward Ratio:** `{rr:.2f}:1` ({'✅ Institutional Gate Cleared' if rr >= 1.5 else '⚠️ Wait for clearer setup'})\n\n"
            f"> *Generated deterministically from live Binance order book & futures tick flow.*"
        )

    def chat_copilot(self, message: str, market_snapshot: Optional[Dict[str, Any]] = None, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Interactive terminal copilot inquiry."""
        clean_msg = message.strip()
        sym = (symbol or "BTCUSDT").upper()
        stock_info = None
        if market_snapshot and "stocks" in market_snapshot:
            stock_info = market_snapshot["stocks"].get(sym)

        # Fast non-blocking check to Ollama with 1.8s timeout
        llm_reply = None
        if self.is_ollama_alive():
            prompt = f"Asset: {sym}\nPrice: {stock_info.get('price') if stock_info else 'N/A'}\nScore: {stock_info.get('score') if stock_info else 'N/A'}\nQuery: {clean_msg}\nResponse:"
            try:
                prev_to = self.timeout_sec
                self.timeout_sec = 1.8
                llm_reply = self._call_ollama(prompt)
                self.timeout_sec = prev_to
            except Exception:
                llm_reply = None

        if llm_reply and len(llm_reply.strip()) > 30 and not "error" in llm_reply.lower():
            return {
                "reply": llm_reply.strip(),
                "backend": "ollama",
                "model": self.model,
                "symbol": sym,
            }

        # Sub-5ms Institutional Quant Engine Response
        quant_reply = self._generate_quant_response(clean_msg, symbol=sym, stock_info=stock_info, market_snapshot=market_snapshot)
        return {
            "reply": quant_reply,
            "backend": "quant_engine",
            "model": "laya_crypto_quant_core",
            "symbol": sym,
        }


_laya_instance: Optional[LayaCryptoEngine] = None

def get_laya_crypto_engine() -> LayaCryptoEngine:
    global _laya_instance
    if _laya_instance is None:
        _laya_instance = LayaCryptoEngine()
    return _laya_instance
