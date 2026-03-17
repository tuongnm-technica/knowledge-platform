import { API, AUTH, authFetch } from '../api/client.js';
import { readApiError, escapeHtml, showToast } from '../utils/ui.js';
import { basketAddDocument, basketAddDocuments } from './basket.js';

let _generateDocCallback = null;
export function setGraphGenerateDocCallback(cb) {
  _generateDocCallback = cb;
}

export let graphViz = {
  canvas: null,
  ctx: null,
  nodes: [],
  edges: [],
  nodeById: new Map(),
  layers: { detail: null, super: null },
  activeLayer: 'detail',
  highlightNodes: new Set(),
  highlightEdges: new Set(),
  selectedNodes: new Set(),
  selectRect: null, // { x0, y0, x1, y1 } in canvas screen coords
  running: false,
  q: '',
  transform: { x: 0, y: 0, k: 1 },
  drag: { mode: null, node: null, ox: 0, oy: 0, sx0: 0, sy0: 0 },
};

export function _graphScreenToWorld(x, y) {
  const t = graphViz.transform;
  return { x: (x - t.x) / t.k, y: (y - t.y) / t.k };
}

export function _graphWorldToScreen(x, y) {
  const t = graphViz.transform;
  return { x: x * t.k + t.x, y: y * t.k + t.y };
}

export function resetGraphView() {
  const c = graphViz.canvas;
  const cx = c ? (c.width / 2) : 0;
  const cy = c ? (c.height / 2) : 0;
  // Start slightly zoomed out so the clustered (super) graph is readable by default.
  graphViz.transform = { x: cx, y: cy, k: 0.62 };
}

export function graphSearchChanged() {
  graphViz.q = String(document.getElementById('graphSearchInput')?.value || '').trim().toLowerCase();
}

export function graphClearSelection() {
  graphViz.selectedNodes = new Set();
  graphViz.selectRect = null;
}

export function graphSelectedDocumentIds(fallbackNode = null) {
  const ids = [];
  const seen = new Set();
  const selected = graphViz.selectedNodes || new Set();

  const addNodeId = (nid) => {
    const id = String(nid || '');
    if (!id.startsWith('doc:')) return;
    const docId = id.split(':', 2)[1];
    if (!docId || seen.has(docId)) return;
    seen.add(docId);
    ids.push(docId);
  };

  for (const nid of selected) addNodeId(nid);
  if (!ids.length && fallbackNode && fallbackNode.id) addNodeId(fallbackNode.id);
  return ids;
}

let _graphCtxMenuEl = null;
let _graphCtxDocIds = [];

export function _graphEnsureContextMenu() {
  if (_graphCtxMenuEl) return _graphCtxMenuEl;
  const el = document.createElement('div');
  el.id = 'graphContextMenu';
  el.style.position = 'fixed';
  el.style.zIndex = '9999';
  el.style.display = 'none';
  el.style.minWidth = '220px';
  el.style.padding = '8px';
  el.style.borderRadius = '14px';
  el.style.border = '1px solid var(--border-strong)';
  el.style.background = 'rgba(255,255,255,0.92)';
  el.style.boxShadow = 'var(--shadow)';
  el.style.backdropFilter = 'blur(8px)';
  el.addEventListener('click', (ev) => ev.stopPropagation());
  document.body.appendChild(el);
  document.addEventListener('click', () => graphHideContextMenu());
  _graphCtxMenuEl = el;
  return el;
}

export function graphHideContextMenu() {
  if (_graphCtxMenuEl) _graphCtxMenuEl.style.display = 'none';
}

