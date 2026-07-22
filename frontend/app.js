/* AMMS v2 Dashboard — Premium real-time UI */

const API = '';
let ws = null, wsReconnectTimer = null, isRunning = false;
let charts = {};
let allAgents = [];
let txnIdsSeen = new Set();
let currentTab = 'overview';

const categoryColors = {
  Electronics: '#93c5fd',
  Clothing: '#f9a8d4',
  Food: '#86efac',
  Books: '#fde047',
  Home: '#fdba74'
};
const categoryGradient = {
  Electronics: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
  Clothing: 'linear-gradient(135deg, #ec4899, #be185d)',
  Food: 'linear-gradient(135deg, #22c55e, #15803d)',
  Books: 'linear-gradient(135deg, #eab308, #a16207)',
  Home: 'linear-gradient(135deg, #f97316, #c2410c)'
};

// ── Panel Controls (collapse / reorder) ──
function togglePanel(panel) {
  const el = document.querySelector(`.stack-panel[data-panel="${panel}"]`);
  if (!el) return;
  el.classList.toggle('collapsed');
  const btn = el.querySelector('.stack-btn.toggle');
  if (btn) btn.textContent = el.classList.contains('collapsed') ? '+' : '−';
}

function movePanel(panel, direction) {
  const panels = [...document.querySelectorAll('.stack-panel')];
  if (panels.length !== 3) return;
  const orders = panels.map(p => parseInt(p.style.order || 1));
  const idx = panels.findIndex(p => p.dataset.panel === panel);
  if (idx < 0) return;
  const targetIdx = idx + direction;
  if (targetIdx < 0 || targetIdx >= panels.length) return;
  // Swap orders
  const temp = orders[idx];
  orders[idx] = orders[targetIdx];
  orders[targetIdx] = temp;
  panels.forEach((p, i) => { p.style.order = orders[i]; });
}

// ── Initialization ──
document.addEventListener('DOMContentLoaded', () => {
  initCharts();
  connectWebSocket();
  loadPresets();
  refreshAll();
  loadAgents();
  setInterval(refreshEvents, 5000);
});

