// connectors.js — Full management: view, create, edit, delete, config, sync
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

console.log('[Trace C1] connectors.js module loaded');

let _dashboardData = null;
let _activeTab = 'confluence';

// ── Load ──────────────────────────────────────────────────────────────────────

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
    showToast('Không tải được connector stats', 'error');
  }
}

export async function loadConnectorCatalog() {
  console.log('[Trace C3] loadConnectorCatalog');
  try {
    const res = await authFetch(`${API}/connectors`);
    if (!res.ok) throw new Error('Catalog API failed');
    _dashboardData = await res.json();
    renderTabs(_dashboardData.tabs || []);
    renderConnectorGrid(_dashboardData.tabs || []);
  } catch (e) {
    console.error('[Connectors] loadConnectorCatalog error:', e);
  }
}

// ── Summary ───────────────────────────────────────────────────────────────────

function updateSummaryGrid(summary) {
  const grid = document.getElementById('connectorsSummaryGrid');
  if (!grid) return;
  grid.innerHTML = `
    <div class="connector-summary-card"><span>Tổng source</span><strong>${summary.total || 0}</strong></div>
    <div class="connector-summary-card"><span>Healthy</span><strong>${summary.healthy || 0}</strong></div>
    <div class="connector-summary-card"><span>Tài liệu</span><strong>${(summary.documents || 0).toLocaleString()}</strong></div>
    <div class="connector-summary-card"><span>Syncing</span><strong>${summary.syncing || 0}</strong></div>
    <div class="connector-summary-card" style="cursor:pointer" onclick="window.syncAllConnectors()">
      <span>🔄 Sync All</span><strong style="color:var(--accent,#63b3ed)">Run</strong>
    </div>
  `;
}

// ── Tabs ──────────────────────────────────────────────────────────────────────

function renderTabs(tabs) {
  const container = document.getElementById('connectorTabs');
  if (!container) return;
  if (!tabs.find(t => t.type === _activeTab)) _activeTab = tabs[0]?.type || '';
  container.innerHTML = tabs.map(tab => `
    <div class="connector-tab-btn ${tab.type === _activeTab ? 'active' : ''}"
         onclick="window.switchConnectorTab('${tab.type}')">
      ${escapeHtml(tab.label || tab.type)}
    </div>
  `).join('');
}

window.switchConnectorTab = (type) => {
  _activeTab = type;
  if (_dashboardData) {
    renderTabs(_dashboardData.tabs || []);
    renderConnectorGrid(_dashboardData.tabs || []);
  } else {
    loadConnectorCatalog();
  }
};

// ── Grid ──────────────────────────────────────────────────────────────────────

function renderConnectorGrid(tabs) {
  const grid = document.getElementById('connectorsGrid');
  if (!grid) return;

  const currentTab = tabs.find(t => t.type === _activeTab);

  // Add Instance button on top
  let html = `
    <div style="margin-bottom:14px;display:flex;align-items:center;gap:10px">
      <button class="primary-btn" onclick="window.openCreateConnector('${escapeHtml(_activeTab)}')">
        + Thêm kết nối ${escapeHtml(_activeTab)}
      </button>
      <button class="secondary-btn mini" onclick="window.syncAllForType('${escapeHtml(_activeTab)}')">
        🔄 Sync tất cả ${escapeHtml(_activeTab)}
      </button>
    </div>
  `;

  if (!currentTab?.instances?.length) {
    html += '<div class="connectors-empty">Chưa có kết nối nào. Thêm kết nối mới để bắt đầu.</div>';
    grid.innerHTML = html;
    return;
  }

  html += currentTab.instances.map(inst => {
    const status = inst.status || {};
    const sync   = (inst.sync || {}).latest_completed_run || {};
    const data   = inst.data || {};
    return `
      <div class="connector-card-rich accent-${inst.connector_type} ${status.tone || 'neutral'}">
        <div class="connector-card-top">
          <div class="connector-icon">${getLargeIcon(inst.connector_type)}</div>
          <div style="flex:1;min-width:0">
            <div class="connector-card-name">${escapeHtml(inst.instance_name)}</div>
            <div style="font-size:11px;color:var(--text-muted)">${escapeHtml(inst.base_url || '')}</div>
          </div>
          <div class="connector-status-badge ${status.code}">${escapeHtml(status.label || status.code || '—')}</div>
        </div>

        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-top:12px;font-size:12px;color:var(--text-secondary)">
          <div><span style="display:block;color:var(--text-muted)">Tài liệu</span><strong>${data.documents || 0}</strong></div>
          <div><span style="display:block;color:var(--text-muted)">Chunks</span><strong>${data.chunks || 0}</strong></div>
          <div><span style="display:block;color:var(--text-muted)">Last sync</span><strong style="font-size:11px">${formatSyncTime(sync.finished_at || sync.last_sync_at)}</strong></div>
        </div>

        <div class="connector-card-footer" style="margin-top:12px;display:flex;flex-wrap:wrap;gap:6px">
          <button class="primary-btn mini" onclick="window.syncConnector('${inst.connector_type}', '${inst.instance_id}')">🔄 Sync</button>
          <button class="secondary-btn mini" onclick="window.testConnection('${inst.connector_type}', '${inst.instance_id}')">🔌 Test</button>
          <button class="secondary-btn mini" onclick="window.openConnectorConfig('${inst.connector_type}', '${inst.instance_id}')">⚙️ Config</button>
          <button class="secondary-btn mini" onclick="window.openEditConnector('${inst.connector_type}', '${inst.instance_id}')">✏️ Sửa</button>
          <button class="secondary-btn mini" onclick="window.deleteConnectorInstance('${inst.connector_type}', '${inst.instance_id}')">🗑 Xóa</button>
          <button class="secondary-btn mini" onclick="window.discoverConnector('${inst.connector_type}', '${inst.instance_id}')">🔍 Discover</button>
        </div>
      </div>
    `;
  }).join('');

  grid.innerHTML = html;
}