export function graphShowContextMenu(clientX, clientY, node) {
  const el = _graphEnsureContextMenu();
  const docIds = graphSelectedDocumentIds(node);
  if (!docIds.length) return;
  _graphCtxDocIds = docIds.slice(0);

  const count = docIds.length;
  el.innerHTML = `
    <div style="font-weight:900;font-family:'Syne',sans-serif;margin:2px 4px 8px">Lựa chọn</div>
    <div style="color:var(--text-muted);font-size:12px;margin:0 4px 10px">${count} tài liệu</div>
    <button class="secondary-btn" style="width:100%;margin-bottom:8px" onclick="graphCtxPin()">📌 Ghim vào giỏ</button>
    <button class="primary-btn" style="width:100%;margin-bottom:8px" onclick="graphCtxDraft()">🚀 Tạo draft từ lựa chọn</button>
    <button class="secondary-btn" style="width:100%" onclick="graphClearSelection(); graphHideContextMenu();">Bỏ chọn</button>
  `;

  const pad = 8;
  const maxLeft = window.innerWidth - el.offsetWidth - pad;
  const maxTop = window.innerHeight - el.offsetHeight - pad;
  el.style.left = Math.max(pad, Math.min(clientX, maxLeft)) + 'px';
  el.style.top = Math.max(pad, Math.min(clientY, maxTop)) + 'px';
  el.style.display = 'block';
}

export function graphCtxPin() {
  const ids = Array.isArray(_graphCtxDocIds) ? _graphCtxDocIds.slice(0) : [];
  graphHideContextMenu();
  if (!ids.length) return;
  basketAddDocuments(ids, { openDrawer: true });
}

export function graphCtxDraft() {
  const ids = Array.isArray(_graphCtxDocIds) ? _graphCtxDocIds.slice(0) : [];
  graphHideContextMenu();
  if (!ids.length) return;
  if (_generateDocCallback) _generateDocCallback(ids);
}

export async function loadGraphDashboard(force = false) {
  if (!AUTH.user.is_admin) return;

  const healthGrid = document.getElementById('graphHealthGrid');
  const canvas = document.getElementById('graphCanvas');
  if (healthGrid && force) {
    healthGrid.innerHTML = `<div class="connector-summary-card"><span>Loading health...</span><strong>—</strong><small>Please wait</small></div>`;
  }

  try {
    const [hResp, gResp] = await Promise.all([
      authFetch(`${API}/graph/health`),
      authFetch(`${API}/graph/view?since_days=30&per_source=45&semantic_k=3&semantic_min_weight=3`),
    ]);
    if (!hResp.ok) throw new Error(await readApiError(hResp));
    if (!gResp.ok) throw new Error(await readApiError(gResp));

    const health = await hResp.json();
    const view = await gResp.json();

    renderGraphHealth(health);
    initGraphCanvas(canvas, view);
    renderGraphInsights(view.insights || []);
  } catch (error) {
    if (healthGrid) {
      healthGrid.innerHTML = `<div class="connector-summary-card"><span style="color:var(--danger)">Graph API error</span><strong>—</strong><small>${escapeHtml(error.message || 'Failed')}</small></div>`;
    }
  }
}