// ── Tab Switching ──
function switchTab(tab) {
  currentTab = tab;
  document.querySelectorAll('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.tab === tab));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.toggle('active', t.id === 'tab-' + tab));
  Object.values(charts).forEach(c => { if (c && c.resize) c.resize(); });
  if (tab === 'agents') loadAgents();
  if (tab === 'analytics') refreshAnalyticsTab();
  if (tab === 'events') refreshEvents();
}

// ── Helpers ──
function initials(str) {
  if (!str) return '?';
  return str.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase();
}
function hashColor(str) {
  let h = 0;
  for (let i = 0; i < str.length; i++) h = str.charCodeAt(i) + ((h << 5) - h);
  const hue = Math.abs(h % 360);
  return `linear-gradient(135deg, hsl(${hue}, 70%, 60%), hsl(${hue + 40}, 70%, 45%))`;
}
function categoryClass(cat) {
  const key = (cat || '').toLowerCase();
  return ['electronics', 'clothing', 'food', 'books', 'home'].includes(key) ? key : 'home';
}

// ── Charts ──
function hexToRgba(hex, alpha) {
  const c = hex.replace('#', '');
  const r = parseInt(c.substring(0, 2), 16);
  const g = parseInt(c.substring(2, 4), 16);
  const b = parseInt(c.substring(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

function makeChart(canvasId, label, color) {
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return null;
  const gradient = ctx.createLinearGradient(0, 0, 0, 240);
  gradient.addColorStop(0, hexToRgba(color, 0.35));
  gradient.addColorStop(0.6, hexToRgba(color, 0.08));
  gradient.addColorStop(1, hexToRgba(color, 0.0));
  return new Chart(ctx, {
    type: 'line',
    data: { labels: [], datasets: [
      { label, data: [], borderColor: color, backgroundColor: gradient,
        borderWidth: 3, fill: true, tension: 0.45,
        pointRadius: 0, pointHoverRadius: 6,
        pointHoverBackgroundColor: '#0f111a', pointHoverBorderColor: color,
        pointHoverBorderWidth: 3 },
      { label: label + ' glow', data: [], borderColor: hexToRgba(color, 0.25),
        borderWidth: 9, fill: false, tension: 0.45,
        pointRadius: 0, pointHoverRadius: 0 }
    ]},
    options: {
      responsive: true, maintainAspectRatio: false,
      animation: { duration: 300, easing: 'easeOutQuart' },
      interaction: { mode: 'index', intersect: false },
      scales: {
        x: { ticks: { color: '#6b7185', maxTicksLimit: 8, font: { size: 10, family: 'Inter' } }, grid: { color: '#ffffff08' }, border: { display: false } },
        y: { ticks: { color: '#6b7185', font: { size: 10, family: 'Inter' } }, grid: { color: '#ffffff08', tickLength: 0 }, border: { display: false }, beginAtZero: false }
      },
      plugins: { legend: { display: false }, tooltip: {
        backgroundColor: '#12141c', borderColor: color, borderWidth: 1,
        padding: 10, cornerRadius: 8, displayColors: false,
        titleColor: '#e2e5ec', bodyColor: '#a0a5b8', titleFont: { size: 12, weight: 600 }, bodyFont: { size: 12 },
        callbacks: { label: ctx => `${label}: ${Number(ctx.raw).toFixed(2)}` }
      }}
    }
  });
}

function makeBarChart(canvasId, label) {
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return null;
  const colors = ['#7c6af0','#2dd4bf','#f87171','#fbbf24','#60a5fa','#f472b6','#34d399','#a78bfa','#fb923c','#22d3ee'];
  const grad = ctx.createLinearGradient(0, 0, 0, 220);
  grad.addColorStop(0, 'rgba(124,106,240,0.9)');
  grad.addColorStop(1, 'rgba(124,106,240,0.35)');
  return new Chart(ctx, {
    type: 'bar',
    data: { labels: [], datasets: [{ label, data: [],
      backgroundColor: colors.map(c => {
        const g = ctx.createLinearGradient(0, 0, 0, 220);
        g.addColorStop(0, hexToRgba(c, 0.95));
        g.addColorStop(1, hexToRgba(c, 0.45));
        return g;
      }),
      borderColor: 'transparent', borderRadius: 8, borderSkipped: false,
      barThickness: 'flex', maxBarThickness: 36 }] },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 350, easing: 'easeOutQuart' },
      scales: {
        x: { ticks: { color: '#6b7185', font: { size: 10, family: 'Inter' } }, grid: { display: false }, border: { display: false } },
        y: { ticks: { color: '#6b7185', font: { size: 10, family: 'Inter' } }, grid: { color: '#ffffff08' }, border: { display: false }, beginAtZero: true }
      },
      plugins: { legend: { display: false }, tooltip: {
        backgroundColor: '#12141c', borderColor: '#7c6af0', borderWidth: 1,
        padding: 10, cornerRadius: 8, displayColors: false,
        titleColor: '#e2e5ec', bodyColor: '#a0a5b8',
        callbacks: { label: ctx => `${ctx.label}: $${Number(ctx.raw).toFixed(0)}` }
      }}
    }
  });
}

function makePieChart(canvasId) {
  const ctx = document.getElementById(canvasId)?.getContext('2d');
  if (!ctx) return null;
  const colors = ['#7c6af0','#2dd4bf','#f87171','#fbbf24','#60a5fa'];
  return new Chart(ctx, {
    type: 'doughnut',
    data: { labels: [], datasets: [{ data: [],
      backgroundColor: colors.map((c, i) => {
        const g = ctx.createLinearGradient(0, i * 30, 80, i * 30 + 80);
        g.addColorStop(0, c);
        g.addColorStop(1, hexToRgba(c, 0.65));
        return g;
      }),
      borderColor: '#12141c', borderWidth: 3, hoverOffset: 8,
      borderRadius: 4 }] },
    options: {
      responsive: true, maintainAspectRatio: false, cutout: '62%',
      animation: { animateScale: true, animateRotate: true, duration: 500 },
      plugins: { legend: { position: 'bottom', labels: { color: '#a0a5b8', font: { size: 11, family: 'Inter' }, padding: 16, usePointStyle: true, pointStyle: 'circle' } },
        tooltip: {
          backgroundColor: '#12141c', borderColor: '#7c6af0', borderWidth: 1,
          padding: 10, cornerRadius: 8, displayColors: true,
          titleColor: '#e2e5ec', bodyColor: '#a0a5b8',
          callbacks: { label: ctx => `${ctx.label}: ${Number(ctx.raw).toFixed(0)} sales` }
        }}
    }
  });
}

function initCharts() {
  charts.price = makeChart('chartPrice', 'Avg Price', '#7c6af0');
  charts.gini = makeChart('chartGini', 'Gini', '#fb923c');
  charts.volume = makeChart('chartVolume', 'Volume', '#34d399');
  charts.wealth = makeBarChart('chartWealth', 'Total Wealth');
  charts.category = makePieChart('chartCategory');
}

function updateLineChart(chart, labels, data, maxPoints = 60) {
  if (!chart) return;
  const trimmed = data.slice(-maxPoints);
  chart.data.labels = labels.slice(-maxPoints);
  chart.data.datasets[0].data = trimmed;
  if (chart.data.datasets[1]) chart.data.datasets[1].data = trimmed;
  chart.update('none');
}

// ── WebSocket ──
function connectWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = `${protocol}//${window.location.host}/ws`;

  if (wsReconnectTimer) { clearInterval(wsReconnectTimer); wsReconnectTimer = null; }

  let socket;
  try { socket = new WebSocket(wsUrl); } catch (e) {
    console.warn('WebSocket unavailable, polling');
    startPolling(); return;
  }
  ws = socket;

  const send = (msg) => { if (socket.readyState === WebSocket.OPEN) socket.send(JSON.stringify(msg)); };

  socket.onopen = () => {
    console.log('WebSocket connected');
    const dot = document.getElementById('wsStatus');
    const label = document.getElementById('wsLabel');
    if (dot) dot.className = 'status-dot connected';
    if (label) label.textContent = 'Live';
    send({ action: 'ping' });
  };

  socket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'pong') return;
      if (data.type === 'tick_update') handleLiveUpdate(data);
    } catch (e) { console.error('WS parse error:', e); }
  };

  socket.onclose = () => {
    const dot = document.getElementById('wsStatus');
    const label = document.getElementById('wsLabel');
    if (dot) dot.className = 'status-dot disconnected';
    if (label) label.textContent = 'Reconnecting...';
    if (!wsReconnectTimer) {
      wsReconnectTimer = setInterval(() => { console.log('Reconnecting...'); connectWebSocket(); }, 3000);
    }
  };

  socket.onerror = (err) => console.error('WS error:', err);
}

