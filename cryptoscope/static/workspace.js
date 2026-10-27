/**
 * Zien Crypto - Institutional Terminal Orchestration
 * Pure Vanilla JavaScript ES Module.
 */

import { CryptoChart } from '/static/crypto-chart.js';

class TerminalApp {
  constructor() {
    this.activeSymbol = 'BTCUSDT';
    this.activeTimeframe = 5;
    this.activeSector = 'ALL';
    this.marketData = null;
    this.quoteData = null;
    this.candles = [];
    this.chart = null;
    this.session = null;
    this.csrfToken = '';

    this.initDOM();
    this.initChart();
    this.bindEvents();
    this.startEpochClock();
    this.bootstrap();
  }

  initDOM() {
    this.dom = {
      feedDot: document.getElementById('feedDot'),
      feedLatency: document.getElementById('feedLatency'),
      fundingEpoch: document.getElementById('fundingEpoch'),
      layaDot: document.getElementById('layaDot'),
      layaModel: document.getElementById('layaModel'),
      tickerRibbon: document.getElementById('tickerRibbon'),
      marketPairCount: document.getElementById('marketPairCount'),
      quadLongBuild: document.getElementById('quadLongBuild'),
      quadShortBuild: document.getElementById('quadShortBuild'),
      quadLongUnwind: document.getElementById('quadLongUnwind'),
      quadShortCover: document.getElementById('quadShortCover'),
      screenerBody: document.getElementById('screenerBody'),
      activeAssetTitle: document.getElementById('activeAssetTitle'),
      activeAssetName: document.getElementById('activeAssetName'),
      activeAssetPrice: document.getElementById('activeAssetPrice'),
      activeAssetChange: document.getElementById('activeAssetChange'),
      activeFundingRate: document.getElementById('activeFundingRate'),
      compositeScoreVal: document.getElementById('compositeScoreVal'),
      compositeTierBadge: document.getElementById('compositeTierBadge'),
      scoreBreakdown: document.getElementById('scoreBreakdown'),
      rrBadge: document.getElementById('rrBadge'),
      levelEntry: document.getElementById('levelEntry'),
      levelSL: document.getElementById('levelSL'),
      levelT1: document.getElementById('levelT1'),
      levelT2: document.getElementById('levelT2'),
      cvdStatusText: document.getElementById('cvdStatusText'),
      atrValText: document.getElementById('atrValText'),
      oiFundingRegimeText: document.getElementById('oiFundingRegimeText'),
      chatHistory: document.getElementById('chatHistory'),
      chatInput: document.getElementById('chatInput'),
      chatSendBtn: document.getElementById('chatSendBtn'),
      authBtn: document.getElementById('authBtn'),
      loginModal: document.getElementById('loginModal'),
      loginForm: document.getElementById('loginForm'),
      loginEmail: document.getElementById('loginEmail'),
      loginPassword: document.getElementById('loginPassword'),
      loginTotp: document.getElementById('loginTotp'),
      loginError: document.getElementById('loginError'),
      closeLoginBtn: document.getElementById('closeLoginBtn'),
    };
  }

  initChart() {
    this.chart = new CryptoChart('chartContainer');
  }