export function renderGraphHealth(health) {
  const grid = document.getElementById('graphHealthGrid');
  if (!grid) return;

  const docs = health.documents_by_source || [];
  const stale = health.stale_sources_30d || [];
  const missing = health.missing_sources || [];

  const docsCards = docs.slice(0, 8).map(d => `
    <div class="connector-summary-card">
      <span>${escapeHtml(d.source || 'source')}</span>
      <strong>${Number(d.count || 0).toLocaleString('vi-VN')}</strong>
      <small>Documents</small>
    </div>
  `).join('');

  const coreCards = `
    <div class="connector-summary-card">
      <span>Entities</span>
      <strong>${Number(health.entities || 0).toLocaleString('vi-VN')}</strong>
      <small>Total entities extracted</small>
    </div>
    <div class="connector-summary-card">
      <span>Relations</span>
      <strong>${Number(health.relations || 0).toLocaleString('vi-VN')}</strong>
      <small>Total edges</small>
    </div>
    <div class="connector-summary-card">
      <span>Doc links</span>
      <strong>${Number(health.document_links || 0).toLocaleString('vi-VN')}</strong>
      <small>Explicit: ${Number(health.explicit_links || 0).toLocaleString('vi-VN')}</small>
    </div>
    <div class="connector-summary-card">
      <span>Orphans</span>
      <strong>${Number(health.orphan_entities || 0).toLocaleString('vi-VN')}</strong>
      <small>Entities without relations</small>
    </div>
    <div class="connector-summary-card ${stale.length ? 'warn' : ''}">
      <span>Stale sources</span>
      <strong>${stale.length}</strong>
      <small>${stale.length ? `>= 30d: ${escapeHtml(stale.map(s => s.source).slice(0, 3).join(', '))}` : 'No stale sources'}</small>
    </div>
    <div class="connector-summary-card ${missing.length ? 'danger' : ''}">
      <span>Missing sources</span>
      <strong>${missing.length}</strong>
      <small>${missing.length ? escapeHtml(missing.slice(0, 4).join(', ')) : 'All sources have data'}</small>
    </div>
  `;

  grid.innerHTML = coreCards + docsCards;
}

export function renderGraphInsights(insights) {
  const wrap = document.getElementById('graphInsights');
  if (!wrap) return;
  const list = Array.isArray(insights) ? insights : [];
  if (!list.length) {
    wrap.style.display = 'none';
    wrap.innerHTML = '';
    return;
  }
  wrap.style.display = '';
  wrap.innerHTML = list.slice(0, 6).map(it => `
    <div class="graph-insight-card ${String(it.severity || '').toLowerCase() === 'warning' ? 'warn' : ''}">
      <div class="graph-insight-title">${escapeHtml(it.title || it.type || 'Insight')}</div>
      <div class="graph-insight-detail">${escapeHtml(it.detail || '')}</div>
    </div>
  `).join('');
}

