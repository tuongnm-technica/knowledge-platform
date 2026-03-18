// graph.js — Knowledge Graph with snapshot, health, and advanced views
import { authFetch, API } from '../api/client.js';
import { showToast, kpPrompt } from '../utils/ui.js';

let _canvas, _ctx;
let _nodes = [], _edges = [];
let _activeView = 'snapshot';
let _selectedNode = null;
let _zoomLevel = 1;
let _panX = 0, _panY = 0;
let _isDragging = false;
let _draggedNode = null;
let _searchTerm = '';

export async function loadGraphDashboard() {
  console.log('[Graph] loadGraphDashboard');
  renderViewToolbar();
  await loadGraphSnapshot();
  await loadHealthStats();
  setupCanvasInteraction();
}

// ── View Toolbar ──────────────────────────────────────────────────────────────

function renderViewToolbar() {
  const container = document.getElementById('graphCanvas');
  if (!container) return;
  const wrap = container.parentElement;
  if (!wrap) return;
  let toolbar = document.getElementById('graphViewToolbar');
  if (!toolbar) {
    toolbar = document.createElement('div');
    toolbar.id = 'graphViewToolbar';
    toolbar.className = 'graph-view-toolbar';
    wrap.insertBefore(toolbar, container);
  }
  const views = [
    { id: 'snapshot', label: '🗺️ Overview' },
    { id: 'gaps', label: '🔍 Gaps' },
    { id: 'focus', label: '🎯 Focus Node' },
    { id: 'impact', label: '💥 Impact' },
    { id: 'trace', label: '🔗 Trace' },
  ];
  toolbar.innerHTML = views.map(v => `
    <button class="graph-view-btn ${v.id === _activeView ? 'active' : ''}"
            onclick="window.graphSwitchView('${v.id}')">${v.label}</button>
  `).join('');
}

