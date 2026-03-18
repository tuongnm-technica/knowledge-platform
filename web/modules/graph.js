// graph.js
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

let _canvas, _ctx;
let _nodes = [], _edges = [];

export async function loadGraphDashboard() {
  console.log('[Graph] loadGraphDashboard');
  const container = document.getElementById('graphCanvas');
  if (!container) return;
  
  _canvas = container;
  _ctx = _canvas.getContext('2d');
  
  try {
    const res = await authFetch(`${API}/graph/snapshot?limit=150`);
    if (!res.ok) throw new Error('Graph fetch failed');
    const data = await res.json();
    _nodes = data.nodes || [];
    _edges = data.edges || [];
    
    // Simple random layout
    _nodes.forEach(n => {
      n.x = 50 + Math.random() * (_canvas.width - 100);
      n.y = 50 + Math.random() * (_canvas.height - 100);
    });

    draw();
    loadHealthStats();
  } catch (e) {
    console.error('[Graph] load error:', e);
  }
}

function draw() {
  if (!_ctx) return;
  _ctx.clearRect(0, 0, _canvas.width, _canvas.height);
  
  // Edges
  _ctx.strokeStyle = 'rgba(0,0,0,0.05)';
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

  // Nodes
  _nodes.forEach(n => {
    _ctx.beginPath();
    _ctx.arc(n.x, n.y, 6, 0, Math.PI * 2);
    _ctx.fillStyle = '#4a90e2';
    _ctx.fill();
    _ctx.strokeStyle = '#fff';
    _ctx.stroke();
  });
}

export async function loadHealthStats() {
  try {
    const res = await authFetch(`${API}/graph/health`);
    if (!res.ok) return;
    const d = await res.json();
    const s = d.components || {};
    
    const grid = document.getElementById('graphHealthGrid');
    if (grid) {
      grid.innerHTML = `
        <div class="connector-summary-card"><span>Tai lieu</span><strong>${s.documents || 0}</strong><small>${s.sources || 0} sources</small></div>
        <div class="connector-summary-card"><span>Thuc the</span><strong>${s.entities || 0}</strong><small>Entities</small></div>
        <div class="connector-summary-card"><span>Quan he</span><strong>${s.relationships || 0}</strong><small>Triples</small></div>
        <div class="connector-summary-card"><span>Ollama</span><strong class="${s.ollama === 'ok' ? 'text-success' : 'text-danger'}">${s.ollama === 'ok' ? 'Online' : 'Offline'}</strong></div>
      `;
    }
  } catch (e) {
    console.warn('[Graph] health fail', e);
  }
}