export function initGraphCanvas(canvas, view) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  function buildLayer(graph, fallbackColor) {
    const rawNodes = (graph && graph.nodes) ? graph.nodes : [];
    const nodes = rawNodes.map((n, i) => ({
      id: String(n.id || i),
      label: String(n.label || n.id || 'node'),
      kind: String(n.kind || 'node'),
      source: String(n.source || ''),
      subkind: String(n.subkind || ''),
      type: String(n.subkind || n.kind || 'node'),
      mentions: Number((n.meta && n.meta.mentions) || 0),
      color: String(n.color || fallbackColor || 'rgba(148,163,184,0.85)'),
      icon: String(n.icon || ''),
      url: String(n.url || ''),
      meta: (n.meta && typeof n.meta === 'object') ? n.meta : {},
      size: Number(n.size || 11.5),
      x: (Math.random() - 0.5) * 860,
      y: (Math.random() - 0.5) * 520,
      vx: 0,
      vy: 0,
      pinned: false,
    }));
    const nodeById = new Map(nodes.map(n => [n.id, n]));
    const rawEdges = (graph && graph.edges) ? graph.edges : [];
    const edges = rawEdges
      .map(e => ({
        source: String(e.source || ''),
        target: String(e.target || ''),
        kind: String(e.kind || 'edge'),
        relation: String(e.relation || ''),
        weight: Number(e.weight || 1),
        meta: (e.meta && typeof e.meta === 'object') ? e.meta : {},
      }))
      .filter(e => nodeById.has(e.source) && nodeById.has(e.target));
    return { nodes, edges, nodeById };
  }

  const detail = buildLayer(view.detail || {}, 'rgba(194,65,12,0.75)');
  const superLayer = buildLayer(view.super || {}, 'rgba(15,118,110,0.85)');

  // Place super nodes near the centroid of their member docs (if present).
  try {
    const members = (view.super && view.super.members) ? view.super.members : {};
    for (const s of superLayer.nodes) {
      const mids = members[String(s.id)] || [];
      if (!mids.length) continue;
      let sx = 0, sy = 0, c = 0;
      for (const mid of mids) {
        const dn = detail.nodeById.get(String(mid));
        if (!dn) continue;
        sx += dn.x; sy += dn.y; c++;
      }
      if (c) {
        s.x = sx / c; s.y = sy / c;
      }
    }
  } catch {}

  graphViz.canvas = canvas;
  graphViz.ctx = ctx;
  graphViz.layers = { detail, super: superLayer };
  graphViz.activeLayer = (graphViz.transform.k < 0.65) ? 'super' : 'detail';
  graphViz.nodes = graphViz.layers[graphViz.activeLayer].nodes;
  graphViz.edges = graphViz.layers[graphViz.activeLayer].edges;
  graphViz.nodeById = graphViz.layers[graphViz.activeLayer].nodeById;
  graphViz.highlightNodes = new Set();
  graphViz.highlightEdges = new Set();
  graphViz.running = true;

  // Resize to container if possible.
  try {
    const parent = canvas.parentElement;
    if (parent) {
      const r = parent.getBoundingClientRect();
      canvas.width = Math.max(720, Math.floor(r.width));
      canvas.height = Math.max(420, 520);
    }
  } catch {}

  resetGraphView();
  _graphSelectLayer();

  // Bind events once.
  if (!canvas.__graphBound) {
    canvas.__graphBound = true;

    canvas.addEventListener('mousedown', (ev) => {
      graphHideContextMenu();
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const p = _graphScreenToWorld(sx, sy);

      // Shift + drag: rectangle selection
      if (ev.button === 0 && ev.shiftKey) {
        graphViz.drag.mode = 'select';
        graphViz.drag.sx0 = sx;
        graphViz.drag.sy0 = sy;
        graphViz.selectRect = { x0: sx, y0: sy, x1: sx, y1: sy };
        graphViz.selectedNodes = new Set();
        return;
      }

      const hit = _graphPickNode(p.x, p.y);
      if (hit) {
        graphViz.drag.mode = 'node';
        graphViz.drag.node = hit;
        hit.pinned = true;
      } else {
        graphViz.drag.mode = 'pan';
        graphViz.drag.ox = ev.clientX;
        graphViz.drag.oy = ev.clientY;
      }
    });

    window.addEventListener('mouseup', () => {
      if (graphViz.drag.mode === 'select') {
        graphViz.drag.mode = null;
        graphViz.drag.node = null;
        graphViz.selectRect = null;
        return;
      }
      graphViz.drag.mode = null;
      graphViz.drag.node = null;
    });

    window.addEventListener('mousemove', (ev) => {
      if (!graphViz.running) return;
      if (!graphViz.drag.mode) return;
      if (graphViz.drag.mode === 'pan') {
        const dx = ev.clientX - graphViz.drag.ox;
        const dy = ev.clientY - graphViz.drag.oy;
        graphViz.drag.ox = ev.clientX;
        graphViz.drag.oy = ev.clientY;
        graphViz.transform.x += dx;
        graphViz.transform.y += dy;
      }
      if (graphViz.drag.mode === 'node' && graphViz.drag.node) {
        const rect = canvas.getBoundingClientRect();
        const sx = ev.clientX - rect.left;
        const sy = ev.clientY - rect.top;
        const p = _graphScreenToWorld(sx, sy);
        graphViz.drag.node.x = p.x;
        graphViz.drag.node.y = p.y;
        graphViz.drag.node.vx = 0;
        graphViz.drag.node.vy = 0;
      }
      if (graphViz.drag.mode === 'select' && graphViz.selectRect) {
        const rect = canvas.getBoundingClientRect();
        const sx = ev.clientX - rect.left;
        const sy = ev.clientY - rect.top;
        graphViz.selectRect.x1 = sx;
        graphViz.selectRect.y1 = sy;

        const p0 = _graphScreenToWorld(graphViz.selectRect.x0, graphViz.selectRect.y0);
        const p1 = _graphScreenToWorld(graphViz.selectRect.x1, graphViz.selectRect.y1);
        const minX = Math.min(p0.x, p1.x);
        const maxX = Math.max(p0.x, p1.x);
        const minY = Math.min(p0.y, p1.y);
        const maxY = Math.max(p0.y, p1.y);

        const ids = new Set();
        for (const n of (graphViz.nodes || [])) {
          if (n.x >= minX && n.x <= maxX && n.y >= minY && n.y <= maxY) {
            ids.add(String(n.id || ''));
          }
        }
        graphViz.selectedNodes = ids;
      }
    });

    canvas.addEventListener('contextmenu', (ev) => {
      ev.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const p = _graphScreenToWorld(sx, sy);
      const hit = _graphPickNode(p.x, p.y);
      // If no selection, let right-click on a node act as selection.
      if ((!graphViz.selectedNodes || graphViz.selectedNodes.size === 0) && hit && hit.id) {
        graphViz.selectedNodes = new Set([String(hit.id)]);
      }
      graphShowContextMenu(ev.clientX, ev.clientY, hit);
    });

    canvas.addEventListener('dblclick', (ev) => {
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const p = _graphScreenToWorld(sx, sy);
      const hit = _graphPickNode(p.x, p.y);
      if (!hit) return;
      renderGraphNodeDetail(hit);
    });

    canvas.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const before = _graphScreenToWorld(sx, sy);
      const zoom = ev.deltaY < 0 ? 1.08 : 1 / 1.08;
      graphViz.transform.k = Math.max(0.35, Math.min(2.8, graphViz.transform.k * zoom));
      const after = _graphWorldToScreen(before.x, before.y);
      graphViz.transform.x += (sx - after.x);
      graphViz.transform.y += (sy - after.y);
    }, { passive: false });
  }

  _graphLoop();
}

