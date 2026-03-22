'use strict';

const API_URL = '/api/scan';
const REFRESH_INTERVAL = 60_000;

let refreshTimer = null;

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(price) {
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(price);
}

function fmtTime(ts) {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

function rsiColor(rsi) {
  if (rsi >= 70) return '#dc2626';
  if (rsi <= 30) return '#16a34a';
  if (rsi >= 55) return '#f59e0b';
  if (rsi <= 45) return '#3b82f6';
  return '#6b7280';
}

function signalHtml(signal) {
  if (signal === 'BULLISH_DIV') return `<span class="signal-badge signal-badge--bullish">▲ BULLISH DIV</span>`;
  if (signal === 'BEARISH_DIV') return `<span class="signal-badge signal-badge--bearish">▼ BEARISH DIV</span>`;
  return `<span class="signal-badge signal-badge--neutral">— Neutral</span>`;
}

function macdHtml(conf) {
  if (conf === 'YES_RISING')  return `<span class="macd-conf macd-conf--yes">✓ Steigend</span>`;
  if (conf === 'YES_FALLING') return `<span class="macd-conf macd-conf--yes">✓ Fallend</span>`;
  if (conf === 'NO')          return `<span class="macd-conf macd-conf--no">✗ Nein</span>`;
  return `<span class="macd-conf macd-conf--na">—</span>`;
}

function trendHtml(trend) {
  if (trend === 'UP')       return `<span class="trend-badge trend-badge--up">↑ Aufwärts</span>`;
  if (trend === 'DOWN')     return `<span class="trend-badge trend-badge--down">↓ Abwärts</span>`;
  return `<span class="trend-badge trend-badge--sideways">→ Seitwärts</span>`;
}

function rsiBarHtml(rsi) {
  const pct = Math.min(100, Math.max(0, rsi));
  const color = rsiColor(rsi);
  return `
    <div class="rsi-wrapper">
      <div class="rsi-bar-track">
        <div class="rsi-bar-fill" style="width:${pct}%;background:${color}"></div>
      </div>
      <span class="rsi-value" style="color:${color}">${rsi.toFixed(1)}</span>
    </div>`;
}

// ── Gauge SVG ─────────────────────────────────────────────────────────────────

function makeGaugeSvg(rsi) {
  const r = 44, cx = 60, cy = 60;
  const startAngle = 210, endAngle = -30;
  const range = startAngle - endAngle;
  const angle = startAngle - (rsi / 100) * range;
  const rad = (a) => (a * Math.PI) / 180;
  const nx = cx + r * Math.cos(rad(angle));
  const ny = cy - r * Math.sin(rad(angle));

  // Track arc (full)
  const trackX1 = cx + r * Math.cos(rad(startAngle));
  const trackY1 = cy - r * Math.sin(rad(startAngle));
  const trackX2 = cx + r * Math.cos(rad(endAngle));
  const trackY2 = cy - r * Math.sin(rad(endAngle));

  // Fill arc
  const fillX1 = trackX1, fillY1 = trackY1;
  const largeArc = range - (startAngle - angle) > 180 ? 1 : 0;

  const color = rsiColor(rsi);

  return `
    <svg class="gauge-svg" width="120" height="80" viewBox="0 0 120 80">
      <!-- Track -->
      <path d="M ${trackX1.toFixed(2)} ${trackY1.toFixed(2)} A ${r} ${r} 0 1 1 ${trackX2.toFixed(2)} ${trackY2.toFixed(2)}"
        fill="none" stroke="#e4e2d9" stroke-width="8" stroke-linecap="round"/>
      <!-- Fill -->
      <path d="M ${fillX1.toFixed(2)} ${fillY1.toFixed(2)} A ${r} ${r} 0 ${largeArc} 0 ${nx.toFixed(2)} ${ny.toFixed(2)}"
        fill="none" stroke="${color}" stroke-width="8" stroke-linecap="round"/>
      <!-- Zones text -->
      <text x="18" y="76" font-size="8" fill="#6b6860" font-family="DM Mono" text-anchor="middle">30</text>
      <text x="102" y="76" font-size="8" fill="#6b6860" font-family="DM Mono" text-anchor="middle">70</text>
    </svg>`;
}

// ── Render ────────────────────────────────────────────────────────────────────

function renderTable(results) {
  const tbody = document.getElementById('tableBody');
  if (!results.length) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center;color:var(--text-3);padding:32px">Keine Daten verfügbar</td></tr>`;
    return;
  }

  tbody.innerHTML = results.map((r, i) => {
    const rowClass = r.signal === 'BULLISH_DIV' ? 'row--bullish' : r.signal === 'BEARISH_DIV' ? 'row--bearish' : '';
    return `
      <tr class="${rowClass}" style="animation-delay:${i * 0.05}s">
        <td><span class="tf-badge">${r.timeframe}</span></td>
        <td><span class="price-cell">${fmt(r.price)}</span></td>
        <td>${rsiBarHtml(r.rsi)}</td>
        <td>${signalHtml(r.signal)}</td>
        <td>${macdHtml(r.macd_conf)}</td>
        <td>${trendHtml(r.trend)}</td>
        <td><span class="detail-text">${r.details}</span></td>
      </tr>`;
  }).join('');
}

function renderCards(results) {
  const prices = results.map(r => r.price).filter(Boolean);
  const price = prices[0] ?? 0;
  const bullish = results.filter(r => r.signal === 'BULLISH_DIV').length;
  const bearish = results.filter(r => r.signal === 'BEARISH_DIV').length;
  const active = bullish + bearish;

  document.getElementById('currentPrice').textContent = fmt(price);
  document.getElementById('priceChange').textContent = 'BTCUSDT · Binance';
  document.getElementById('activeSignals').textContent = active;
  document.getElementById('bullishCount').textContent = bullish;
  document.getElementById('bearishCount').textContent = bearish;
}

function renderPills(results) {
  const container = document.getElementById('timeframePills');
  container.innerHTML = results.map(r => {
    const cls = r.signal === 'BULLISH_DIV' ? 'pill--bullish'
               : r.signal === 'BEARISH_DIV' ? 'pill--bearish' : 'pill--neutral';
    return `<span class="pill ${cls}">${r.timeframe}</span>`;
  }).join('');
}

function renderGauges(results) {
  const section = document.getElementById('gaugeSection');
  section.innerHTML = results.map(r => `
    <div class="gauge-card">
      <div class="gauge-tf">${r.timeframe}</div>
      ${makeGaugeSvg(r.rsi)}
      <div class="gauge-rsi-value" style="color:${rsiColor(r.rsi)}">${r.rsi.toFixed(1)}</div>
      <div class="gauge-rsi-label">RSI</div>
    </div>
  `).join('');
}

// ── Fetch & update ────────────────────────────────────────────────────────────

async function fetchData() {
  const btn = document.getElementById('refreshBtn');
  btn.classList.add('loading');

  try {
    const res = await fetch(API_URL);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const json = await res.json();
    const results = json.results ?? [];

    renderCards(results);
    renderTable(results);
    renderPills(results);
    renderGauges(results);

    document.getElementById('lastUpdated').textContent = 'Aktualisiert: ' + fmtTime(json.last_updated);
  } catch (err) {
    console.error('Fetch error:', err);
    document.getElementById('lastUpdated').textContent = 'Fehler beim Laden';
  } finally {
    btn.classList.remove('loading');
  }

  clearTimeout(refreshTimer);
  refreshTimer = setTimeout(fetchData, REFRESH_INTERVAL);
}

// ── Init ──────────────────────────────────────────────────────────────────────
fetchData();
