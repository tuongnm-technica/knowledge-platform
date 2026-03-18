// connectors.js
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

console.log('[Trace C1] connectors.js module loaded');

export async function loadConnectorStats(refresh = false) {
  console.log('[Trace C2] loadConnectorStats');
  try {
    const res = await authFetch(`${API}/connectors/stats`);
    if (!res.ok) throw new Error('Stats API failed');
    const data = await res.json();
    
    updateSummaryGrid(data.summary || {});
    await loadConnectorCatalog();
  } catch (e) {
    console.error('[Connectors] loadConnectorStats error:', e);
  }
}

export async function loadConnectorCatalog() {
  console.log('[Trace C3] loadConnectorCatalog');
  try {
    const res = await authFetch(`${API}/connectors`);
    if (!res.ok) throw new Error('Catalog API failed');
    const data = await res.json();
    
    renderTabs(data.tabs || []);
    renderConnectorGrid(data.tabs || []);
  } catch (e) {
    console.error('[Connectors] loadConnectorCatalog error:', e);
  }
}

function updateSummaryGrid(summary) {
  const grid = document.getElementById('connectorsSummaryGrid');
  if (!grid) return;
  
  grid.innerHTML = `
    <div class="connector-summary-card"><span>Tong source</span><strong>${summary.total || 0}</strong></div>
    <div class="connector-summary-card"><span>Healthy</span><strong>${summary.healthy || 0}</strong></div>
    <div class="connector-summary-card"><span>Tai lieu</span><strong>${(summary.documents || 0).toLocaleString()}</strong></div>
    <div class="connector-summary-card"><span>Syncing</span><strong>${summary.syncing || 0}</strong></div>
  `;
}

let _activeTab = 'confluence';
function renderTabs(tabs) {
  const container = document.getElementById('connectorTabs');
  if (!container) return;
  if (!tabs.find(t => t.type === _activeTab)) _activeTab = tabs[0]?.type || '';

  container.innerHTML = tabs.map(tab => `
    <div class="connector-tab-btn ${tab.type === _activeTab ? 'active' : ''}" 
         onclick="window.switchConnectorTab('${tab.type}')">
      ${tab.label}
    </div>
  `).join('');
}

window.switchConnectorTab = (type) => {
  _activeTab = type;
  loadConnectorCatalog();
};

function renderConnectorGrid(tabs) {
  const grid = document.getElementById('connectorsGrid');
  if (!grid) return;
  
  const currentTab = tabs.find(t => t.type === _activeTab);
  if (!currentTab?.instances?.length) {
    grid.innerHTML = '<div class="connectors-empty">Chua co ket noi nao.</div>';
    return;
  }

  grid.innerHTML = currentTab.instances.map(inst => {
    const status = inst.status || {};
    return `
      <div class="connector-card-rich accent-${inst.connector_type} ${status.tone || 'neutral'}">
        <div class="connector-card-top">
          <div class="connector-icon">${getLargeIcon(inst.connector_type)}</div>
          <div class="connector-card-name" style="flex:1;font-weight:700">${escapeHtml(inst.instance_name)}</div>
          <div class="connector-status-badge ${status.code}">${status.label}</div>
        </div>
        <div class="connector-card-footer" style="margin-top:12px">
            <button class="primary-btn mini" onclick="window.syncConnector('${inst.connector_type}', '${inst.instance_id}')">Sync Now</button>
            <button class="secondary-btn mini" onclick="window.testConnection('${inst.connector_type}', '${inst.instance_id}')">Test</button>
        </div>
      </div>
    `;
  }).join('');
}

function getLargeIcon(type) {
  const map = { confluence:'📘', jira:'🎫', slack:'💬' };
  return map[type] || '🔗';
}

export async function syncConnector(type, id) {
  try {
    await authFetch(`${API}/connectors/${type}/instances/${id}/sync`, { method:'POST' });
    showToast('Starting sync...');
  } catch (e) { showToast(e.message, 'error'); }
}

export async function testConnection(type, id) {
  try {
    const res = await authFetch(`${API}/connectors/${type}/instances/${id}/test`, { method:'POST' });
    const data = await res.json();
    showToast(data.status === 'ok' ? 'Success' : 'Failed');
  } catch (e) { showToast(e.message, 'error'); }
}