export function _graphPickNode(x, y) {
  const nodes = graphViz.nodes || [];
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i];
    const r = Math.max(8, Number(n.size || 12));
    const dx = n.x - x;
    const dy = n.y - y;
    if ((dx * dx + dy * dy) <= (r * r)) return n;
  }
  return null;
}

export function renderGraphNodeDetail(node) {
  const panel = document.getElementById('graphNodeDetail');
  if (!panel) return;
  const isDoc = String(node && node.id ? node.id : '').startsWith('doc:');
  const pinBtn = isDoc ? `<button class="secondary-btn mini" onclick="graphPinNode('${escapeHtml(node.id)}')">📌 Pin</button>` : '';
  const draftBtn = isDoc ? `<button class="secondary-btn mini" onclick="graphDraftNode('${escapeHtml(node.id)}')">🚀 Draft</button>` : '';
  panel.style.display = 'block';
  panel.innerHTML = `
    <div class="graph-detail-title">${escapeHtml(node.label)}</div>
    <div class="graph-detail-meta">Type: ${escapeHtml(node.type)} · Mentions: ${Number(node.mentions || 0).toLocaleString('vi-VN')}</div>
    <div class="graph-detail-actions">
      <button class="secondary-btn mini" onclick="closeGraphDetail()">Close</button>
      <button class="secondary-btn mini" onclick="unpinGraphNode('${escapeHtml(node.id)}')">Unpin</button>
      <button class="secondary-btn mini" onclick="graphFocusNode('${escapeHtml(node.id)}')">Focus</button>
      <button class="secondary-btn mini" onclick="graphOpenNode('${escapeHtml(node.id)}')">Open</button>
      <button class="secondary-btn mini" onclick="graphTraceNode('${escapeHtml(node.id)}')">Trace</button>
      <button class="secondary-btn mini" onclick="graphImpactNode('${escapeHtml(node.id)}')">Impact</button>
      <button class="secondary-btn mini" onclick="graphClearHighlight()">Clear</button>
      ${pinBtn}
      ${draftBtn}
    </div>
  `;
}