function startPolling() { setInterval(refreshAll, 2000); }

// ── Live Update Handler ──
function handleLiveUpdate(data) {
  document.getElementById('tickNum').textContent = data.tick;
  const footerTick = document.getElementById('footerTick');
  if (footerTick) footerTick.textContent = 'Tick ' + data.tick;

  // Metrics
  setMetric('metricConsumer', data.total_agents || 0);
  setMetric('metricProducts', data.total_products || 0);
  setMetric('metricTxns', data.total_transactions || 0);
  setMetric('metricGini', (data.gini || 0).toFixed(4));
  setMetric('metricPrice', '$' + ((data.avg_price || 0)).toFixed(2));

  // Charts
  if (data.price_point) {
    updateLineChart(charts.price,
      [...(charts.price.data.labels || []), 'T' + data.price_point.tick],
      [...(charts.price.data.datasets[0].data || []), data.price_point.avg_price]);
  }
  if (data.gini_point) {
    updateLineChart(charts.gini,
      [...(charts.gini.data.labels || []), 'T' + data.gini_point.tick],
      [...(charts.gini.data.datasets[0].data || []), data.gini_point.gini]);
  }

  // Top products
  if (data.top_products) updateTopProducts(data.top_products);

  // Transaction feed
  if (data.recent_transactions) appendTransactions(data.recent_transactions);

  // Reviews
  if (data.reviews) appendReviews(data.reviews);

  // Events
  if (data.active_events) updateActiveEvents(data.active_events);

  // Tick flash
  const tickEl = document.getElementById('tickNum');
  if (tickEl) { tickEl.classList.add('tick-flash'); setTimeout(() => tickEl.classList.remove('tick-flash'), 400); }
}