window.graphSwitchView = async function (viewId) {
  if (viewId === 'focus') {
    const nodeId = await kpPrompt({ 
      title: '🎯 Focus Node', 
      message: 'Nhập node ID để xem focus:', 
      placeholder: 'vd: entity_123' 
    });
    if (!nodeId) return;
    _activeView = viewId;
    renderViewToolbar();
    return loadGraphFocus(nodeId);
  }
  if (viewId === 'impact') {
    const docId = await kpPrompt({ 
      title: '💥 Impact Analysis', 
      message: 'Nhập document ID để xem impact:', 
      placeholder: 'vd: doc_abc' 
    });
    if (!docId) return;
    _activeView = viewId;
    renderViewToolbar();
    return loadGraphImpact(docId);
  }
  if (viewId === 'trace') {
    const docId = await kpPrompt({ 
      title: '🔗 Trace Root Cause', 
      message: 'Nhập document ID hoặc Jira key:', 
      placeholder: 'vd: PROJ-123 hoặc doc_id' 
    });
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

// ── Snapshot (Canvas + Interactive) ───────────────────────────────────────────

async function loadGraphSnapshot() {
  const container = document.getElementById('graphCanvas');
  if (!container) return;
  _canvas = container;
  _ctx = _canvas.getContext ? _canvas.getContext('2d') : null;
  _selectedNode = null;
  _searchTerm = '';

  showGraphLoading();
  try {
    const res = await authFetch(`${API}/graph/snapshot?limit=150`);
    if (!res.ok) throw new Error('Graph fetch failed');
    const data = await res.json();
    _nodes = data.nodes || [];
    _edges = data.edges || [];

    // Initialize positions with force-directed layout simulation
    initializeNodePositions();
    runForceSimulation(10);  // 10 iterations
    draw();
    hideGraphLoading();
  } catch (e) {
    console.error('[Graph] load error:', e);
    showToast('Không tải được graph data', 'error');
    hideGraphLoading();
  }
}

function initializeNodePositions() {
  const width = _canvas.width;
  const height = _canvas.height;
  const center_x = width / 2;
  const center_y = height / 2;
  const radius = Math.min(width, height) / 3;

  _nodes.forEach((n, i) => {
    const angle = (i / _nodes.length) * Math.PI * 2;
    n.x = center_x + Math.cos(angle) * radius + (Math.random() - 0.5) * 40;
    n.y = center_y + Math.sin(angle) * radius + (Math.random() - 0.5) * 40;
    n.vx = 0;
    n.vy = 0;
  });
}

function runForceSimulation(iterations) {
  const k = 50;  // Repulsion factor
  const l = 80;  // Target link distance
  const damping = 0.9;

  for (let iter = 0; iter < iterations; iter++) {
    // Repulsion forces
    for (let i = 0; i < _nodes.length; i++) {
      for (let j = i + 1; j < _nodes.length; j++) {
        const dx = _nodes[j].x - _nodes[i].x;
        const dy = _nodes[j].y - _nodes[i].y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = k / (dist * dist);
        _nodes[i].vx -= (force * dx) / dist;
        _nodes[i].vy -= (force * dy) / dist;
        _nodes[j].vx += (force * dx) / dist;
        _nodes[j].vy += (force * dy) / dist;
      }
    }

    // Attraction forces (springs along edges)
    _edges.forEach(e => {
      const source = _nodes.find(n => n.id === e.source);
      const target = _nodes.find(n => n.id === e.target);
      if (source && target) {
        const dx = target.x - source.x;
        const dy = target.y - source.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = ((dist - l) / dist) * 0.1;
        source.vx += force * dx;
        source.vy += force * dy;
        target.vx -= force * dx;
        target.vy -= force * dy;
      }
    });

    // Apply velocity
    _nodes.forEach(n => {
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;

      // Boundary constraints
      n.x = Math.max(20, Math.min(_canvas.width - 20, n.x));
      n.y = Math.max(20, Math.min(_canvas.height - 20, n.y));
    });
  }
}

function draw() {
  if (!_ctx) return;
  _ctx.clearRect(0, 0, _canvas.width, _canvas.height);

  // Draw edges first
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

  // Draw nodes with labels
  _nodes.forEach(n => {
    const isSelected = _selectedNode && _selectedNode.id === n.id;
    const isSearchMatch = _searchTerm && (n.label || n.id).toLowerCase().includes(_searchTerm.toLowerCase());
    
    // Node circle
    _ctx.beginPath();
    _ctx.arc(n.x, n.y, isSelected ? 8 : 6, 0, Math.PI * 2);
    _ctx.fillStyle = isSearchMatch ? '#ffb800' : (isSelected ? '#ff6b6b' : '#4a90e2');
    _ctx.fill();
    _ctx.strokeStyle = isSelected ? '#fff' : (isSearchMatch ? '#ffc107' : 'rgba(255,255,255,0.6)');
    _ctx.lineWidth = isSelected ? 2.5 : 1.5;
    _ctx.stroke();

    // Node label
    _ctx.fillStyle = 'var(--text, #000)';
    _ctx.font = '11px DM Sans';
    _ctx.textAlign = 'center';
    _ctx.textBaseline = 'middle';
    const label = (n.label || n.id).substring(0, 15);
    _ctx.fillText(label, n.x, n.y + 14);
  });

  requestAnimationFrame(draw);
}

function setupCanvasInteraction() {
  if (!_canvas) return;

  _canvas.addEventListener('mousemove', (e) => {
    const rect = _canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / _zoomLevel;
    const y = (e.clientY - rect.top) / _zoomLevel;

    if (_isDragging && _draggedNode) {
      _draggedNode.x = x;
      _draggedNode.y = y;
      _draggedNode.pinned = true;
      return;
    }

    // Find hovered node
    const hovered = _nodes.find(n => {
      const dist = Math.sqrt((n.x - x) ** 2 + (n.y - y) ** 2);
      return dist < 10;
    });

    _canvas.style.cursor = hovered ? 'pointer' : 'grab';
  });

  _canvas.addEventListener('mousedown', (e) => {
    const rect = _canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / _zoomLevel;
    const y = (e.clientY - rect.top) / _zoomLevel;

    const node = _nodes.find(n => {
      const dist = Math.sqrt((n.x - x) ** 2 + (n.y - y) ** 2);
      return dist < 10;
    });

    if (node) {
      _isDragging = true;
      _draggedNode = node;
      _selectedNode = node;
      showNodeDetail(node);
    }
  });

  _canvas.addEventListener('mouseup', () => {
    _isDragging = false;
    _draggedNode = null;
  });

  _canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const scaleFactor = e.deltaY > 0 ? 0.9 : 1.1;
    _zoomLevel *= scaleFactor;
    _zoomLevel = Math.max(0.5, Math.min(3, _zoomLevel));
  });
}

function showNodeDetail(node) {
  const detail = document.getElementById('graphNodeDetail');
  if (!detail) return;
  
  const mentions = node.mentions || 0;
  detail.innerHTML = `
    <div class="graph-detail-header">
      <div class="graph-detail-title">${node.label || node.id}</div>
      <button onclick="document.getElementById('graphNodeDetail').style.display='none'" class="graph-detail-close">✕</button>
    </div>
    <div class="graph-detail-body">
      <div class="graph-detail-item">
        <span class="label">Type:</span>
        <span class="value">${node.type || 'Entity'}</span>
      </div>
      <div class="graph-detail-item">
        <span class="label">ID:</span>
        <span class="value" style="font-family:monospace;font-size:11px">${node.id}</span>
      </div>
      <div class="graph-detail-item">
        <span class="label">Mentions:</span>
        <span class="value">${mentions}</span>
      </div>
    </div>
  `;
  detail.style.display = 'block';
}

// ── Global search function ────────────────────────────────────────────────────

