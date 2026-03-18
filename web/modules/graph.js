// graph.js — Knowledge Graph with snapshot, health, and advanced views
import { authFetch, API } from '../api/client.js';
import { showToast, kpPrompt } from '../utils/ui.js';

let _canvas, _ctx;
let _nodes = [], _edges = [];
let _activeView = 'snapshot';

export async function loadGraphDashboard() {
  console.log('[Graph] loadGraphDashboard');
  renderViewToolbar();
  await loadGraphSnapshot();
  await loadHealthStats();
}

// ── View Toolbar ──────────────────────────────────────────────────────────────

function renderViewToolbar() {
  const container = document.getElementById('graphCanvas');
  if (!container) return;
  // Insert toolbar above canvas if not already there
  const wrap = container.parentElement;
  if (!wrap) return;
  let toolbar = document.getElementById('graphViewToolbar');
  if (!toolbar) {
    toolbar = document.createElement('div');
    toolbar.id = 'graphViewToolbar';
    toolbar.style.cssText = 'display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;';
    wrap.insertBefore(toolbar, container);
  }
  const views = [
    { id: 'snapshot', label: '🗺️ Overview' },
    { id: 'gaps',     label: '🔍 Gaps' },
    { id: 'focus',    label: '🎯 Focus Node' },
    { id: 'impact',   label: '💥 Impact' },
    { id: 'trace',    label: '🔗 Trace' },
  ];
  toolbar.innerHTML = views.map(v => `
    <button class="secondary-btn mini ${v.id === _activeView ? 'active' : ''}"
            onclick="window.graphSwitchView('${v.id}')">${v.label}</button>
  `).join('');
}

window.graphSwitchView = async function (viewId) {
  if (viewId === 'focus') {
    const nodeId = await kpPrompt({ title: '🎯 Focus Node', message: 'Nhập node ID để xem focus:', placeholder: 'vd: entity_123' });
    if (!nodeId) return;
    _activeView = viewId;
    renderViewToolbar();
    return loadGraphFocus(nodeId);
  }
  if (viewId === 'impact') {
    const docId = await kpPrompt({ title: '💥 Impact Analysis', message: 'Nhập document ID để xem impact:', placeholder: 'vd: doc_abc' });
    if (!docId) return;
    _activeView = viewId;
    renderViewToolbar();
    return loadGraphImpact(docId);
  }
  if (viewId === 'trace') {
    const docId = await kpPrompt({ title: '🔗 Trace Root Cause', message: 'Nhập document ID hoặc Jira key để trace:', placeholder: 'vd: PROJ-123 hoặc doc_id' });
    if (!docId) return;
    _activeView = viewId;
    renderViewToolbar();
    const isJira = /^[A-Z]+-\d+$/.test(docId.trim());
    return loadGraphTrace(isJira ? null : docId, isJira ? docId : null);
  }
  _activeView = viewId;
  renderViewToolbar();
  if (viewId === 'snapshot') return loadGraphSnapshot();
  if (viewId === 'gaps') return loadGraphGaps();
};

// ── Snapshot (default canvas view) ───────────────────────────────────────────

async function loadGraphSnapshot() {
  const container = document.getElementById('graphCanvas');
  if (!container) return;
  _canvas = container;
  _ctx = _canvas.getContext ? _canvas.getContext('2d') : null;

  try {
    const res = await authFetch(`${API}/graph/snapshot?limit=150`);
    if (!res.ok) throw new Error('Graph fetch failed');
    const data = await res.json();
    _nodes = data.nodes || [];
    _edges = data.edges || [];

    _nodes.forEach(n => {
      n.x = 50 + Math.random() * (_canvas.width - 100);
      n.y = 50 + Math.random() * (_canvas.height - 100);
    });
    draw();
  } catch (e) {
    console.error('[Graph] load error:', e);
    showToast('Không tải được graph data', 'error');
  }
}