function setMetric(id, value) {
  const el = document.getElementById(id);
  if (!el) return;
  const val = el.querySelector('.metric-value');
  if (val) val.textContent = value;
}

function appendTransactions(txns) {
  const feed = document.getElementById('txnFeed');
  if (!feed) return;
  const newTxns = txns.filter(t => !txnIdsSeen.has(t.id));
  if (newTxns.length === 0) return;

  const html = newTxns.slice(0, 15).map(t => {
    txnIdsSeen.add(t.id);
    return `<div class="txn-item">
      <div class="txn-avatar" style="background:${hashColor(t.agent)}">${initials(t.agent)}</div>
      <div class="txn-body">
        <div class="txn-line">
          <span class="txn-agent">${esc(t.agent)}</span>
          <span class="txn-action">bought</span>
          <span class="txn-product">${esc(t.product)}</span>
        </div>
        <div class="txn-meta">Just now</div>
      </div>
      <span class="txn-price">$${t.price.toFixed(2)}</span>
      <span class="txn-tick">T${t.tick}</span>
    </div>`;
  }).join('');

  feed.insertAdjacentHTML('afterbegin', html);
  while (feed.children.length > 50) feed.lastChild.remove();
  if (txnIdsSeen.size > 500) { const arr = [...txnIdsSeen]; txnIdsSeen = new Set(arr.slice(-300)); }
}

function appendReviews(reviews) {
  const feed = document.getElementById('reviewFeed');
  if (!feed) return;
  const existingIds = new Set([...feed.querySelectorAll('.review-item')].map(el => el.dataset.id));
  const newItems = reviews.filter(r => !existingIds.has(String(r.id)));
  if (newItems.length === 0) return;

  const html = newItems.map(r => `
    <div class="review-item" data-id="${r.id}">
      <div class="review-header">
        <span class="review-product">${esc(r.product_name)}</span>
        <span class="review-stars">${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</span>
      </div>
      ${r.text ? `<div class="review-text">${esc(r.text)}</div>` : ''}
      <div class="review-agent">— ${esc(r.agent_name)} · T${r.tick}</div>
    </div>
  `).join('');
  feed.insertAdjacentHTML('afterbegin', html);
  while (feed.children.length > 50) feed.lastChild.remove();
}

function updateTopProducts(products) {
  const tbody = document.querySelector('#tableProducts tbody');
  if (!tbody) return;
  tbody.innerHTML = products.map(p => `
    <tr>
      <td>
        <div class="product-cell">
          <div class="product-thumb" style="background:${categoryGradient[p.category] || categoryGradient.Home}">${initials(p.name)}</div>
          <span class="product-name">${esc(p.name)}</span>
        </div>
      </td>
      <td><span class="category-tag ${categoryClass(p.category)}">${esc(p.category)}</span></td>
      <td>$${p.current_price.toFixed(2)}</td>
      <td class="num"><span class="sold-badge">${p.sales_velocity}</span></td>
    </tr>
  `).join('');
}

function updateActiveEvents(events) {
  const el = document.getElementById('activeEvents');
  if (!el) return;
  if (!events || events.length === 0) {
    el.innerHTML = '<span style="color:#6b7185">No active events</span>';
    return;
  }
  el.innerHTML = events.map(e => `
    <div class="active-event">
      <span class="ae-icon">${e.data?.icon || '📢'}</span>
      <span>${esc(e.description)}</span>
      <span class="ae-remaining">${e.duration} ticks</span>
    </div>
  `).join('');
}