export function graphSearchChanged() {
  const input = document.getElementById('graphSearchInput');
  if (!input) return;
  _searchTerm = input.value.trim();
}

export function resetGraphView() {
  _zoomLevel = 1;
  _panX = 0;
  _panY = 0;
  _selectedNode = null;
  _searchTerm = '';
  const input = document.getElementById('graphSearchInput');
  if (input) input.value = '';
  const detail = document.getElementById('graphNodeDetail');
  if (detail) detail.style.display = 'none';
  initializeNodePositions();
  runForceSimulation(10);
  draw();
}

function showGraphLoading() {
  let hint = document.getElementById('graphHint');
  if (!hint) {
    hint = document.createElement('div');
    hint.id = 'graphHint';
    hint.className = 'graph-loading-state';
    hint.innerHTML = '<div class="spinner"></div><p>Initializing force simulation...</p>';
    _canvas?.parentElement?.appendChild(hint);
  } else {
    hint.style.display = 'flex';
  }
}

function hideGraphLoading() {
  const hint = document.getElementById('graphHint');
  if (hint) hint.style.display = 'none';
}

// ── Health Stats ──────────────────────────────────────────────────────────────

export async function loadHealthStats() {
  try {
    const res = await authFetch(`${API}/graph/health`);
    if (!res.ok) return;
    const d = await res.json();

    const grid = document.getElementById('graphHealthGrid');
    if (grid) {
      const totalDocs = (d.documents_by_source || []).reduce((sum, s) => sum + (s.count || 0), 0);
      const sources = (d.documents_by_source || []).length;
      
      let staleHTML = '';
      if (d.stale_sources_30d && d.stale_sources_30d.length > 0) {
        staleHTML = `
          <div class="connector-summary-card warning">
            <span>⚠️ Stale (30d)</span>
            <strong style="color:var(--warning)">${d.stale_sources_30d.length}</strong>
            <small>${d.stale_sources_30d.map(s => s.source).join(', ')}</small>
          </div>`;
      }

      grid.innerHTML = `
        <div class="connector-summary-card">
          <span>Tài liệu</span>
          <strong>${totalDocs}</strong>
          <small>${sources} sources</small>
        </div>
        <div class="connector-summary-card">
          <span>Thực thể</span>
          <strong>${d.entities || 0}</strong>
          <small>Entities</small>
        </div>
        <div class="connector-summary-card">
          <span>Quan hệ</span>
          <strong>${d.relations || 0}</strong>
          <small>Relations</small>
        </div>
        <div class="connector-summary-card">
          <span>Doc links</span>
          <strong>${d.document_links || 0}</strong>
          <small>${d.explicit_links || 0} explicit</small>
        </div>
        ${d.orphan_entities > 0 ? `
          <div class="connector-summary-card danger">
            <span>⚠️ Orphans</span>
            <strong>${d.orphan_entities}</strong>
            <small>Entities cô lập</small>
          </div>
        ` : ''}
        ${staleHTML}
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
    panel.className = 'graph-result-panel';
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
    <div class="graph-result-header">
      <h3>${title}</h3>
      <p>${nodes.length} nodes · ${edges.length} edges</p>
    </div>
    <div class="graph-nodes-list">
      ${nodes.slice(0, 40).map(n => `
        <span class="graph-node-chip ${n.type || 'entity'}" title="${n.type || 'entity'}">${n.label || n.id}</span>
      `).join('')}
      ${nodes.length > 40 ? `<span class="graph-nodes-more">+${nodes.length - 40} more</span>` : ''}
    </div>
  `;
}

function renderGapsResult(panel, data) {
  const gaps = data.insights?.gaps || [];
  const stale = data.insights?.stale_sources || [];
  
  let html = '<div class="graph-result-header"><h3>🔍 Gap Insights</h3></div>';
  
  if (stale && stale.length > 0) {
    html += `
      <div class="gap-section">
        <div class="gap-section-title">⚠️ Stale sources (> 30 ngày)</div>
        <ul class="gap-list">
          ${stale.slice(0, 10).map(s => `
            <li class="gap-item">
              <span class="gap-source">${s.source}</span>
              <span class="gap-days">${s.days} days</span>
            </li>
          `).join('')}
        </ul>
      </div>
    `;
  } else {
    html += '<div class="gap-section"><p style="color:var(--success)">✅ Không có stale sources trong 30 ngày</p></div>';
  }
  
  if (gaps && gaps.length > 0) {
    html += `
      <div class="gap-section">
        <div class="gap-section-title">📊 Gaps phát hiện</div>
        <ul class="gap-list">
          ${gaps.slice(0, 15).map(g => `
            <li class="gap-item">
              <span>${g.type || 'Missing relation'}</span>
              <span class="gap-badge">${g.count || 1}</span>
            </li>
          `).join('')}
        </ul>
      </div>
    `;
  }
  
  panel.innerHTML = html;
}