  bindEvents() {
    // Sector filter buttons
    document.querySelectorAll('.filter-chip').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.filter-chip').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.activeSector = e.target.dataset.sector;
        this.renderScreener();
      });
    });

    // Timeframe selector buttons
    document.querySelectorAll('.tf-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.activeTimeframe = parseInt(e.target.dataset.tf, 10);
        this.loadActiveAssetData();
      });
    });

    // Chat events
    this.dom.chatSendBtn.addEventListener('click', () => this.handleSendMessage());
    this.dom.chatInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') this.handleSendMessage();
    });

    // Quick Prompt Chips
    document.querySelectorAll('.ai-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const prompt = chip.dataset.prompt;
        this.dom.chatInput.value = prompt;
        this.handleSendMessage();
      });
    });

    // Auth modal events
    this.dom.authBtn.addEventListener('click', () => {
      if (this.session && this.session.authenticated) {
        this.handleLogout();
      } else {
        this.dom.loginModal.style.display = 'flex';
      }
    });

    this.dom.closeLoginBtn.addEventListener('click', () => {
      this.dom.loginModal.style.display = 'none';
    });

    this.dom.loginForm.addEventListener('submit', (e) => {
      e.preventDefault();
      this.handleLogin();
    });
  }

  startEpochClock() {
    const updateCountdown = () => {
      const now = new Date();
      const utcHours = now.getUTCHours();
      let nextEpochHour = 8;
      if (utcHours >= 16) nextEpochHour = 24;
      else if (utcHours >= 8) nextEpochHour = 16;

      const target = new Date(Date.UTC(
        now.getUTCFullYear(),
        now.getUTCMonth(),
        now.getUTCDate() + (nextEpochHour === 24 ? 1 : 0),
        nextEpochHour === 24 ? 0 : nextEpochHour,
        0, 0, 0
      ));

      const diffMs = Math.max(0, target.getTime() - now.getTime());
      const h = String(Math.floor(diffMs / 3600000)).padStart(2, '0');
      const m = String(Math.floor((diffMs % 3600000) / 60000)).padStart(2, '0');
      const s = String(Math.floor((diffMs % 60000) / 1000)).padStart(2, '0');

      if (this.dom.fundingEpoch) {
        this.dom.fundingEpoch.textContent = `${h}:${m}:${s} UTC`;
      }
    };

    updateCountdown();
    setInterval(updateCountdown, 1000);
  }

  async bootstrap() {
    try {
      const res = await fetch('/api/bootstrap');
      if (res.ok) {
        const data = await res.json();
        this.session = data.session;
        this.csrfToken = data.session?.csrf_token || '';

        if (this.session && this.session.authenticated) {
          this.dom.authBtn.textContent = 'Logout';
          this.dom.authBtn.style.background = '#dc2626';
        }

        if (data.laya_ai) {
          this.dom.layaModel.textContent = data.laya_ai.model;
          if (!data.laya_ai.ollama_alive) {
            this.dom.layaDot.classList.add('warning');
          }
        }
      }
    } catch (err) {
      console.warn('Bootstrap fetch warning:', err);
    }

    // Start market data loop
    await this.pollMarket();
    await this.loadActiveAssetData();

    setInterval(() => this.pollMarket(), 2500);
    setInterval(() => this.loadActiveAssetData(true), 3500);
  }

  async pollMarket() {
    const t0 = performance.now();
    try {
      const res = await fetch(`/api/crypto/market?timeframe=${this.activeTimeframe}`);
      if (!res.ok) return;
      const data = await res.json();
      const latency = Math.round(performance.now() - t0);

      this.dom.feedLatency.textContent = `${latency}ms`;
      this.dom.feedDot.classList.remove('warning');
      this.marketData = data;

      // Update Quadrant counters
      if (data.quadrants) {
        this.dom.quadLongBuild.textContent = data.quadrants.long_buildup || 0;
        this.dom.quadShortBuild.textContent = data.quadrants.short_buildup || 0;
        this.dom.quadLongUnwind.textContent = data.quadrants.long_unwinding || 0;
        this.dom.quadShortCover.textContent = data.quadrants.short_covering || 0;
      }

      this.renderTickerRibbon();
      this.renderScreener();
    } catch (err) {
      this.dom.feedDot.classList.add('warning');
      this.dom.feedLatency.textContent = 'ERR';
    }
  }

  renderTickerRibbon() {
    if (!this.marketData || !this.marketData.assets) return;
    const topAssets = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT', 'SUIUSDT', 'NEARUSDT', 'AVAXUSDT', 'LINKUSDT'];
    
    let html = '';
    for (const sym of topAssets) {
      const a = this.marketData.assets.find(item => item.symbol === sym);
      if (!a) continue;
      const isUp = a.change >= 0;
      const chgClass = isUp ? 'up' : 'down';
      const sign = isUp ? '+' : '';
      const priceStr = a.price >= 1000 ? a.price.toFixed(1) : (a.price >= 1 ? a.price.toFixed(2) : a.price.toFixed(4));
      
      html += `
        <div class="ticker-chip" data-symbol="${a.symbol}">
          <span class="sym">${a.symbol.replace('USDT', '')}</span>
          <span style="color: #cbd5e1;">$${priceStr}</span>
          <span class="chg ${chgClass}">${sign}${a.change.toFixed(2)}%</span>
        </div>
      `;
    }

    this.dom.tickerRibbon.innerHTML = html;
    this.dom.tickerRibbon.querySelectorAll('.ticker-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        this.selectAsset(chip.dataset.symbol);
      });
    });
  }

  renderScreener() {
    if (!this.marketData || !this.marketData.assets) return;
    const assets = this.marketData.assets;
    let filtered = assets;
    if (this.activeSector !== 'ALL') {
      filtered = assets.filter(a => a.sector === this.activeSector);
    }

    let rowsHtml = '';
    for (const a of filtered) {
      const isUp = a.change >= 0;
      const chgColor = isUp ? 'var(--bull)' : 'var(--bear)';
      const sign = isUp ? '+' : '';
      const priceStr = a.price >= 1000 ? a.price.toFixed(1) : (a.price >= 1 ? a.price.toFixed(2) : a.price.toFixed(4));
      const isSelected = a.symbol === this.activeSymbol ? 'selected' : '';
      const score = Math.round(a.composite_score ?? a.score ?? 50);

      let scoreBadgeClass = 'neutral';
      if (score >= 75) scoreBadgeClass = 'high-bull';
      else if (score >= 60) scoreBadgeClass = 'bull';
      else if (score <= 25) scoreBadgeClass = 'high-bear';
      else if (score <= 40) scoreBadgeClass = 'bear';

      const rawRegime = a.regime || a.metrics?.oi_regime || a.tier || 'BALANCED';
      const regimeStr = String(rawRegime).replace(/_/g, ' ');

      rowsHtml += `
        <tr class="asset-row ${isSelected}" data-symbol="${a.symbol}">
          <td>
            <div style="font-weight: 700; color: #f8fafc;">${a.symbol.replace('USDT', '')}</div>
            <div style="font-size: 9px; color: #64748b;">${a.name}</div>
          </td>
          <td style="text-align: right; font-weight: 600;">$${priceStr}</td>
          <td style="text-align: right; color: ${chgColor}; font-weight: 600;">${sign}${a.change.toFixed(2)}%</td>
          <td style="text-align: center;">
            <span class="score-badge ${scoreBadgeClass}">${score}</span>
          </td>
          <td>
            <span style="font-size: 9px; color: #94a3b8;">${regimeStr}</span>
          </td>
        </tr>
      `;
    }

    this.dom.screenerBody.innerHTML = rowsHtml;
    this.dom.screenerBody.querySelectorAll('.asset-row').forEach(row => {
      row.addEventListener('click', () => {
        this.selectAsset(row.dataset.symbol);
      });
    });
  }

  selectAsset(symbol) {
    if (this.activeSymbol === symbol) return;
    this.activeSymbol = symbol;
    this.renderScreener();
    this.loadActiveAssetData();
  }

  async loadActiveAssetData(silent = false) {
    try {
      const [candleRes, quoteRes] = await Promise.all([
        fetch(`/api/crypto/candles?symbol=${this.activeSymbol}&timeframe=${this.activeTimeframe}&limit=70`),
        fetch(`/api/crypto/quote?symbol=${this.activeSymbol}&timeframe=${this.activeTimeframe}`)
      ]);

      if (candleRes.ok) {
        const cData = await candleRes.json();
        this.candles = cData.candles || [];
      }

      if (quoteRes.ok) {
        this.quoteData = await quoteRes.json();
      }

      this.updateActiveUI();
      if (this.chart) {
        this.chart.setData(this.candles, this.quoteData?.quant_analysis || null);
      }
    } catch (err) {
      if (!silent) console.error('Failed to load asset data:', err);
    }
  }

  updateActiveUI() {
    if (!this.quoteData) return;
    const q = this.quoteData;
    const isUp = q.change >= 0;
    const sign = isUp ? '+' : '';
    const priceStr = q.price >= 1000 ? q.price.toFixed(1) : (q.price >= 1 ? q.price.toFixed(2) : q.price.toFixed(4));

    this.dom.activeAssetTitle.textContent = q.symbol;
    this.dom.activeAssetName.textContent = `${q.name} • ${q.sector}`;
    this.dom.activeAssetPrice.textContent = `$${priceStr}`;
    this.dom.activeAssetPrice.style.color = isUp ? 'var(--bull)' : 'var(--bear)';

    this.dom.activeAssetChange.textContent = `${sign}${q.change.toFixed(2)}%`;
    this.dom.activeAssetChange.style.background = isUp ? 'rgba(16,185,129,0.15)' : 'rgba(244,63,94,0.15)';
    this.dom.activeAssetChange.style.color = isUp ? 'var(--bull)' : 'var(--bear)';

    if (q.funding_rate !== undefined && q.funding_rate !== null) {
      const fundPct = (q.funding_rate * 100).toFixed(4);
      this.dom.activeFundingRate.textContent = `${fundPct > 0 ? '+' : ''}${fundPct}%`;
      this.dom.activeFundingRate.style.color = q.funding_rate > 0.0003 ? '#f43f5e' : (q.funding_rate < 0 ? '#10b981' : '#f59e0b');
    }

    // Quant Decision Engine Values
    const qa = q.quant_analysis || q.quant_evaluation;
    if (qa) {
      const score = Math.round(qa.composite_score ?? qa.score ?? 50);
      this.dom.compositeScoreVal.textContent = score;

      const tier = qa.tier_label || qa.tier || 'NEUTRAL';
      this.dom.compositeTierBadge.textContent = tier;

      let tBadgeClass = 'neutral';
      if (score >= 75) tBadgeClass = 'high-bull';
      else if (score >= 60) tBadgeClass = 'bull';
      else if (score <= 25) tBadgeClass = 'high-bear';
      else if (score <= 40) tBadgeClass = 'bear';
      this.dom.compositeTierBadge.className = `score-badge ${tBadgeClass}`;

      const cs = qa.category_scores || {
        trend: qa.metrics?.ema_fast >= qa.metrics?.ema_slow ? 65 : 35,
        momentum: qa.metrics?.rsi || 50,
        cvd: qa.cvd?.delta_ratio ? 50 + qa.cvd.delta_ratio * 100 : 50,
        derivatives: 50,
        structure: qa.metrics?.has_bullish_ob ? 70 : 50
      };

      this.dom.scoreBreakdown.innerHTML = `
        <span>Trend: ${Math.round(cs.trend || 0)}</span>
        <span>Mom: ${Math.round(cs.momentum || 0)}</span>
        <span>CVD: ${Math.round(cs.cvd || 0)}</span>
        <span>Perp: ${Math.round(cs.derivatives || 0)}</span>
        <span>OB: ${Math.round(cs.structure || 0)}</span>
      `;

      const ts = qa.trade_signal || {
        entry_price: qa.entry || q.price,
        stop_loss: qa.stop_loss || (q.price * 0.98),
        target_1: qa.target_1 || (q.price * 1.03),
        target_2: qa.target_2 || (q.price * 1.06),
        rr_ratio: qa.rr_ratio || 1.50
      };

      const fmt = (p) => p >= 1000 ? `$${p.toFixed(1)}` : (p >= 1 ? `$${p.toFixed(2)}` : `$${p.toFixed(4)}`);
      this.dom.levelEntry.textContent = fmt(ts.entry_price || qa.entry || q.price);
      this.dom.levelSL.textContent = fmt(ts.stop_loss || qa.stop_loss || (q.price * 0.98));
      this.dom.levelT1.textContent = fmt(ts.target_1 || qa.target_1 || (q.price * 1.03));
      this.dom.levelT2.textContent = fmt(ts.target_2 || qa.target_2 || (q.price * 1.06));

      const rr = ts.rr_ratio || qa.rr_ratio || 1.50;
      const rrValid = rr >= 1.5;
      this.dom.rrBadge.textContent = `R:R: ${rr.toFixed(2)} (${rrValid ? 'GATE VALID' : 'BELOW 1.5'})`;
      this.dom.rrBadge.style.color = rrValid ? '#10b981' : '#f59e0b';

      const cvdRegime = qa.cvd?.regime || qa.metrics?.cvd_divergence || 'Neutral';
      this.dom.cvdStatusText.textContent = String(cvdRegime).replace(/_/g, ' ');
      this.dom.cvdStatusText.style.color = (cvdRegime.includes('Absorption') || cvdRegime.includes('Buy') || score >= 60) ? '#10b981' : '#f43f5e';

      const atrVal = qa.atr || qa.metrics?.atr || 0;
      this.dom.atrValText.textContent = atrVal >= 1.0 ? `$${atrVal.toFixed(2)}` : `$${atrVal.toFixed(4)}`;

      const oiRegime = qa.oi_funding_regime || qa.metrics?.oi_regime || 'BALANCED';
      this.dom.oiFundingRegimeText.textContent = String(oiRegime).replace(/_/g, ' ').toUpperCase();
    }
  }

  async handleSendMessage() {
    const text = this.dom.chatInput.value.trim();
    if (!text) return;

    this.dom.chatInput.value = '';
    this.appendMessage('user', text);

    const thinkingId = this.appendMessage('laya', '<em>Laya Crypto is analyzing market structure and derivatives flow...</em>');

    try {
      const context = {
        symbol: this.activeSymbol,
        timeframe: `${this.activeTimeframe}m`,
        price: this.quoteData?.price,
        change: this.quoteData?.change,
        funding_rate: this.quoteData?.funding_rate,
        quant_analysis: this.quoteData?.quant_analysis
      };

      const res = await fetch('/api/ai/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt: text,
          context: context,
          csrf_token: this.csrfToken
        })
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        this.updateMessage(thinkingId, `Error communicating with Laya: ${err.detail || res.statusText}`);
        return;
      }

      const data = await res.json();
      const reply = data.reply || 'No response generated.';
      this.updateMessage(thinkingId, this.formatMarkdown(reply));
    } catch (err) {
      this.updateMessage(thinkingId, `Connection error to Laya AI Engine: ${err.message}`);
    }
  }

  appendMessage(role, htmlContent) {
    const id = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 5)}`;
    const div = document.createElement('div');
    div.id = id;
    div.className = `chat-bubble ${role}`;
    div.innerHTML = htmlContent;
    this.dom.chatHistory.appendChild(div);
    this.dom.chatHistory.scrollTop = this.dom.chatHistory.scrollHeight;
    return id;
  }

  updateMessage(id, htmlContent) {
    const el = document.getElementById(id);
    if (el) {
      el.innerHTML = htmlContent;
      this.dom.chatHistory.scrollTop = this.dom.chatHistory.scrollHeight;
    }
  }

  formatMarkdown(text) {
    if (!text) return '';
    let html = text;

    // Convert markdown tables
    html = html.replace(/(?:^|\n)(\|.+?\|\n\|[-:| ]+\|\n(?:\|.+?\|\n?)+)/g, (match) => {
      const rows = match.trim().split('\n');
      if (rows.length < 3) return match;
      const headers = rows[0].split('|').filter(c => c.trim().length > 0).map(c => `<th style="padding:4px 8px;border:1px solid rgba(255,255,255,0.08);text-align:left;">${c.trim()}</th>`).join('');
      const bodyRows = rows.slice(2).map(r => {
        const cells = r.split('|').filter(c => c.trim().length > 0).map(c => `<td style="padding:3px 8px;border:1px solid rgba(255,255,255,0.05);">${c.trim()}</td>`).join('');
        return `<tr>${cells}</tr>`;
      }).join('');
      return `<div style="overflow-x:auto;margin:8px 0;"><table style="width:100%;border-collapse:collapse;font-size:11px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.08);border-radius:4px;"><thead><tr style="background:rgba(255,255,255,0.05);color:#94a3b8;">${headers}</tr></thead><tbody>${bodyRows}</tbody></table></div>`;
    });

    // Headers
    html = html.replace(/^### (.*$)/gim, '<div style="font-weight:700;font-size:13px;color:#f8fafc;margin:8px 0 4px;">$1</div>');
    html = html.replace(/^#### (.*$)/gim, '<div style="font-weight:600;font-size:12px;color:#cbd5e1;margin:6px 0 3px;">$1</div>');

    // Blockquotes
    html = html.replace(/^\> (.*$)/gim, '<div style="border-left:3px solid #10b981;padding:4px 8px;margin:6px 0;background:rgba(16,185,129,0.08);font-size:11px;color:#94a3b8;border-radius:0 3px 3px 0;">$1</div>');

    // Bullet points
    html = html.replace(/^\- (.*$)/gim, '<div style="padding-left:10px;margin:2px 0;color:#cbd5e1;">• $1</div>');

    // Bold, Italic, Code
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="color:#f8fafc;">$1</strong>');
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/`([^`]+)`/g, '<code style="background:rgba(255,255,255,0.08);padding:1px 5px;border-radius:3px;color:#38bdf8;font-family:monospace;font-size:11px;">$1</code>');

    // Newlines
    html = html.replace(/\n\n/g, '<br><br>');
    html = html.replace(/\n/g, '<br>');

    return html;
  }

  async handleLogin() {
    this.dom.loginError.style.display = 'none';
    const email = this.dom.loginEmail.value.trim();
    const password = this.dom.loginPassword.value;
    const totp = this.dom.loginTotp.value.trim();

    try {
      const res = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password, totp })
      });

      const data = await res.json();
      if (!res.ok) {
        this.dom.loginError.textContent = data.detail || data.error || 'Authentication failed.';
        this.dom.loginError.style.display = 'block';
        return;
      }

      this.session = { authenticated: true, email: data.email, role: data.role };
      this.csrfToken = data.csrf_token || '';
      this.dom.loginModal.style.display = 'none';
      this.dom.authBtn.textContent = 'Logout';
      this.dom.authBtn.style.background = '#dc2626';
    } catch (err) {
      this.dom.loginError.textContent = `Login error: ${err.message}`;
      this.dom.loginError.style.display = 'block';
    }
  }

  async handleLogout() {
    try {
      await fetch('/api/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ csrf_token: this.csrfToken })
      });
      window.location.reload();
    } catch (err) {
      window.location.reload();
    }
  }
}

// Start terminal on load
window.addEventListener('DOMContentLoaded', () => {
  new TerminalApp();
});
