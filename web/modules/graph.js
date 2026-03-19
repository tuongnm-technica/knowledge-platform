// graph.js — Knowledge Graph with snapshot, health, and advanced views
import { authFetch, API } from '../api/client.js';
import { showToast, kpPrompt, escapeHtml } from '../utils/ui.js';

let _canvas, _ctx;
let _nodes = [], _edges = [];
let _activeView = 'snapshot';
let _selectedNode = null;
let _zoomLevel = 1;
let _panX = 0, _panY = 0;
let _isDragging = false;
let _isPanning = false;
let _lastMouseX = 0;
let _lastMouseY = 0;
let _draggedNode = null;
let _searchTerm = '';
let _hoveredNode = null;
let _simAlpha = 1;
let _animationFrameId = null;

// Xuất hàm ra global window để index.html có thể gọi bằng onclick=""
window.loadGraphDashboard = loadGraphDashboard;
window.graphSearchChanged = graphSearchChanged;
window.resetGraphView = resetGraphView;

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
  // Ẩn panel kết quả text khi chuyển view (chỉ hiện lại khi xem Gaps)
  const panel = document.getElementById('graphResultPanel');
  if (panel) panel.style.display = (viewId === 'gaps') ? 'block' : 'none';

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
    updateCanvasWithData(data);
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
    n.x = center_x + Math.cos(angle) * radius + (Math.random() - 0.5) * 80;
    n.y = center_y + Math.sin(angle) * radius + (Math.random() - 0.5) * 80;
    n.vx = 0;
    n.vy = 0;
  });
}

function updateCanvasWithData(data) {
  _nodes = (data.detail && data.detail.nodes) ? data.detail.nodes : (data.nodes || []);
  _edges = (data.detail && data.detail.edges) ? data.detail.edges : (data.edges || []);
  
  initializeNodePositions();
  
  // Ánh xạ trước object node vào edge để physics chạy nhanh O(E) thay vì O(E*N)
  _edges.forEach(e => {
    e.sourceNode = _nodes.find(n => n.id === (e.source || e.from));
    e.targetNode = _nodes.find(n => n.id === (e.target || e.to));
  });
  
  _panX = 0;
  _panY = 0;
  _zoomLevel = 1;
  _simAlpha = 1.0; // Wake up physics
  
  if (_animationFrameId) cancelAnimationFrame(_animationFrameId);
  draw();
}

function stepPhysics() {
  if (_simAlpha < 0.001) return;

  const k = 150 * _simAlpha;  // Lực đẩy
  const damping = 0.85;       // Giảm xóc

  // Lực đẩy giữa các node (Repulsion)
  for (let i = 0; i < _nodes.length; i++) {
    for (let j = i + 1; j < _nodes.length; j++) {
      const dx = _nodes[j].x - _nodes[i].x;
      const dy = _nodes[j].y - _nodes[i].y;
      let distSq = dx * dx + dy * dy;
      if (distSq === 0) distSq = 1;
      if (distSq < 60000) { // Chỉ đẩy nhau nếu nằm trong bán kính nhất định
        const force = k / distSq;
        _nodes[i].vx -= force * dx;
        _nodes[i].vy -= force * dy;
        _nodes[j].vx += force * dx;
        _nodes[j].vy += force * dy;
      }
    }
  }

  // Lực kéo từ các liên kết (Attraction / Springs)
  _edges.forEach(e => {
    const s = e.sourceNode;
    const t = e.targetNode;
    if (s && t) {
      const dx = t.x - s.x;
      const dy = t.y - s.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      let l = 90; // Khoảng cách lý tưởng
      if (s.kind === 'super' || t.kind === 'super') l = 160;
      
      const force = ((dist - l) / dist) * 0.04 * _simAlpha * (e.weight || 1);
      s.vx += force * dx;
      s.vy += force * dy;
      t.vx -= force * dx;
      t.vy -= force * dy;
    }
  });

  // Lực hấp dẫn tâm & Áp dụng vận tốc
  const cx = _canvas.width / 2;
  const cy = _canvas.height / 2;
  
  _nodes.forEach(n => {
    if (!n.pinned) {
      n.vx += (cx - n.x) * 0.001 * _simAlpha;
      n.vy += (cy - n.y) * 0.001 * _simAlpha;
      
      n.vx *= damping;
      n.vy *= damping;
      n.x += n.vx;
      n.y += n.vy;
    } else {
      n.vx = 0; n.vy = 0;
    }
  });
  
  _simAlpha *= 0.985; // Alpha cooling
}

