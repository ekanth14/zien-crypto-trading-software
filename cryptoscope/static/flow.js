/**
 * Zien Crypto - Capital Flow River Animation & Matrix Visualizer
 * Pure Vanilla JavaScript ES Module.
 */

class CryptoFlowApp {
  constructor() {
    this.timeframe = 5;
    this.data = null;
    this.canvas = document.getElementById('riverCanvas');
    this.ctx = this.canvas ? this.canvas.getContext('2d') : null;
    this.hoverAsset = null;
    this.mouseX = -1;
    this.mouseY = -1;

    this.sectorColors = {
      'Layer 1': '#06b6d4',
      'Layer 2': '#3b82f6',
      'DeFi': '#a855f7',
      'AI & Big Data': '#10b981',
      'Meme': '#f43f5e',
      'Crypto': '#f59e0b'
    };

    this.init();
  }

  init() {
    this.setupEpochClock();
    this.setupEvents();
    this.resizeCanvas();
    this.pollFlow();
    setInterval(() => this.pollFlow(), 3000);
  }

  setupEpochClock() {
    const el = document.getElementById('fundingEpoch');
    const update = () => {
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
      if (el) el.textContent = `${h}:${m}:${s} UTC`;
    };
    update();
    setInterval(update, 1000);
  }

  setupEvents() {
    window.addEventListener('resize', () => {
      this.resizeCanvas();
      this.renderRiver();
    });

    document.querySelectorAll('.tf-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
        e.target.classList.add('active');
        this.timeframe = parseInt(e.target.dataset.tf, 10);
        this.pollFlow();
      });
    });

    if (this.canvas) {
      this.canvas.addEventListener('mousemove', (e) => {
        const rect = this.canvas.getBoundingClientRect();
        this.mouseX = e.clientX - rect.left;
        this.mouseY = e.clientY - rect.top;
        this.renderRiver();
      });

      this.canvas.addEventListener('mouseleave', () => {
        this.mouseX = -1;
        this.mouseY = -1;
        this.renderRiver();
      });
    }
  }

  resizeCanvas() {
    if (!this.canvas) return;
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.dpr = window.devicePixelRatio || 1;
    this.width = rect.width;
    this.height = rect.height;

    this.canvas.width = Math.floor(this.width * this.dpr);
    this.canvas.height = Math.floor(this.height * this.dpr);

    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.scale(this.dpr, this.dpr);
  }

  async pollFlow() {
    try {
      const res = await fetch(`/api/crypto/flow?timeframe=${this.timeframe}`);
      if (!res.ok) return;
      this.data = await res.json();
      this.renderSectorStrip();
      this.renderMatrixLists();
      this.renderRiver();
    } catch (err) {
      console.warn('Flow poll warning:', err);
    }
  }

  renderSectorStrip() {
    const strip = document.getElementById('sectorStrip');
    if (!strip || !this.data || !this.data.sectors) return;

    let html = '';
    for (const [sec, d] of Object.entries(this.data.sectors)) {
      const isUp = (d.avg_change || 0) >= 0;
      const color = isUp ? 'var(--bull)' : 'var(--bear)';
      const sign = isUp ? '+' : '';
      const dotCol = this.sectorColors[sec] || '#94a3b8';

      html += `
        <div class="sector-card">
          <div class="sector-name" style="display: flex; align-items: center; gap: 4px;">
            <span style="display:inline-block;width:6px;height:6px;border-radius:50%;background:${dotCol};"></span>
            ${sec}
          </div>
          <div class="sector-val" style="color: ${color}">
            ${sign}${(d.avg_change || 0).toFixed(2)}%
          </div>
          <div style="font-size: 9px; color: #64748b; margin-top: 2px;">
            Avg Score: <strong>${Math.round(d.avg_score || 50)}</strong>
          </div>
        </div>
      `;
    }
    strip.innerHTML = html;
  }

  renderMatrixLists() {
    if (!this.data || !this.data.matrix) return;
    const longList = document.getElementById('longMatrixList');
    const shortList = document.getElementById('shortMatrixList');
    const longCount = document.getElementById('longCount');
    const shortCount = document.getElementById('shortCount');

    const lb = this.data.matrix.long_buildup || [];
    const sb = this.data.matrix.short_buildup || [];

    if (longCount) longCount.textContent = lb.length;
    if (shortCount) shortCount.textContent = sb.length;

    const renderItems = (arr, isLong) => {
      if (!arr.length) return '<div style="font-size: 10px; color: #64748b; padding: 8px;">No active symbols</div>';
      return arr.map(item => `
        <div class="matrix-item" onclick="window.location.href='/bloomberg'">
          <div>
            <div style="font-weight: 700; color: #f8fafc;">${item.symbol.replace('USDT', '')}</div>
            <div style="font-size: 9px; color: ${isLong ? 'var(--bull)' : 'var(--bear)'};">
              ${item.change >= 0 ? '+' : ''}${item.change.toFixed(2)}%
            </div>
          </div>
          <div style="text-align: right;">
            <span class="score-badge ${isLong ? 'bull' : 'bear'}">${Math.round(item.score)}</span>
          </div>
        </div>
      `).join('');
    };

    if (longList) longList.innerHTML = renderItems(lb, true);
    if (shortList) shortList.innerHTML = renderItems(sb, false);
  }

  renderRiver() {
    if (!this.ctx || !this.width || !this.height || !this.data) return;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    const trajectories = this.data.trajectories || {};
    const keys = Object.keys(trajectories);
    if (!keys.length) {
      ctx.fillStyle = '#64748b';
      ctx.font = '12px ui-monospace, monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Accumulating continuous rolling flow trajectories...', this.width / 2, this.height / 2);
      return;
    }

    // Grid lines
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
    ctx.lineWidth = 1;
    for (let x = 50; x < this.width; x += 100) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, this.height);
      ctx.stroke();
    }
    const midY = this.height / 2;
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(0, midY);
    ctx.lineTo(this.width, midY);
    ctx.stroke();
    ctx.setLineDash([]);

    ctx.fillStyle = '#64748b';
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.fillText('AGGRESSIVE INFLOW (SCORE 100)', 14, 20);
    ctx.fillText('NEUTRAL EQUILIBRIUM (SCORE 50)', 14, midY - 6);
    ctx.fillText('AGGRESSIVE OUTFLOW (SCORE 0)', 14, this.height - 12);

    // Draw stream lines for assets
    for (const sym of keys) {
      const pts = trajectories[sym];
      if (!pts || pts.length < 2) continue;

      const meta = this.data.stocks[sym];
      const sector = meta ? meta.sector : 'Crypto';
      const color = this.sectorColors[sector] || '#38bdf8';

      ctx.strokeStyle = color;
      ctx.lineWidth = sym === 'BTCUSDT' || sym === 'ETHUSDT' || sym === 'SOLUSDT' ? 2.5 : 1.2;
      ctx.globalAlpha = 0.7;

      ctx.beginPath();
      for (let i = 0; i < pts.length; i++) {
        const p = pts[i];
        const x = (i / (pts.length - 1)) * (this.width - 90) + 10;
        // Map score 0-100 to y (height-30 to 30)
        const y = this.height - 30 - ((p.score / 100) * (this.height - 60));

        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // End label
      const last = pts[pts.length - 1];
      const endX = this.width - 80;
      const endY = this.height - 30 - ((last.score / 100) * (this.height - 60));

      ctx.fillStyle = color;
      ctx.globalAlpha = 1.0;
      ctx.font = '9px ui-monospace, monospace';
      ctx.fillText(sym.replace('USDT', ''), endX + 4, endY + 3);
    }
  }
}

window.addEventListener('DOMContentLoaded', () => {
  new CryptoFlowApp();
});