function draw() {
  if (!_ctx) return;
  _ctx.clearRect(0, 0, _canvas.width, _canvas.height);

  _ctx.strokeStyle = 'rgba(100,120,200,0.15)';
  _ctx.lineWidth = 1;
  _edges.forEach(e => {
    const s = _nodes.find(n => n.id === e.source);
    const t = _nodes.find(n => n.id === e.target);
    if (s && t) {
      _ctx.beginPath();
      _ctx.moveTo(s.x, s.y);
      _ctx.lineTo(t.x, t.y);
      _ctx.stroke();
    }
  });

  _nodes.forEach(n => {
    _ctx.beginPath();
    _ctx.arc(n.x, n.y, 6, 0, Math.PI * 2);
    _ctx.fillStyle = '#4a90e2';
    _ctx.fill();
    _ctx.strokeStyle = '#fff';
    _ctx.lineWidth = 1.5;
    _ctx.stroke();
  });
}

// ── Health Stats (Fix: BE trả flat object, không phải d.components) ──────────

export async function loadHealthStats() {
  try {
    const res = await authFetch(`${API}/graph/health`);
    if (!res.ok) return;
    const d = await res.json();

    // BE trả: { entities, relations, document_links, explicit_links, orphan_entities, documents_by_source }
    const grid = document.getElementById('graphHealthGrid');
    if (grid) {
      const totalDocs = (d.documents_by_source || []).reduce((sum, s) => sum + (s.count || 0), 0);
      const sources   = (d.documents_by_source || []).length;
      grid.innerHTML = `
        <div class="connector-summary-card"><span>Tài liệu</span><strong>${totalDocs}</strong><small>${sources} sources</small></div>
        <div class="connector-summary-card"><span>Thực thể</span><strong>${d.entities || 0}</strong><small>Entities</small></div>
        <div class="connector-summary-card"><span>Quan hệ</span><strong>${d.relations || 0}</strong><small>Relations</small></div>
        <div class="connector-summary-card"><span>Doc links</span><strong>${d.document_links || 0}</strong><small>${d.explicit_links || 0} explicit</small></div>
        ${(d.orphan_entities > 0) ? `<div class="connector-summary-card"><span>⚠️ Orphans</span><strong style="color:var(--warning,#f59e0b)">${d.orphan_entities}</strong><small>Entities cô lập</small></div>` : ''}
      `;
    }
  } catch (e) {
    console.warn('[Graph] health fail', e);
  }
}

// ── Focus View ────────────────────────────────────────────────────────────────

