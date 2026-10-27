/**
 * Zien Crypto - Institutional HTML5 Canvas Candlestick, CVD, & Microstructure Chart
 * Pure Vanilla JavaScript ES Module. Zero external dependencies.
 */

export class CryptoChart {
  constructor(containerId, options = {}) {
    this.container = typeof containerId === 'string' ? document.getElementById(containerId) : containerId;
    if (!this.container) throw new Error(`Container #${containerId} not found`);

    this.options = Object.assign({
      bullColor: '#10b981',
      bearColor: '#f43f5e',
      gridColor: 'rgba(255, 255, 255, 0.05)',
      textColor: '#94a3b8',
      textHighlight: '#f8fafc',
      cvdColor: '#38bdf8',
      rsiColor: '#e879f9',
      emaColors: {
        ema9: '#06b6d4',
        ema21: '#f59e0b',
        ema50: '#a855f7',
        ema200: '#3b82f6'
      }
    }, options);

    this.candles = [];
    this.quant = null;
    this.hoverIndex = -1;
    this.mouseX = -1;
    this.mouseY = -1;

    this.initDOM();
    this.setupEvents();
    this.resize();
  }

  initDOM() {
    this.container.innerHTML = '';
    this.container.style.position = 'relative';
    this.container.style.userSelect = 'none';

    // Canvas element
    this.canvas = document.createElement('canvas');
    this.canvas.style.width = '100%';
    this.canvas.style.height = '100%';
    this.canvas.style.display = 'block';
    this.container.appendChild(this.canvas);
    this.ctx = this.canvas.getContext('2d');

    // Tooltip HUD
    this.hud = document.createElement('div');
    this.hud.className = 'chart-hud';
    this.hud.style.position = 'absolute';
    this.hud.style.top = '8px';
    this.hud.style.left = '12px';
    this.hud.style.pointerEvents = 'none';
    this.hud.style.fontFamily = 'ui-monospace, monospace';
    this.hud.style.fontSize = '11px';
    this.hud.style.lineHeight = '1.4';
    this.hud.style.color = '#cbd5e1';
    this.hud.style.zIndex = '10';
    this.container.appendChild(this.hud);
  }

  setupEvents() {
    window.addEventListener('resize', () => this.resize());

    this.canvas.addEventListener('mousemove', (e) => {
      const rect = this.canvas.getBoundingClientRect();
      this.mouseX = e.clientX - rect.left;
      this.mouseY = e.clientY - rect.top;
      this.updateHoverIndex();
      this.render();
    });

    this.canvas.addEventListener('mouseleave', () => {
      this.hoverIndex = -1;
      this.mouseX = -1;
      this.mouseY = -1;
      this.render();
    });
  }

  resize() {
    if (!this.canvas) return;
    const rect = this.container.getBoundingClientRect();
    this.dpr = window.devicePixelRatio || 1;
    this.width = rect.width;
    this.height = rect.height;

    this.canvas.width = Math.floor(this.width * this.dpr);
    this.canvas.height = Math.floor(this.height * this.dpr);

    this.ctx.setTransform(1, 0, 0, 1, 0, 0);
    this.ctx.scale(this.dpr, this.dpr);

    this.render();
  }

  setData(candles, quantData = null) {
    this.candles = Array.isArray(candles) ? candles : [];
    this.quant = quantData;
    this.render();
  }

  updateHoverIndex() {
    if (!this.candles.length || this.mouseX < 0) {
      this.hoverIndex = -1;
      return;
    }
    const chartWidth = this.width - 65;
    const n = this.candles.length;
    if (n === 0) return;
    const slotWidth = chartWidth / n;
    const idx = Math.floor(this.mouseX / slotWidth);
    this.hoverIndex = Math.max(0, Math.min(n - 1, idx));
  }