// ── Full Refresh ──
async function refreshAll() {
  try {
    const [dash, status] = await Promise.all([
      fetch(`${API}/analytics/dashboard`).then(r => r.json()),
      fetch(`${API}/simulation/status`).then(r => r.json()),
    ]);
    updateMetrics(dash, status);
    updateChartsFull(dash);
    updateTopProducts(dash.top_products || []);
    updateReviewsBulk(dash.recent_reviews || []);
    updateTransactionsBulk(dash.recent_transactions || []);
    updateUIState(status);
    if (currentTab === 'analytics') refreshAnalyticsTabData(dash);
  } catch (e) { console.error('Refresh error:', e); }
}

function updateMetrics(d, s) {
  setMetric('metricConsumer', d.total_agents || 0);
  setMetric('metricMerchant', s.merchants_count || 0);
  setMetric('metricProducts', d.total_products || 0);
  setMetric('metricTxns', d.total_transactions || 0);
  setMetric('metricVolume', '$' + ((d.total_volume || 0)).toLocaleString(undefined, {maximumFractionDigits: 0}));
  setMetric('metricGini', ((d.current_gini || 0)).toFixed(4));
  setMetric('metricPrice', '$' + ((d.avg_price_index || 0)).toFixed(2));
}

function updateChartsFull(d) {
  if (d.price_trend) updateLineChart(charts.price, d.price_trend.map(p => 'T' + p.tick), d.price_trend.map(p => p.avg_price));
  if (d.gini_trend) updateLineChart(charts.gini, d.gini_trend.map(p => 'T' + p.tick), d.gini_trend.map(p => p.gini));
  if (d.volume_trend) updateLineChart(charts.volume, d.volume_trend.map(p => 'T' + p.tick), d.volume_trend.map(p => p.volume));
}

function updateTransactionsBulk(txns) {
  const feed = document.getElementById('txnFeed');
  if (!feed || !txns) return;
  feed.innerHTML = txns.slice(0, 30).map(t => {
    txnIdsSeen.add(t.id);
    return `<div class="txn-item">
      <div class="txn-avatar" style="background:${hashColor(t.agent)}">${initials(t.agent)}</div>
      <div class="txn-body">
        <div class="txn-line">
          <span class="txn-agent">${esc(t.agent)}</span>
          <span class="txn-action">bought</span>
          <span class="txn-product">${esc(t.product)}</span>
        </div>
        <div class="txn-meta">T${t.tick}</div>
      </div>
      <span class="txn-price">$${t.price.toFixed(2)}</span>
    </div>`;
  }).join('');
}

function updateReviewsBulk(reviews) {
  const feed = document.getElementById('reviewFeed');
  if (!feed || !reviews) return;
  feed.innerHTML = reviews.map(r => `
    <div class="review-item" data-id="${r.id}">
      <div class="review-header">
        <span class="review-product">${esc(r.product_name)}</span>
        <span class="review-stars">${'★'.repeat(r.rating)}${'☆'.repeat(5 - r.rating)}</span>
      </div>
      ${r.text ? `<div class="review-text">${esc(r.text)}</div>` : ''}
      <div class="review-agent">— ${esc(r.agent_name)} · T${r.tick}</div>
    </div>
  `).join('');
}

// ── UI State ──
function updateUIState(s) {
  isRunning = s?.running || false;
  const badge = document.getElementById('simStatus');
  if (badge) {
    badge.textContent = s?.running ? 'RUNNING' : 'STOPPED';
    badge.className = 'sim-badge ' + (s?.running ? 'running' : 'stopped');
  }
  document.getElementById('tickNum').textContent = s?.tick || 0;
  const footerTick = document.getElementById('footerTick');
  if (footerTick) footerTick.textContent = 'Tick ' + (s?.tick || 0);
  const footerStatus = document.getElementById('footerStatus');
  if (footerStatus) footerStatus.textContent = s?.running ? 'Running' : 'Paused';
  if (s?.tick_speed_ms) {
    document.getElementById('speedDisplay').textContent = (s.tick_speed_ms / 1000).toFixed(1) + 's';
  }
  if (s?.active_events) updateActiveEvents(s.active_events);
}