function draw() {
  if (!_ctx) return;
  
  stepPhysics(); // Cho phép tương tác vật lý liên tục
  
  _ctx.save();
  _ctx.clearRect(0, 0, _canvas.width, _canvas.height);
  _ctx.translate(_panX, _panY);
  _ctx.scale(_zoomLevel, _zoomLevel);

  // Draw edges first
  _edges.forEach(e => {
    const s = e.sourceNode;
    const t = e.targetNode;
    if (s && t) {
      _ctx.beginPath();
      _ctx.moveTo(s.x, s.y);
      _ctx.lineTo(t.x, t.y);
      const weight = e.weight || 1;
      _ctx.lineWidth = Math.min(weight, 3.5);
      _ctx.strokeStyle = `rgba(100, 120, 200, ${Math.min(0.1 + weight * 0.05, 0.4)})`;
      _ctx.stroke();
    }
  });

  // Draw nodes with labels
  _nodes.forEach(n => {
    const isSelected = _selectedNode && _selectedNode.id === n.id;
    const isHovered = _hoveredNode && _hoveredNode.id === n.id;
    const isSearchMatch = _searchTerm && (n.label || n.id).toLowerCase().includes(_searchTerm.toLowerCase());
    const isSuper = n.kind === 'super';

    const baseRadius = n.size || (isSuper ? 18 : 8);
    const radius = isSelected || isSearchMatch ? baseRadius * 1.3 : baseRadius;
    const color = isSearchMatch ? '#ffb800' : (n.color || '#4a90e2');

    // Draw glow
    if (isSelected || isSearchMatch) {
      _ctx.beginPath();
      _ctx.arc(n.x, n.y, radius + 5, 0, Math.PI * 2);
      _ctx.fillStyle = isSearchMatch ? 'rgba(255,184,0,0.3)' : 'rgba(255,107,107,0.3)';
      _ctx.fill();
    }

    // Node circle
    _ctx.beginPath();
    _ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
    _ctx.fillStyle = color;
    _ctx.fill();
    _ctx.strokeStyle = isSelected ? '#fff' : 'rgba(255,255,255,0.7)';
    _ctx.lineWidth = isSelected ? 2.5 : (isSuper ? 1.5 : 1);
    _ctx.stroke();

    // Node label
    if (_zoomLevel > 1.0 || isSuper || isSelected || isSearchMatch || isHovered) {
      _ctx.font = isSuper ? 'bold 11px sans-serif' : '10px sans-serif';
      _ctx.textAlign = 'center';
      _ctx.textBaseline = 'top';
      
      let labelText = n.label || n.id;
      // Rút gọn text nếu quá dài (trừ khi đang hover, chọn, hoặc search)
      if (!isSelected && !isSearchMatch && !isHovered && labelText.length > 15) {
        labelText = labelText.substring(0, 13) + '...';
      }

      const textY = n.y + radius + 4;
      // Vẽ viền (halo) cho chữ để tách biệt khỏi các đường line bên dưới
      _ctx.lineWidth = 3;
      _ctx.strokeStyle = document.documentElement.getAttribute('data-theme') === 'dark' ? 'rgba(15, 23, 42, 0.85)' : 'rgba(255, 255, 255, 0.85)';
      _ctx.strokeText(labelText, n.x, textY);

      // Vẽ chữ (đổi màu nổi bật nếu đang tương tác)
      _ctx.fillStyle = (isSelected || isHovered || isSearchMatch) ? (isSearchMatch ? '#d97706' : '#0284c7') : (document.documentElement.getAttribute('data-theme') === 'dark' ? '#cbd5e1' : '#334155');
      _ctx.fillText(labelText, n.x, textY);
    }
  });

  _ctx.restore();
  _animationFrameId = requestAnimationFrame(draw);
}