  render() {
    if (!this.ctx || !this.width || !this.height) return;
    const ctx = this.ctx;
    ctx.clearRect(0, 0, this.width, this.height);

    if (!this.candles.length) {
      ctx.fillStyle = '#64748b';
      ctx.font = '12px ui-monospace, monospace';
      ctx.textAlign = 'center';
      ctx.fillText('Awaiting real-time crypto feed data...', this.width / 2, this.height / 2);
      return;
    }

    // Proportions:
    // 0 -> 64% Price Chart
    // 64% -> 82% CVD & Volume Chart
    // 82% -> 100% RSI Chart
    const priceTop = 10;
    const priceHeight = Math.max(100, this.height * 0.62 - priceTop);
    const cvdTop = priceTop + priceHeight + 16;
    const cvdHeight = Math.max(40, this.height * 0.17);
    const rsiTop = cvdTop + cvdHeight + 16;
    const rsiHeight = Math.max(30, this.height - rsiTop - 20);

    const chartWidth = this.width - 65;

    this.renderPriceChart(priceTop, priceHeight, chartWidth);
    this.renderCvdChart(cvdTop, cvdHeight, chartWidth);
    this.renderRsiChart(rsiTop, rsiHeight, chartWidth);
    this.renderCrosshairAndHUD(chartWidth, priceTop, priceHeight, cvdTop, cvdHeight, rsiTop, rsiHeight);
  }