async function loadGraphFocus(nodeId) {
  const panel = getOrCreateResultPanel();
  panel.innerHTML = '<div class="graph-loading">Đang tải focus graph...</div>';
  try {
    const res = await authFetch(`${API}/graph/focus?node_id=${encodeURIComponent(nodeId)}&depth=2`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderGraphResult(panel, `🎯 Focus: ${nodeId}`, data);
  } catch (e) {
    panel.innerHTML = `<div class="graph-error">Lỗi: ${e.message}</div>`;
    showToast('Không tải được focus graph', 'error');
  }
}

// ── Impact View ───────────────────────────────────────────────────────────────

async function loadGraphImpact(docId) {
  const panel = getOrCreateResultPanel();
  panel.innerHTML = '<div class="graph-loading">Đang tính toán impact...</div>';
  try {
    const res = await authFetch(`${API}/graph/impact?doc_id=${encodeURIComponent(docId)}&depth=3`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderGraphResult(panel, `💥 Impact: ${docId}`, data);
  } catch (e) {
    panel.innerHTML = `<div class="graph-error">Lỗi: ${e.message}</div>`;
    showToast('Không tải được impact analysis', 'error');
  }
}

// ── Trace View ────────────────────────────────────────────────────────────────

async function loadGraphTrace(docId, jiraKey) {
  const panel = getOrCreateResultPanel();
  panel.innerHTML = '<div class="graph-loading">Đang trace root cause...</div>';
  try {
    const params = docId ? `doc_id=${encodeURIComponent(docId)}` : `jira_key=${encodeURIComponent(jiraKey)}`;
    const res = await authFetch(`${API}/graph/trace?${params}&depth=4`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderGraphResult(panel, `🔗 Trace: ${docId || jiraKey}`, data);
  } catch (e) {
    panel.innerHTML = `<div class="graph-error">Lỗi: ${e.message}</div>`;
    showToast('Không tải được trace', 'error');
  }
}

// ── Gaps View ─────────────────────────────────────────────────────────────────

async function loadGraphGaps() {
  const panel = getOrCreateResultPanel();
  panel.innerHTML = '<div class="graph-loading">Đang phân tích gaps...</div>';
  try {
    const res = await authFetch(`${API}/graph/gaps?since_days=30`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    renderGapsResult(panel, data);
  } catch (e) {
    panel.innerHTML = `<div class="graph-error">Lỗi: ${e.message}</div>`;
    showToast('Không tải được gap insights', 'error');
  }
}

// ── Render helpers ────────────────────────────────────────────────────────────

function getOrCreateResultPanel() {
  let panel = document.getElementById('graphResultPanel');
  if (!panel) {
    panel = document.createElement('div');
    panel.id = 'graphResultPanel';
    panel.style.cssText = 'margin-top:16px;padding:16px;background:var(--surface-alt,rgba(255,255,255,0.05));border-radius:8px;max-height:400px;overflow-y:auto;';
    const canvas = document.getElementById('graphCanvas');
    if (canvas && canvas.parentElement) canvas.parentElement.appendChild(panel);
    else document.body.appendChild(panel);
  }
  return panel;
}

function renderGraphResult(panel, title, data) {
  const nodes = data.nodes || [];
  const edges = data.edges || [];
  panel.innerHTML = `
    <h4 style="margin:0 0 12px;color:var(--text-primary)">${title}</h4>
    <p style="color:var(--text-secondary);margin:0 0 12px">${nodes.length} nodes · ${edges.length} edges</p>
    <div style="display:flex;flex-wrap:wrap;gap:8px;">
      ${nodes.slice(0, 40).map(n => `
        <span style="padding:3px 10px;border-radius:20px;background:rgba(74,144,226,0.2);color:#4a90e2;font-size:12px;cursor:pointer"
              onclick="window.graphSwitchView('focus')" title="${n.type || 'entity'}">${n.label || n.id}</span>
      `).join('')}
      ${nodes.length > 40 ? `<span style="color:var(--text-muted)">+${nodes.length - 40} more...</span>` : ''}
    </div>
  `;
}

function renderGapsResult(panel, data) {
  const gaps = data.gaps || data.missing_connections || [];
  const stale = data.stale_sources_30d || [];
  panel.innerHTML = `
    <h4 style="margin:0 0 12px;color:var(--text-primary)">🔍 Gap Insights</h4>
    ${stale.length ? `
      <p style="color:var(--warning,#f59e0b);margin:0 0 8px"><strong>⚠️ Stale sources (> 30 ngày):</strong></p>
      <ul style="margin:0 0 12px;padding-left:20px;color:var(--text-secondary)">
        ${stale.slice(0, 10).map(s => `<li>${s.source}: ${s.days} ngày</li>`).join('')}
      </ul>
    ` : '<p style="color:var(--text-secondary)">✅ Không có stale sources trong 30 ngày qua</p>'}
    ${gaps.length ? `
      <p style="color:var(--text-secondary);margin:0 0 8px"><strong>Gaps phát hiện:</strong></p>
      <ul style="margin:0;padding-left:20px;color:var(--text-secondary)">
        ${gaps.slice(0, 15).map(g => `<li>${JSON.stringify(g)}</li>`).join('')}
      </ul>
    ` : ''}
  `;
}