function setupCanvasInteraction() {
  if (!_canvas) return;

  _canvas.addEventListener('mousemove', (e) => {
    const rect = _canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    
    const worldX = (mouseX - _panX) / _zoomLevel;
    const worldY = (mouseY - _panY) / _zoomLevel;

    if (_isDragging && _draggedNode) {
      _draggedNode.x = worldX;
      _draggedNode.y = worldY;
      _simAlpha = Math.max(_simAlpha, 0.1); // Wake up physics
      return;
    }

    if (_isPanning) {
      _panX += (mouseX - _lastMouseX);
      _panY += (mouseY - _lastMouseY);
      _lastMouseX = mouseX;
      _lastMouseY = mouseY;
      return;
    }

    // Find hovered node
    const hovered = _nodes.find(n => {
      const radius = n.size || 8;
      const dist = Math.sqrt((n.x - worldX) ** 2 + (n.y - worldY) ** 2);
      return dist < radius * 1.5 + 4;
    });
    _hoveredNode = hovered || null; // Lưu lại node đang hover

    _canvas.style.cursor = hovered ? 'pointer' : 'grab';
  });

  _canvas.addEventListener('mousedown', (e) => {
    const rect = _canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;
    const worldX = (mouseX - _panX) / _zoomLevel;
    const worldY = (mouseY - _panY) / _zoomLevel;

    const node = _nodes.find(n => {
      const radius = n.size || 8;
      const dist = Math.sqrt((n.x - worldX) ** 2 + (n.y - worldY) ** 2);
      return dist < radius * 1.5 + 4;
    });

    if (node) {
      _isDragging = true;
      _draggedNode = node;
      _draggedNode.pinned = true;
      _selectedNode = node;
      showNodeDetail(node);
    } else {
      _isPanning = true;
      _lastMouseX = mouseX;
      _lastMouseY = mouseY;
      _selectedNode = null;
      const detail = document.getElementById('graphNodeDetail');
      if (detail) detail.style.display = 'none';
      _canvas.style.cursor = 'grabbing';
    }
  });

  _canvas.addEventListener('mouseup', () => {
    if (_draggedNode) _draggedNode.pinned = false;
    _isDragging = false;
    _isPanning = false;
    _draggedNode = null;
    _canvas.style.cursor = 'grab';
  });
  
  _canvas.addEventListener('mouseleave', () => {
    if (_draggedNode) _draggedNode.pinned = false;
    _isDragging = false;
    _isPanning = false;
    _draggedNode = null;
  });

  _canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    const rect = _canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    const scaleFactor = e.deltaY > 0 ? 0.9 : 1.1;
    const newZoom = Math.max(0.2, Math.min(4, _zoomLevel * scaleFactor));
    
    // Dịch chuyển panX, panY để zoom mượt vào vị trí con trỏ chuột
    _panX = mouseX - (mouseX - _panX) * (newZoom / _zoomLevel);
    _panY = mouseY - (mouseY - _panY) * (newZoom / _zoomLevel);
    
    _zoomLevel = newZoom;
  });
}

function showNodeDetail(node) {
  const detail = document.getElementById('graphNodeDetail');
  if (!detail) return;
  
  const meta = node.meta || {};
  let metaHtml = Object.entries(meta).map(([k, v]) => `
    <div class="graph-detail-item">
      <span class="label">${escapeHtml(k)}:</span>
      <span class="value">${escapeHtml(String(v))}</span>
    </div>
  `).join('');

  detail.innerHTML = `
    <div class="graph-detail-header">
      <div class="graph-detail-title">${escapeHtml(node.label || node.id)}</div>
      <button onclick="document.getElementById('graphNodeDetail').style.display='none'" class="graph-detail-close">✕</button>
    </div>
    <div class="graph-detail-body">
      <div class="graph-detail-item">
        <span class="label">Type:</span>
        <span class="value">${escapeHtml(node.kind || node.type || 'Entity')}</span>
      </div>
      <div class="graph-detail-item">
        <span class="label">ID:</span>
        <span class="value" style="font-family:monospace;font-size:11px">${escapeHtml(node.id)}</span>
      </div>
      ${node.url ? `
      <div class="graph-detail-item">
        <span class="label">Link:</span>
        <span class="value"><a href="${escapeHtml(node.url)}" target="_blank" style="color:var(--accent)">Mở tài liệu ↗</a></span>
      </div>` : ''}
      ${metaHtml ? `<hr style="border:0;border-top:1px solid var(--border);margin:8px 0;">${metaHtml}` : ''}
      ${node.id.startsWith('doc:') ? `
      <div style="margin-top:12px">
        <button class="primary-btn mini" style="width:100%" onclick="if(window.viewDocument) window.viewDocument('${escapeHtml(node.id.replace('doc:',''))}')">📄 Xem chi tiết tài liệu</button>
      </div>` : ''}
    </div>
  `;
  detail.style.display = 'block';
}