// ── Simulation Controls ──
async function simControl(action) {
  const badge = document.getElementById('simStatus');
  try {
    if (action === 'step') {
      const r = await fetch(`${API}/simulation/step`, { method: 'POST' });
      const d = await r.json();
      badge.textContent = `T${d.tick}`;
    } else if (action === 'start' || action === 'stop') {
      const r = await fetch(`${API}/simulation/${action}`, { method: 'POST' });
      await r.json();
    } else if (action === 'reset') {
      if (!confirm('Reset ALL data? This cannot be undone.')) return;
      await fetch(`${API}/simulation/reset`, { method: 'POST' });
      Object.values(charts).forEach(c => { if (c) { c.data.labels = []; c.data.datasets.forEach(ds => ds.data = []); c.update(); } });
      document.getElementById('txnFeed').innerHTML = '';
      document.getElementById('reviewFeed').innerHTML = '';
      txnIdsSeen.clear();
    }
    setTimeout(() => { refreshAll(); updateUIStateBrief(); }, 300);
  } catch (e) { console.error('Control error:', e); }
}

async function updateUIStateBrief() {
  try {
    const r = await fetch(`${API}/simulation/status`);
    const s = await r.json();
    updateUIState(s);
  } catch (e) {}
}

function setSpeed(ms) {
  document.getElementById('speedDisplay').textContent = (ms / 1000).toFixed(1) + 's';
  fetch(`${API}/simulation/speed?ms=${ms}`, { method: 'POST' }).catch(() => {});
}

// ── Presets ──
async function loadPresets() {
  try {
    const r = await fetch(`${API}/simulation/presets`);
    const presets = await r.json();
    const sel = document.getElementById('presetSelect');
    presets.forEach(p => {
      const opt = document.createElement('option');
      opt.value = p.id; opt.textContent = p.label;
      sel.appendChild(opt);
    });
  } catch (e) { console.error('Presets load error:', e); }
}

async function applyPreset(id) {
  if (!id) return;
  if (!confirm(`Apply preset "${id}"? This resets all data.`)) {
    document.getElementById('presetSelect').value = '';
    return;
  }
  try {
    const r = await fetch(`${API}/simulation/presets/${id}`, { method: 'POST' });
    const d = await r.json();
    document.getElementById('presetSelect').value = '';
    Object.values(charts).forEach(c => { if (c) { c.data.labels = []; c.data.datasets.forEach(ds => ds.data = []); c.update(); } });
    document.getElementById('txnFeed').innerHTML = '';
    document.getElementById('reviewFeed').innerHTML = '';
    txnIdsSeen.clear();
    setTimeout(refreshAll, 500);
    setTimeout(loadAgents, 600);
    console.log('Preset applied:', d);
  } catch (e) { console.error('Preset apply error:', e); }
}

// ── Agents ──
async function loadAgents() {
  try {
    const r = await fetch(`${API}/agents/consumers`);
    allAgents = await r.json();
    document.getElementById('agentCount').textContent = `(${allAgents.length})`;
    renderAgents(allAgents);
  } catch (e) { console.error('Agents load error:', e); }
}

function filterAgents() {
  const search = (document.getElementById('agentSearch')?.value || '').toLowerCase();
  const sort = document.getElementById('agentSort')?.value || 'balance-desc';
  let filtered = allAgents.filter(a => a.name.toLowerCase().includes(search));
  if (sort === 'balance-desc') filtered.sort((a, b) => b.balance - a.balance);
  else if (sort === 'balance-asc') filtered.sort((a, b) => a.balance - b.balance);
  else if (sort === 'name') filtered.sort((a, b) => a.name.localeCompare(b.name));
  renderAgents(filtered);
}