export function closeGraphDetail() {
  const panel = document.getElementById('graphNodeDetail');
  if (panel) panel.style.display = 'none';
}

export function unpinGraphNode(nodeId) {
  const n = graphViz.nodeById.get(String(nodeId || ''));
  if (n) n.pinned = false;
}

export function graphClearHighlight() {
  graphViz.highlightNodes = new Set();
  graphViz.highlightEdges = new Set();
}

export function _graphEdgeKey(e) {
  return `${String(e.source || '')}|${String(e.target || '')}|${String(e.kind || '')}|${String(e.relation || '')}`;
}

export function graphOpenNode(nodeId) {
  const n = graphViz.nodeById.get(String(nodeId || ''));
  const url = n && n.url ? String(n.url) : '';
  if (!url) return showToast('No URL for this node.', 'info');
  try { window.open(url, '_blank'); } catch {}
}

export function graphPinNode(nodeId) {
  const id = String(nodeId || '');
  const docId = id.startsWith('doc:') ? id.split(':', 2)[1] : '';
  if (!docId) return showToast('Pin is available for document nodes only.', 'info');
  basketAddDocument(docId, { openDrawer: true });
}

export function graphDraftNode(nodeId) {
  const id = String(nodeId || '');
  const docId = id.startsWith('doc:') ? id.split(':', 2)[1] : '';
  if (!docId) return showToast('Draft is available for document nodes only.', 'info');
  if (_generateDocCallback) return _generateDocCallback([docId]);
}

export async function graphFocusNode(nodeId) {
  try {
    const r = await authFetch(`${API}/graph/focus?node_id=${encodeURIComponent(String(nodeId || ''))}&depth=2&max_docs=260`);
    if (!r.ok) throw new Error(await readApiError(r));
    const payload = await r.json();
    initGraphCanvas(document.getElementById('graphCanvas'), { detail: payload.detail, super: payload.super });
    renderGraphInsights(payload.insights || []);
    graphClearHighlight();
  } catch (e) {
    showToast(`Graph focus failed: ${e.message || 'API error'}`, 'error');
  }
}

export async function graphTraceNode(nodeId) {
  const id = String(nodeId || '');
  const docId = id.startsWith('doc:') ? id.split(':', 2)[1] : '';
  if (!docId) return showToast('Trace is available for document nodes only.', 'info');
  try {
    const r = await authFetch(`${API}/graph/trace?doc_id=${encodeURIComponent(docId)}&depth=4`);
    if (!r.ok) throw new Error(await readApiError(r));
    const d = await r.json();
    if (d.detail && d.super) {
      initGraphCanvas(document.getElementById('graphCanvas'), { detail: d.detail, super: d.super });
      renderGraphInsights(d.insights || []);
    }
    graphViz.highlightNodes = new Set(d.highlight_nodes || []);
    graphViz.highlightEdges = new Set(d.highlight_edges || []);
  } catch (e) {
    showToast(`Trace failed: ${e.message || 'API error'}`, 'error');
  }
}

export async function graphImpactNode(nodeId) {
  const id = String(nodeId || '');
  const docId = id.startsWith('doc:') ? id.split(':', 2)[1] : '';
  if (!docId) return showToast('Impact is available for document nodes only.', 'info');
  try {
    const r = await authFetch(`${API}/graph/impact?doc_id=${encodeURIComponent(docId)}&depth=3`);
    if (!r.ok) throw new Error(await readApiError(r));
    const d = await r.json();
    if (d.detail && d.super) {
      initGraphCanvas(document.getElementById('graphCanvas'), { detail: d.detail, super: d.super });
      renderGraphInsights(d.insights || []);
    }
    graphViz.highlightNodes = new Set(d.highlight_nodes || []);
    graphViz.highlightEdges = new Set(d.highlight_edges || []);
  } catch (e) {
    showToast(`Impact failed: ${e.message || 'API error'}`, 'error');
  }
}