  renderPriceChart(top, height, width) {
    const ctx = this.ctx;
    const candles = this.candles;
    const n = candles.length;
    const slot = width / n;
    const barWidth = Math.max(2, slot * 0.68);

    let minP = Infinity;
    let maxP = -Infinity;
    for (const c of candles) {
      if (c.low < minP) minP = c.low;
      if (c.high > maxP) maxP = c.high;
    }

    if (this.quant && this.quant.order_blocks) {
      for (const ob of this.quant.order_blocks) {
        if (ob.low && ob.low < minP) minP = ob.low;
        if (ob.high && ob.high > maxP) maxP = ob.high;
      }
    }

    const range = (maxP - minP) || 1;
    const pad = range * 0.08;
    const yMin = minP - pad;
    const yMax = maxP + pad;
    const yRange = yMax - yMin;

    const toY = (val) => top + height - ((val - yMin) / yRange) * height;
    this.priceToY = toY;
    this.yMin = yMin;
    this.yMax = yMax;

    // Grid lines & Axis labels
    ctx.strokeStyle = this.options.gridColor;
    ctx.lineWidth = 1;
    const steps = 5;
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.fillStyle = this.options.textColor;

    for (let i = 0; i <= steps; i++) {
      const p = yMin + (yRange / steps) * i;
      const y = toY(p);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();

      const label = p >= 1000 ? p.toFixed(1) : (p >= 1 ? p.toFixed(2) : p.toFixed(4));
      ctx.fillText(label, width + 8, y + 3);
    }

    // Render ICT Order Blocks (Zones)
    if (this.quant && this.quant.order_blocks) {
      for (const ob of this.quant.order_blocks) {
        const isBull = ob.kind === 'bullish';
        const obTopY = toY(ob.high);
        const obBottomY = toY(ob.low);
        const obH = Math.max(3, obBottomY - obTopY);

        ctx.fillStyle = isBull ? 'rgba(16, 185, 129, 0.12)' : 'rgba(244, 63, 94, 0.12)';
        ctx.fillRect(0, obTopY, width, obH);

        ctx.strokeStyle = isBull ? 'rgba(16, 185, 129, 0.5)' : 'rgba(244, 63, 94, 0.5)';
        ctx.setLineDash([4, 4]);
        ctx.strokeRect(0, obTopY, width, obH);

        // Midline (Equilibrium 50%)
        const midY = (obTopY + obBottomY) / 2;
        ctx.beginPath();
        ctx.moveTo(0, midY);
        ctx.lineTo(width, midY);
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = isBull ? '#34d399' : '#fb7185';
        ctx.font = '9px ui-monospace, monospace';
        const lowStr = ob.low >= 1000 ? ob.low.toFixed(1) : ob.low.toFixed(3);
        const highStr = ob.high >= 1000 ? ob.high.toFixed(1) : ob.high.toFixed(3);
        ctx.fillText(`${isBull ? '▲ BULLISH' : '▼ BEARISH'} OB [$${lowStr} - $${highStr}]`, 8, obTopY + 11);
      }
    }

    // Render Fair Value Gaps (FVG)
    if (this.quant && this.quant.fvg) {
      for (const fvg of this.quant.fvg) {
        const isBull = fvg.kind === 'bullish';
        const fvgTopY = toY(fvg.top);
        const fvgBotY = toY(fvg.bottom);
        const fvgH = Math.max(2, fvgBotY - fvgTopY);

        ctx.fillStyle = isBull ? 'rgba(6, 182, 212, 0.12)' : 'rgba(245, 158, 11, 0.12)';
        ctx.fillRect(0, fvgTopY, width, fvgH);

        ctx.strokeStyle = isBull ? 'rgba(6, 182, 212, 0.45)' : 'rgba(245, 158, 11, 0.45)';
        ctx.setLineDash([2, 2]);
        ctx.strokeRect(0, fvgTopY, width, fvgH);
        ctx.setLineDash([]);

        ctx.fillStyle = isBull ? '#22d3ee' : '#fbbf24';
        ctx.font = '8px ui-monospace, monospace';
        const botStr = fvg.bottom >= 1000 ? fvg.bottom.toFixed(1) : fvg.bottom.toFixed(3);
        const topStr = fvg.top >= 1000 ? fvg.top.toFixed(1) : fvg.top.toFixed(3);
        ctx.fillText(`FVG [${botStr} - ${topStr}]`, width - 130, fvgTopY + 10);
      }
    }

    // Render Candlesticks
    for (let i = 0; i < n; i++) {
      const c = candles[i];
      const xCenter = i * slot + slot / 2;
      const xLeft = xCenter - barWidth / 2;
      const isUp = c.close >= c.open;
      const color = isUp ? this.options.bullColor : this.options.bearColor;

      // Wick
      ctx.strokeStyle = color;
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(xCenter, toY(c.high));
      ctx.lineTo(xCenter, toY(c.low));
      ctx.stroke();

      // Body
      const yOpen = toY(c.open);
      const yClose = toY(c.close);
      const bTop = Math.min(yOpen, yClose);
      const bH = Math.max(2, Math.abs(yClose - yOpen));

      ctx.fillStyle = color;
      ctx.fillRect(xLeft, bTop, barWidth, bH);
    }

    // Render EMAs
    if (this.quant && this.quant.emas) {
      const emas = this.quant.emas;
      for (const [key, color] of Object.entries(this.options.emaColors)) {
        const series = emas[key];
        if (!series || !series.length) continue;
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < n; i++) {
          const val = series[i];
          if (val === null || val === undefined || isNaN(val)) continue;
          const x = i * slot + slot / 2;
          const y = toY(val);
          if (!started) {
            ctx.moveTo(x, y);
            started = true;
          } else {
            ctx.lineTo(x, y);
          }
        }
        ctx.stroke();
      }
    }
  }

  renderCvdChart(top, height, width) {
    const ctx = this.ctx;
    const candles = this.candles;
    const n = candles.length;
    const slot = width / n;
    const barWidth = Math.max(1, slot * 0.6);

    ctx.fillStyle = '#64748b';
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.fillText('VOLUME & CUMULATIVE VOLUME DELTA (CVD)', 8, top + 10);

    let maxVol = 0;
    for (const c of candles) {
      if (c.volume > maxVol) maxVol = c.volume;
    }
    maxVol = maxVol || 1;

    const toVolY = (vol) => top + height - (vol / maxVol) * (height * 0.75);
    for (let i = 0; i < n; i++) {
      const c = candles[i];
      const x = i * slot + (slot - barWidth) / 2;
      const isUp = c.close >= c.open;
      const y = toVolY(c.volume);
      ctx.fillStyle = isUp ? 'rgba(16, 185, 129, 0.22)' : 'rgba(244, 63, 94, 0.22)';
      ctx.fillRect(x, y, barWidth, top + height - y);
    }

    let cvdSeries = [];
    if (this.quant && this.quant.cvd && Array.isArray(this.quant.cvd.series)) {
      cvdSeries = this.quant.cvd.series;
    } else {
      let running = 0;
      for (const c of candles) {
        const delta = (c.taker_buy_volume !== undefined)
          ? (2 * c.taker_buy_volume - c.volume)
          : (c.close >= c.open ? c.volume * 0.35 : -c.volume * 0.35);
        running += delta;
        cvdSeries.push(running);
      }
    }

    if (cvdSeries.length) {
      let minCvd = Math.min(...cvdSeries);
      let maxCvd = Math.max(...cvdSeries);
      const cvdRange = (maxCvd - minCvd) || 1;
      const toCvdY = (val) => top + height - ((val - minCvd) / cvdRange) * (height - 14) - 4;

      ctx.strokeStyle = this.options.cvdColor;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      for (let i = 0; i < n; i++) {
        const x = i * slot + slot / 2;
        const y = toCvdY(cvdSeries[i] || 0);
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      const lastCvd = cvdSeries[cvdSeries.length - 1];
      ctx.fillStyle = this.options.cvdColor;
      ctx.font = '9px ui-monospace, monospace';
      ctx.textAlign = 'left';
      const formattedCvd = Math.round(lastCvd).toLocaleString();
      ctx.fillText(`CVD: ${lastCvd > 0 ? '+' : ''}${formattedCvd}`, width + 8, top + height / 2);

      if (this.quant && this.quant.cvd && this.quant.cvd.divergence) {
        const div = this.quant.cvd.divergence;
        if (div.type === 'bullish_absorption') {
          ctx.fillStyle = '#10b981';
          ctx.font = 'bold 9px ui-monospace, monospace';
          ctx.fillText('▲ BULLISH ABSORPTION', width - 150, top + 12);
        } else if (div.type === 'bearish_exhaustion') {
          ctx.fillStyle = '#f43f5e';
          ctx.font = 'bold 9px ui-monospace, monospace';
          ctx.fillText('▼ BEARISH EXHAUSTION', width - 150, top + 12);
        }
      }
    }
  }

  renderRsiChart(top, height, width) {
    const ctx = this.ctx;
    const candles = this.candles;
    const n = candles.length;
    const slot = width / n;

    ctx.fillStyle = '#64748b';
    ctx.font = '10px ui-monospace, monospace';
    ctx.textAlign = 'left';
    ctx.fillText('WILDER RSI(14)', 8, top + 10);

    const toRsiY = (val) => top + height - (val / 100) * height;

    ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
    ctx.setLineDash([3, 3]);

    [30, 50, 70].forEach(lvl => {
      const y = toRsiY(lvl);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();

      ctx.fillStyle = lvl === 50 ? '#64748b' : (lvl === 70 ? '#f43f5e' : '#10b981');
      ctx.font = '9px ui-monospace, monospace';
      ctx.fillText(String(lvl), width + 8, y + 3);
    });
    ctx.setLineDash([]);

    let rsiSeries = [];
    if (this.quant && this.quant.rsi_series) {
      rsiSeries = this.quant.rsi_series;
    } else {
      rsiSeries = this.candles.map(() => 50.0);
    }

    if (rsiSeries.length) {
      ctx.strokeStyle = this.options.rsiColor;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      let started = false;
      for (let i = 0; i < n; i++) {
        const val = rsiSeries[i];
        if (val === null || val === undefined || isNaN(val)) continue;
        const x = i * slot + slot / 2;
        const y = toRsiY(val);
        if (!started) {
          ctx.moveTo(x, y);
          started = true;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.stroke();

      const lastRsi = rsiSeries[rsiSeries.length - 1];
      if (lastRsi !== undefined) {
        ctx.fillStyle = this.options.rsiColor;
        ctx.font = 'bold 9px ui-monospace, monospace';
        ctx.fillText(`RSI: ${lastRsi.toFixed(1)}`, width - 80, top + 10);
      }
    }
  }

  renderCrosshairAndHUD(width, priceTop, priceHeight, cvdTop, cvdHeight, rsiTop, rsiHeight) {
    const ctx = this.ctx;
    const n = this.candles.length;
    if (this.hoverIndex < 0 || this.hoverIndex >= n || this.mouseX < 0 || this.mouseX > width) {
      const last = this.candles[n - 1];
      if (last) {
        const isUp = last.close >= last.open;
        const col = isUp ? '#10b981' : '#f43f5e';
        const chg = (((last.close - last.open) / last.open) * 100).toFixed(2);
        this.hud.innerHTML = `
          <div style="display: flex; gap: 14px; flex-wrap: wrap;">
            <span>O: <b style="color:#f8fafc">${last.open}</b></span>
            <span>H: <b style="color:#f8fafc">${last.high}</b></span>
            <span>L: <b style="color:#f8fafc">${last.low}</b></span>
            <span>C: <b style="color:${col}">${last.close}</b> (${chg > 0 ? '+' : ''}${chg}%)</span>
            <span>Vol: <b style="color:#f8fafc">${Math.round(last.volume).toLocaleString()}</b></span>
            <span style="color:#06b6d4">EMA9</span>
            <span style="color:#f59e0b">EMA21</span>
            <span style="color:#a855f7">EMA50</span>
            <span style="color:#3b82f6">EMA200</span>
          </div>
        `;
      }
      return;
    }

    const slot = width / n;
    const snapX = this.hoverIndex * slot + slot / 2;
    const c = this.candles[this.hoverIndex];

    // Vertical line
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.25)';
    ctx.lineWidth = 1;
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(snapX, 0);
    ctx.lineTo(snapX, this.height);
    ctx.stroke();

    // Horizontal line in price panel
    if (this.mouseY >= priceTop && this.mouseY <= priceTop + priceHeight) {
      ctx.beginPath();
      ctx.moveTo(0, this.mouseY);
      ctx.lineTo(width, this.mouseY);
      ctx.stroke();

      if (this.priceToY && this.yMin !== undefined && this.yMax !== undefined) {
        const hoveredPrice = this.yMin + ((priceTop + priceHeight - this.mouseY) / priceHeight) * (this.yMax - this.yMin);
        ctx.fillStyle = '#0284c7';
        ctx.fillRect(width + 2, this.mouseY - 9, 60, 18);
        ctx.fillStyle = '#ffffff';
        ctx.font = '10px ui-monospace, monospace';
        ctx.textAlign = 'left';
        ctx.fillText(hoveredPrice >= 1000 ? hoveredPrice.toFixed(1) : (hoveredPrice >= 1 ? hoveredPrice.toFixed(2) : hoveredPrice.toFixed(4)), width + 6, this.mouseY + 4);
      }
    }
    ctx.setLineDash([]);

    const isUp = c.close >= c.open;
    const col = isUp ? '#10b981' : '#f43f5e';
    const chg = (((c.close - c.open) / c.open) * 100).toFixed(2);
    const dateStr = c.time ? new Date(c.time * 1000).toLocaleTimeString() : '';

    this.hud.innerHTML = `
      <div style="display: flex; gap: 14px; flex-wrap: wrap;">
        <span style="color:#38bdf8">[${dateStr}]</span>
        <span>O: <b style="color:#f8fafc">${c.open}</b></span>
        <span>H: <b style="color:#f8fafc">${c.high}</b></span>
        <span>L: <b style="color:#f8fafc">${c.low}</b></span>
        <span>C: <b style="color:${col}">${c.close}</b> (${chg > 0 ? '+' : ''}${chg}%)</span>
        <span>Vol: <b style="color:#f8fafc">${Math.round(c.volume).toLocaleString()}</b></span>
        ${c.taker_buy_volume ? `<span>Taker Delta: <b style="color:${(2*c.taker_buy_volume - c.volume) >= 0 ? '#10b981' : '#f43f5e'}">${Math.round(2*c.taker_buy_volume - c.volume).toLocaleString()}</b></span>` : ''}
      </div>
    `;
  }
}