// ── Modal helper ──────────────────────────────────────────────────────────────

function showConnectorModal(title, bodyHtml, onConfirm) {
  let overlay = document.getElementById('connectorModalOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'connectorModalOverlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:9000;display:flex;align-items:center;justify-content:center;';
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `
    <div style="background:var(--surface,#1e2130);border-radius:14px;padding:28px 32px;min-width:440px;max-width:580px;width:95%;box-shadow:0 8px 40px rgba(0,0,0,0.5);max-height:85vh;overflow-y:auto;">
      <h3 style="margin:0 0 20px;color:var(--text-primary,#fff)">${title}</h3>
      <div id="connectorModalBody">${bodyHtml}</div>
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:20px">
        <button class="secondary-btn" id="connectorModalCancel">Huỷ</button>
        <button class="primary-btn" id="connectorModalConfirm">Xác nhận</button>
      </div>
    </div>
  `;
  overlay.style.display = 'flex';
  document.getElementById('connectorModalCancel').onclick = closeConnectorModal;
  overlay.onclick = (e) => { if (e.target === overlay) closeConnectorModal(); };
  document.getElementById('connectorModalConfirm').onclick = onConfirm;
}

function closeConnectorModal() {
  const overlay = document.getElementById('connectorModalOverlay');
  if (overlay) overlay.style.display = 'none';
}

// ── Create Instance ───────────────────────────────────────────────────────────

window.openCreateConnector = function (connectorType) {
  showConnectorModal(`Thêm kết nối ${connectorType}`, `
    <div style="display:grid;gap:12px">
      <label>Tên kết nối<br><input id="cName" type="text" class="admin-input" placeholder="vd: Confluence Production" style="width:100%"></label>
      <label>Base URL<br><input id="cUrl" type="url" class="admin-input" placeholder="https://mycompany.atlassian.net" style="width:100%"></label>
      <label>Kiểu xác thực<br>
        <select id="cAuthType" class="admin-input" style="width:100%" onchange="window._toggleConnectorAuth()">
          <option value="token">Token</option>
          <option value="basic">Basic (Username + Password)</option>
        </select>
      </label>
      <div id="cAuthBasic" style="display:none">
        <label>Username<br><input id="cUsername" type="text" class="admin-input" style="width:100%"></label>
      </div>
      <label>Secret / Token / Password<br><input id="cSecret" type="password" class="admin-input" placeholder="API Token hoặc Password" style="width:100%"></label>
    </div>
  `, async () => {
    const name     = document.getElementById('cName')?.value.trim();
    const base_url = document.getElementById('cUrl')?.value.trim();
    const auth_type= document.getElementById('cAuthType')?.value;
    const username = document.getElementById('cUsername')?.value.trim() || undefined;
    const secret   = document.getElementById('cSecret')?.value;
    if (!name) return showToast('Vui lòng nhập tên kết nối', 'error');
    const btn = document.getElementById('connectorModalConfirm');
    btn.disabled = true; btn.textContent = 'Đang tạo...';
    try {
      const res = await authFetch(`${API}/connectors/${connectorType}/instances`, {
        method: 'POST',
        body: JSON.stringify({ name, base_url, auth_type, username, secret }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi tạo connector'); }
      showToast('Đã tạo kết nối thành công', 'success');
      closeConnectorModal();
      loadConnectorCatalog();
    } catch (e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = 'Xác nhận'; }
  });
};

window._toggleConnectorAuth = function () {
  const type = document.getElementById('cAuthType')?.value;
  const basic = document.getElementById('cAuthBasic');
  if (basic) basic.style.display = type === 'basic' ? 'block' : 'none';
};

// ── Edit Instance ─────────────────────────────────────────────────────────────

window.openEditConnector = function (connectorType, instanceId) {
  // Find the instance from cached data
  const tabs = (_dashboardData?.tabs || []);
  const tab = tabs.find(t => t.type === connectorType);
  const inst = (tab?.instances || []).find(i => String(i.instance_id) === String(instanceId));

  showConnectorModal(`Sửa kết nối: ${escapeHtml(inst?.instance_name || instanceId)}`, `
    <div style="display:grid;gap:12px">
      <label>Tên kết nối<br><input id="cName" type="text" class="admin-input" value="${escapeHtml(inst?.instance_name || '')}" style="width:100%"></label>
      <label>Base URL<br><input id="cUrl" type="url" class="admin-input" value="${escapeHtml(inst?.base_url || '')}" style="width:100%"></label>
      <label>Kiểu xác thực<br>
        <select id="cAuthType" class="admin-input" style="width:100%">
          <option value="token" ${inst?.auth_type !== 'basic' ? 'selected' : ''}>Token</option>
          <option value="basic" ${inst?.auth_type === 'basic' ? 'selected' : ''}>Basic</option>
        </select>
      </label>
      <label>Username (nếu Basic)<br><input id="cUsername" type="text" class="admin-input" value="${escapeHtml(inst?.username || '')}" style="width:100%"></label>
      <label>Secret mới (để trống = không đổi)<br><input id="cSecret" type="password" class="admin-input" placeholder="••••••••" style="width:100%"></label>
    </div>
  `, async () => {
    const payload = {};
    const name     = document.getElementById('cName')?.value.trim();
    const base_url = document.getElementById('cUrl')?.value.trim();
    const auth_type= document.getElementById('cAuthType')?.value;
    const username = document.getElementById('cUsername')?.value.trim();
    const secret   = document.getElementById('cSecret')?.value;
    if (name) payload.name = name;
    if (base_url) payload.base_url = base_url;
    if (auth_type) payload.auth_type = auth_type;
    if (username) payload.username = username;
    if (secret) payload.secret = secret;
    const btn = document.getElementById('connectorModalConfirm');
    btn.disabled = true; btn.textContent = 'Đang lưu...';
    try {
      const res = await authFetch(`${API}/connectors/${connectorType}/instances/${instanceId}`, {
        method: 'PUT',
        body: JSON.stringify(payload),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi cập nhật'); }
      showToast('Đã cập nhật kết nối', 'success');
      closeConnectorModal();
      loadConnectorCatalog();
    } catch (e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = 'Xác nhận'; }
  });
};

// ── Delete Instance ───────────────────────────────────────────────────────────

window.deleteConnectorInstance = async function (connectorType, instanceId) {
  if (!confirm('Xóa kết nối này? Dữ liệu đã sync sẽ không bị ảnh hưởng.')) return;
  try {
    const res = await authFetch(`${API}/connectors/${connectorType}/instances/${instanceId}`, { method: 'DELETE' });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Xóa thất bại'); }
    showToast('Đã xóa kết nối', 'success');
    loadConnectorCatalog();
  } catch (e) { showToast(e.message, 'error'); }
};

// ── Config Panel ──────────────────────────────────────────────────────────────

window.openConnectorConfig = function (connectorType, instanceId) {
  const tabs = (_dashboardData?.tabs || []);
  const tab = tabs.find(t => t.type === connectorType);
  const inst = (tab?.instances || []).find(i => String(i.instance_id) === String(instanceId));
  const cfg = inst?.config || {};

  showConnectorModal(`⚙️ Cấu hình: ${escapeHtml(inst?.instance_name || instanceId)}`, `
    <div style="display:grid;gap:16px">
      <label style="display:flex;align-items:center;gap:10px">
        <input type="checkbox" id="cfgEnabled" ${cfg.enabled !== false ? 'checked' : ''}> Enabled (đang hoạt động)
      </label>
      <label style="display:flex;align-items:center;gap:10px">
        <input type="checkbox" id="cfgAutoSync" ${cfg.auto_sync ? 'checked' : ''}> Auto Sync (tự động)
      </label>
      <div>
        <p style="margin:0 0 8px;color:var(--text-secondary)">Lịch sync hàng ngày:</p>
        <div style="display:flex;gap:12px;align-items:center">
          <label>Giờ (0–23)<br><input id="cfgHour" type="number" min="0" max="23" class="admin-input" value="${cfg.schedule_hour ?? 2}" style="width:80px"></label>
          <label>Phút (0–59)<br><input id="cfgMinute" type="number" min="0" max="59" class="admin-input" value="${cfg.schedule_minute ?? 0}" style="width:80px"></label>
        </div>
      </div>
    </div>
  `, async () => {
    const enabled        = document.getElementById('cfgEnabled')?.checked ?? true;
    const auto_sync      = document.getElementById('cfgAutoSync')?.checked ?? false;
    const schedule_hour  = parseInt(document.getElementById('cfgHour')?.value) || 2;
    const schedule_minute= parseInt(document.getElementById('cfgMinute')?.value) || 0;
    const btn = document.getElementById('connectorModalConfirm');
    btn.disabled = true; btn.textContent = 'Đang lưu...';
    try {
      const res = await authFetch(`${API}/connectors/${connectorType}/instances/${instanceId}/config`, {
        method: 'PUT',
        body: JSON.stringify({ enabled, auto_sync, schedule_hour, schedule_minute }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi lưu config'); }
      showToast('Đã lưu cấu hình', 'success');
      closeConnectorModal();
      loadConnectorCatalog();
    } catch (e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = 'Xác nhận'; }
  });
};

// ── Sync actions ──────────────────────────────────────────────────────────────

export async function syncConnector(type, id) {
  try {
    const res = await authFetch(`${API}/connectors/${type}/instances/${id}/sync`, { method: 'POST' });
    if (!res.ok) throw new Error('Sync failed');
    showToast('🔄 Đang sync...', 'success');
    setTimeout(loadConnectorCatalog, 2000);
  } catch (e) { showToast(e.message, 'error'); }
}

window.syncConnector = syncConnector;

window.syncAllConnectors = async function () {
  if (!confirm('Sync tất cả connectors? Có thể mất vài phút.')) return;
  try {
    const res = await authFetch(`${API}/connectors/sync-all`, { method: 'POST' });
    if (!res.ok) throw new Error('Sync all failed');
    showToast('🔄 Đang sync tất cả connectors...', 'success');
    setTimeout(loadConnectorCatalog, 3000);
  } catch (e) { showToast(e.message, 'error'); }
};

window.syncAllForType = async function (connectorType) {
  try {
    const res = await authFetch(`${API}/connectors/${connectorType}/sync-all`, { method: 'POST' });
    if (!res.ok) throw new Error('Sync failed');
    showToast(`🔄 Đang sync tất cả ${connectorType}...`, 'success');
    setTimeout(loadConnectorCatalog, 2000);
  } catch (e) { showToast(e.message, 'error'); }
};

// ── Test Connection ───────────────────────────────────────────────────────────

export async function testConnection(type, id) {
  showToast('🔌 Đang test kết nối...', 'info');
  try {
    const res = await authFetch(`${API}/connectors/${type}/instances/${id}/test`, { method: 'POST' });
    const data = await res.json();
    showToast(data.status === 'ok' ? '✅ Kết nối thành công' : `❌ Thất bại: ${data.message || 'unknown'}`,
              data.status === 'ok' ? 'success' : 'error');
  } catch (e) { showToast(e.message, 'error'); }
}

window.testConnection = testConnection;

// ── Discover ──────────────────────────────────────────────────────────────────

window.discoverConnector = async function (connectorType, instanceId) {
  showToast('🔍 Đang khám phá scopes...', 'info');
  try {
    const res = await authFetch(`${API}/connectors/${connectorType}/instances/${instanceId}/discover`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    const scopes = data.scopes || data.spaces || data.projects || [];
    const panel = document.getElementById('connectorsGrid');
    if (panel && scopes.length) {
      const info = document.createElement('div');
      info.style.cssText = 'margin-top:12px;padding:12px;background:rgba(99,179,237,0.08);border-radius:8px;border:1px solid rgba(99,179,237,0.2)';
      info.innerHTML = `
        <strong style="color:var(--accent)">🔍 Tìm thấy ${scopes.length} scope(s):</strong>
        <ul style="margin:8px 0 0;padding-left:20px;font-size:12px;color:var(--text-secondary)">
          ${scopes.slice(0, 20).map(s => `<li>${escapeHtml(JSON.stringify(s))}</li>`).join('')}
        </ul>
      `;
      panel.appendChild(info);
    } else {
      showToast(`Tìm thấy ${scopes.length} scopes`, 'success');
    }
  } catch (e) { showToast(`Discover thất bại: ${e.message}`, 'error'); }
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function getLargeIcon(type) {
  const map = { confluence: '📘', jira: '🎫', slack: '💬', github: '🐙', notion: '📝' };
  return map[type] || '🔗';
}

function formatSyncTime(ts) {
  if (!ts) return 'Chưa sync';
  try {
    return new Date(ts).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  } catch { return ts; }
}