export function _graphSelectLayer() {
  const want = (graphViz.transform.k < 0.65) ? 'super' : 'detail';
  if (!graphViz.layers || !graphViz.layers[want]) return;
  if (graphViz.activeLayer === want) return;
  graphViz.activeLayer = want;
  graphViz.nodes = graphViz.layers[want].nodes;
  graphViz.edges = graphViz.layers[want].edges;
  graphViz.nodeById = graphViz.layers[want].nodeById;
}

export function _graphLoop() {
  if (!graphViz.running || !graphViz.canvas || !graphViz.ctx) return;
  const active = !!document.getElementById('page-graph')?.classList.contains('active');
  if (active) {
    _graphSelectLayer();
    _graphStep();
    _graphDraw();
  }
  requestAnimationFrame(_graphLoop);
}

export function _graphStep() {
  const nodes = graphViz.nodes;
  const edges = graphViz.edges;
  if (!nodes || !edges) return;

  const repulsion = 4200;
  const springK = 0.012;
  const targetLen = 92;
  const damping = 0.88;

  // Repulsion: exact for small graphs, sampled for large graphs (keeps UI responsive).
  const N = nodes.length;
  if (N <= 240) {
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01;
        const f = repulsion / d2;
        const fx = (dx / Math.sqrt(d2)) * f;
        const fy = (dy / Math.sqrt(d2)) * f;
        if (!a.pinned) { a.vx += fx; a.vy += fy; }
        if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
      }
    }
  } else {
    const samples = Math.min(34, N - 1);
    for (let i = 0; i < N; i++) {
      const a = nodes[i];
      for (let s = 0; s < samples; s++) {
        const j = (i * 31 + s * 97) % N;
        if (j === i) continue;
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01;
        const f = repulsion / d2;
        const fx = (dx / Math.sqrt(d2)) * f;
        const fy = (dy / Math.sqrt(d2)) * f;
        if (!a.pinned) { a.vx += fx; a.vy += fy; }
      }
    }
  }

  // Springs along edges
  for (const e of edges) {
    const a = graphViz.nodeById.get(e.source);
    const b = graphViz.nodeById.get(e.target);
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
    const diff = d - targetLen;
    const f = springK * diff;
    const fx = (dx / d) * f;
    const fy = (dy / d) * f;
    if (!a.pinned) { a.vx += fx; a.vy += fy; }
    if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
  }

  // Integrate
  for (const n of nodes) {
    if (n.pinned) continue;
    n.vx *= damping;
    n.vy *= damping;
    n.x += n.vx * 0.016;
    n.y += n.vy * 0.016;
  }
}