function renderAgents(agents) {
  const grid = document.getElementById('agentGrid');
  if (!grid) return;
  grid.innerHTML = agents.map(a => `
    <div class="agent-card">
      <div class="agent-card-header">
        <span class="ac-name">${esc(a.name)}</span>
        <span class="ac-balance">$${a.balance.toFixed(2)}</span>
      </div>
      ${a.purchase_count ? `<div class="ac-purchases">${a.purchase_count} purchases</div>` : '<div class="ac-purchases">No purchases yet</div>'}
      <div class="trait-row"><span class="trait-name">Price</span><div class="trait-bar-bg"><div class="trait-bar-fill ps" style="width:${(a.price_sensitivity||0)*100}%"></div></div></div>
      <div class="trait-row"><span class="trait-name">Impulse</span><div class="trait-bar-bg"><div class="trait-bar-fill im" style="width:${(a.impulsiveness||0)*100}%"></div></div></div>
      <div class="trait-row"><span class="trait-name">Risk</span><div class="trait-bar-bg"><div class="trait-bar-fill rt" style="width:${(a.risk_tolerance||0)*100}%"></div></div></div>
      <div class="trait-row"><span class="trait-name">Loyalty</span><div class="trait-bar-bg"><div class="trait-bar-fill bl" style="width:${(a.brand_loyalty||0)*100}%"></div></div></div>
      <div class="trait-row"><span class="trait-name">Trend</span><div class="trait-bar-bg"><div class="trait-bar-fill ta" style="width:${(a.trend_alignment||0)*100}%"></div></div></div>
    </div>
  `).join('');
}

// ── Analytics Tab ──
async function refreshAnalyticsTab() {
  try {
    const dash = await fetch(`${API}/analytics/dashboard`).then(r => r.json());
    refreshAnalyticsTabData(dash);
  } catch (e) { console.error(e); }
}

function refreshAnalyticsTabData(d) {
  // Wealth distribution
  if (d.wealth_distribution && charts.wealth) {
    const wd = d.wealth_distribution;
    charts.wealth.data.labels = wd.deciles.map(dc => 'D' + dc.decile);
    charts.wealth.data.datasets[0].data = wd.deciles.map(dc => dc.total);
    charts.wealth.update();
  }

  // Category breakdown
  if (d.category_breakdown && charts.category) {
    const cb = d.category_breakdown;
    charts.category.data.labels = cb.map(c => c.category);
    charts.category.data.datasets[0].data = cb.map(c => c.total_sales);
    charts.category.update();
  }

  // Leaderboard tables
  if (d.agent_leaderboard) {
    const lb = d.agent_leaderboard;
    const richestTbody = document.querySelector('#tableRichest tbody');
    if (richestTbody) {
      richestTbody.innerHTML = lb.richest_consumers.map((a, i) => `
        <tr><td class="num">${i + 1}</td><td>${esc(a.name)}</td><td class="num">$${a.balance.toFixed(2)}</td><td class="num">${a.purchases}</td><td class="num">$${a.spent.toFixed(2)}</td></tr>
      `).join('');
    }
    const activeTbody = document.querySelector('#tableActive tbody');
    if (activeTbody) {
      activeTbody.innerHTML = lb.most_active.map((a, i) => `
        <tr><td class="num">${i + 1}</td><td>${esc(a.name)}</td><td class="num">${a.purchases}</td><td class="num">$${a.spent.toFixed(2)}</td></tr>
      `).join('');
    }
  }

  // Category table
  if (d.category_breakdown) {
    const catTbody = document.querySelector('#tableCategories tbody');
    if (catTbody) {
      catTbody.innerHTML = d.category_breakdown.map(c => `
        <tr><td>${c.category}</td><td class="num">${c.product_count}</td><td class="num">${c.total_sales}</td><td class="num">$${c.avg_price}</td></tr>
      `).join('');
    }
  }
}

// ── Events Tab ──
async function refreshEvents() {
  try {
    const [status, events] = await Promise.all([
      fetch(`${API}/simulation/status`).then(r => r.json()),
      fetch(`${API}/simulation/events`).then(r => r.json()),
    ]);
    if (status.active_events) updateActiveEvents(status.active_events);
    if (events.history) {
      const timeline = document.getElementById('eventTimeline');
      if (timeline) {
        timeline.innerHTML = events.history.slice().reverse().map(e => `
          <div class="event-entry">
            <span class="ev-icon">${e.icon || '📢'}</span>
            <span class="ev-tick">T${e.tick}</span>
            <span class="ev-desc">${esc(e.description)}</span>
            <span class="ev-cat">${esc(e.category)}</span>
          </div>
        `).join('');
      }
    }
  } catch (e) { console.error('Events error:', e); }
}

// ── Utilities ──
function esc(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// Periodic full refresh
setInterval(refreshAll, 10000);