// ── Global search function ────────────────────────────────────────────────────

export function graphSearchChanged() {
  const input = document.getElementById('graphSearchInput');
  if (!input) return;
  _searchTerm = input.value.trim();
  _simAlpha = Math.max(_simAlpha, 0.1); // Wake up
}

export function resetGraphView() {
  _selectedNode = null;
  _searchTerm = '';
  const input = document.getElementById('graphSearchInput');
  if (input) input.value = '';
  const detail = document.getElementById('graphNodeDetail');
  if (detail) detail.style.display = 'none';
  
  _zoomLevel = 1;
  _panX = _canvas ? (_canvas.width - _canvas.width * _zoomLevel) / 2 : 0;
  _panY = _canvas ? (_canvas.height - _canvas.height * _zoomLevel) / 2 : 0;
  _simAlpha = 1.0;
}

function showGraphLoading() {
  let hint = document.getElementById('graphHintOverlay');
  if (!hint) {
    hint = document.createElement('div');
    hint.id = 'graphHintOverlay';
    hint.className = 'graph-loading-state';
    hint.innerHTML = '<div class="spinner"></div><p>Đang tải dữ liệu và tính toán lực...</p>';
    _canvas?.parentElement?.appendChild(hint);
  } else {
    hint.style.display = 'flex';
  }
}

function hideGraphLoading() {
  const hint = document.getElementById('graphHintOverlay');
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
      const totalDocs = d.totalDocuments || 0;
      const sources = Object.keys(d.statusByConnector || {}).length;
      
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
  showGraphLoading();
  try {
    const res = await authFetch(`${API}/graph/focus?node_id=${encodeURIComponent(nodeId)}&depth=2`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    updateCanvasWithData(data);
    hideGraphLoading();
    showToast(`Đã tải Focus Graph cho ${nodeId}`, 'success');
  } catch (e) {
    hideGraphLoading();
    showToast('Không tải được focus graph', 'error');
  }
}

// ── Impact View ───────────────────────────────────────────────────────────────

async function loadGraphImpact(docId) {
  showGraphLoading();
  try {
    const res = await authFetch(`${API}/graph/impact?doc_id=${encodeURIComponent(docId)}&depth=3`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    updateCanvasWithData(data);
    hideGraphLoading();
    showToast(`Đã tải Impact Analysis`, 'success');
  } catch (e) {
    hideGraphLoading();
    showToast('Không tải được impact analysis', 'error');
  }
}

// ── Trace View ────────────────────────────────────────────────────────────────

async function loadGraphTrace(docId, jiraKey) {
  showGraphLoading();
  try {
    const params = docId ? `doc_id=${encodeURIComponent(docId)}` : `jira_key=${encodeURIComponent(jiraKey)}`;
    const res = await authFetch(`${API}/graph/trace?${params}&depth=4`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    updateCanvasWithData(data);
    hideGraphLoading();
    showToast(`Đã tải Trace Root Cause`, 'success');
  } catch (e) {
    hideGraphLoading();
    showToast('Không tải được trace', 'error');
  }
}

// ── Gaps View ─────────────────────────────────────────────────────────────────

async function loadGraphGaps() {
  const panel = getOrCreateResultPanel();
  panel.style.display = 'block';
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
  panel.style.display = 'block';
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
  const stale = data.staleSources || [];
  // Tự map lại từ cấu trúc trả về mới của BE thành list gaps để render
  const gaps = [];
  if (data.orphanEntities?.length) gaps.push({ type: "Orphan Entities", count: data.orphanEntities.length });
  if (data.missingRelationships?.length) gaps.push({ type: "Missing Relationships", count: data.missingRelationships.length });
  if (data.isolatedDocuments?.length) gaps.push({ type: "Isolated Documents", count: data.isolatedDocuments.length });
  
  let html = '<div class="graph-result-header"><h3>🔍 Gap Insights</h3></div>';
  
  if (stale && stale.length > 0) {
    html += `
      <div class="gap-section">
        <div class="gap-section-title">⚠️ Stale sources (> 30 ngày)</div>
        <ul class="gap-list">
          ${stale.slice(0, 10).map(s => `
            <li class="gap-item">
              <span class="gap-source">${s.connector || s.source}</span>
              <span class="gap-days">${s.daysSinceSync || s.days} days</span>
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