export function _graphDraw() {
  const canvas = graphViz.canvas;
  const ctx = graphViz.ctx;
  if (!canvas || !ctx) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();

  // Background
  ctx.fillStyle = 'rgba(255,255,255,0.35)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.translate(graphViz.transform.x, graphViz.transform.y);
  ctx.scale(graphViz.transform.k, graphViz.transform.k);

  // Edges
  const hlNodes = graphViz.highlightNodes || new Set();
  const hlEdges = graphViz.highlightEdges || new Set();

  function edgeHighlighted(e) {
    const k1 = _graphEdgeKey(e);
    const k2 = `${String(e.target || '')}|${String(e.source || '')}|${String(e.kind || '')}|${String(e.relation || '')}`;
    return hlEdges.has(k1) || hlEdges.has(k2);
  }

  for (const e of graphViz.edges) {
    const a = graphViz.nodeById.get(e.source);
    const b = graphViz.nodeById.get(e.target);
    if (!a || !b) continue;

    const kind = String(e.kind || '');
    const isHL = edgeHighlighted(e);

    ctx.setLineDash([]);
    ctx.lineWidth = (isHL ? 2.2 : 1) / graphViz.transform.k;

    if (kind === 'semantic') {
      ctx.strokeStyle = isHL ? 'rgba(15,118,110,0.85)' : 'rgba(15,118,110,0.20)';
      ctx.setLineDash([6 / graphViz.transform.k, 4 / graphViz.transform.k]);
    } else if (kind === 'explicit') {
      ctx.strokeStyle = isHL ? 'rgba(29,78,216,0.85)' : 'rgba(69,47,26,0.22)';
    } else if (kind === 'membership') {
      ctx.strokeStyle = 'rgba(100,116,139,0.10)';
    } else if (kind === 'actor') {
      ctx.strokeStyle = 'rgba(100,116,139,0.16)';
    } else {
      ctx.strokeStyle = 'rgba(69,47,26,0.16)';
    }

    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  // Nodes
  const q = (graphViz.q || '').toLowerCase();
  for (const n of graphViz.nodes) {
    const label = String(n.label || '');
    const match = q && label.toLowerCase().includes(q);
    const isHL = hlNodes.has(String(n.id || ''));
    const isSel = (graphViz.selectedNodes && graphViz.selectedNodes.has(String(n.id || '')));
    const r = Math.max(8, Number(n.size || 11.5));

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = String(n.color || 'rgba(148,163,184,0.85)');
    ctx.fill();

    if (match || isHL || n.pinned || isSel) {
      if (isHL) ctx.strokeStyle = 'rgba(15,118,110,0.95)';
      else if (isSel) ctx.strokeStyle = 'rgba(217,119,6,0.92)';
      else ctx.strokeStyle = match ? 'rgba(15,118,110,0.75)' : 'rgba(15,118,110,0.55)';
      ctx.lineWidth = (isHL ? 2.4 : (isSel ? 2.4 : 2)) / graphViz.transform.k;
      ctx.stroke();
    }
  }

  // Simple "icon" letters for quick recognition when zoomed in.
  if (graphViz.transform.k > 0.95 && (graphViz.nodes || []).length < 260) {
    ctx.font = `${10 / graphViz.transform.k}px DM Sans`;
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    for (const n of graphViz.nodes) {
      const kind = String(n.kind || '');
      let t = '';
      if (kind === 'jira') t = 'J';
      else if (kind === 'confluence') t = 'C';
      else if (kind === 'slack') t = 'S';
      else if (kind === 'file') t = 'F';
      else if (kind === 'user') t = 'U';
      else if (kind === 'super') t = '◎';
      if (!t) continue;
      ctx.fillText(t, n.x - (3.5 / graphViz.transform.k), n.y + (3.5 / graphViz.transform.k));
    }
  }

  // Labels for matches
  if (q || (hlNodes && hlNodes.size)) {
    ctx.font = `${12 / graphViz.transform.k}px DM Sans`;
    ctx.fillStyle = 'rgba(32,21,13,0.9)';
    for (const n of graphViz.nodes) {
      const label = String(n.label || '');
      const match = q && label.toLowerCase().includes(q);
      const isHL = hlNodes.has(String(n.id || ''));
      if (!match && !isHL) continue;
      ctx.fillText(label.slice(0, 28), n.x + 10, n.y - 10);
    }
  }

  ctx.restore();

  // Selection rectangle (screen coords)
  const sr = graphViz.selectRect;
  if (sr) {
    const x = Math.min(sr.x0, sr.x1);
    const y = Math.min(sr.y0, sr.y1);
    const w = Math.abs(sr.x1 - sr.x0);
    const h = Math.abs(sr.y1 - sr.y0);
    ctx.save();
    ctx.setLineDash([6, 4]);
    ctx.strokeStyle = 'rgba(217,119,6,0.85)';
    ctx.lineWidth = 2;
    ctx.strokeRect(x, y, w, h);
    ctx.fillStyle = 'rgba(217,119,6,0.12)';
    ctx.fillRect(x, y, w, h);
    ctx.restore();
  }
}