// connectors.js — Full management: view, create, edit, delete, config, sync
// Uses shared kpOpenModal/kpConfirm from ui.js
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml, kpOpenModal, kpConfirm, _kpBuildModalField } from '../utils/ui.js';

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
    <div class="connector-summary-card"><span>Tổng source</span><strong>${summary.total || 0}</strong><small>Connectors cấu hình</small></div>
    <div class="connector-summary-card"><span>Healthy</span><strong>${summary.healthy || 0}</strong><small>Kết nối hoạt động</small></div>
    <div class="connector-summary-card"><span>Tài liệu</span><strong>${(summary.documents || 0).toLocaleString()}</strong><small>Chunks trong KB</small></div>
    <div class="connector-summary-card"><span>Syncing</span><strong>${summary.syncing || 0}</strong><small>Đang đồng bộ</small></div>
    <div class="connector-summary-card" style="cursor:pointer" onclick="window.syncAllConnectors()">
      <span>🔄 Sync All</span><strong style="color:var(--accent)">Run</strong><small>Kích hoạt tất cả</small>
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
  const grid    = document.getElementById('connectorsGrid');
  const toolbar = document.getElementById('connectorsToolbar');
  if (!grid) return;

  const currentTab = tabs.find(t => t.type === _activeTab);

  // Render "Add instance" toolbar SEPARATELY, outside the css grid
  if (toolbar) {
    toolbar.innerHTML = `
      <div style="display:flex;align-items:center;gap:10px;padding:0 0 12px">
        <button class="primary-btn" onclick="window.openCreateConnector('${escapeHtml(_activeTab)}')">
          + Thêm kết nối ${escapeHtml(_activeTab)}
        </button>
        <button class="secondary-btn" onclick="window.syncAllForType('${escapeHtml(_activeTab)}')">
          🔄 Sync tất cả ${escapeHtml(_activeTab)}
        </button>
      </div>
    `;
  }

  if (!currentTab?.instances?.length) {
    grid.innerHTML = '<div class="connectors-empty">Chưa có kết nối nào. Thêm kết nối mới để bắt đầu.</div>';
    return;
  }

  grid.innerHTML = currentTab.instances.map(inst => renderConnectorCard(inst)).join('');
}

function renderConnectorCard(inst) {
  const status = inst.status || {};
  const sync   = (inst.sync || {}).latest_completed_run || {};
  const data   = inst.data || {};
  const cfg    = inst.config || {};
  const type   = inst.connector_type || '';
  const iid    = inst.instance_id;
  const badgeClass = status.code || 'neutral';
  const syncTime = formatSyncTime(sync.finished_at || sync.last_sync_at);
  const hasSyncRun = !!(sync.started_at || sync.finished_at);
  const docsVal = (data.documents || 0).toLocaleString();
  const chunksVal = (data.chunks || 0).toLocaleString();
  const isEnabled = cfg.enabled !== false;
  const autoSync  = !!cfg.auto_sync;

  return `
    <article class="connector-card connector-card-rich accent-${escapeHtml(type)}">
      <div class="connector-card-top">
        <div class="connector-header" style="display:flex;align-items:flex-start;gap:12px;flex:1;min-width:0">
          <div class="connector-icon connector-icon-default">${getLargeIcon(type)}</div>
          <div style="flex:1;min-width:0">
            <div class="connector-name-row">
              <div class="connector-name" style="font-family:var(--font-family-title, 'Syne', sans-serif);font-size:15px;font-weight:700;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(inst.instance_name)}</div>
              <span class="connector-kind">${escapeHtml(type)}</span>
            </div>
            <div class="connector-desc" style="font-size:11px;color:var(--text-muted);margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${escapeHtml(inst.base_url || type)}</div>
          </div>
        </div>
        <div class="connector-status-badge ${badgeClass}">
          <div class="status-dot-sm"></div>
          <span>${escapeHtml(status.label || status.code || '—')}</span>
        </div>
      </div>

      <div class="connector-body">
        <div class="connector-config-grid">
          <div class="connector-config-item">
            <span>Trạng thái</span>
            <strong>${isEnabled ? '✅ Enabled' : '⏸ Disabled'}</strong>
          </div>
          <div class="connector-config-item">
            <span>Auto sync</span>
            <strong>${autoSync ? `🕐 ${cfg.schedule_hour ?? '?'}:${String(cfg.schedule_minute ?? 0).padStart(2,'0')}` : '⛔ Tắt'}</strong>
          </div>
        </div>

        <div class="connector-stats connector-stats-rich">
          <div class="stat-item">
            <div class="stat-value">${docsVal}</div>
            <div class="stat-label">Tài liệu</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">${chunksVal}</div>
            <div class="stat-label">Chunks</div>
          </div>
          <div class="stat-item">
            <div class="stat-value stat-value-small">${syncTime}</div>
            <div class="stat-label">Last sync</div>
          </div>
        </div>

        ${hasSyncRun ? `<div class="connector-run-strip ${sync.status === 'running' ? 'running' : ''}">
          <div>
            <strong>Lần sync gần nhất</strong>
            <span>${sync.status === 'running' ? '🔄 Đang chạy...' : escapeHtml(sync.status || 'completed')}</span>
          </div>
          <div class="connector-run-metrics">
            <span style="font-size:11px;color:var(--text-dim)">${formatSyncTime(sync.started_at)}</span>
            ${sync.documents_synced ? `<span style="font-size:11px;color:var(--accent)">${sync.documents_synced} docs</span>` : ''}
          </div>
        </div>` : ''}

        <div class="connector-actions-row" style="margin-top:auto;padding-top:14px;border-top:1px solid var(--border)">
          <button class="primary-btn connector-action-btn" onclick="window.syncConnector('${type}', '${iid}')">🔄 Sync</button>
          <button class="secondary-btn connector-action-btn" onclick="window.testConnection('${type}', '${iid}')">🔌 Test</button>
          
          <div style="flex-basis:100%;height:0"></div> <!-- line break for many buttons -->
          
          <button class="secondary-btn mini" onclick="window.openConnectorConfig('${type}', '${iid}')">⚙️ Config</button>
          <button class="secondary-btn mini" onclick="window.openEditConnector('${type}', '${iid}')">✏️ Sửa</button>
          <button class="secondary-btn mini" onclick="window.discoverConnector('${type}', '${iid}')">🔍 Scope</button>
          <button class="danger-btn mini" style="margin-left:auto" onclick="window.deleteConnectorInstance('${type}', '${iid}')">🗑</button>
        </div>
      </div>
    </article>
  `;
}

// ── Create Instance ───────────────────────────────────────────────────────────

window.openCreateConnector = function (connectorType) {
  const body = document.createElement('div');
  body.className = 'kp-modal-form';

  const { wrap: w1, input: nameIn } = _kpBuildModalField({ id: 'cName', label: 'Tên kết nối', placeholder: 'vd: Confluence Production', required: true });
  const { wrap: w2, input: urlIn } = _kpBuildModalField({ id: 'cUrl', label: 'Base URL', type: 'url', placeholder: 'https://mycompany.atlassian.net' });
  const { wrap: w3, input: authTypeIn } = _kpBuildModalField({
    id: 'cAuthType', label: 'Kiểu xác thực', type: 'select',
    options: [{ value: 'token', label: 'Token' }, { value: 'basic', label: 'Basic (Username + Password)' }],
  });
  const { wrap: w4, input: usernameIn } = _kpBuildModalField({ id: 'cUsername', label: 'Username (nếu Basic)', placeholder: 'Username' });
  const { wrap: w5, input: secretIn } = _kpBuildModalField({ id: 'cSecret', label: 'Secret / Token / Password', type: 'password', placeholder: 'API Token hoặc Password' });

  w4.style.display = 'none';
  authTypeIn.addEventListener('change', () => {
    w4.style.display = authTypeIn.value === 'basic' ? '' : 'none';
  });

  body.append(w1, w2, w3, w4, w5);

  kpOpenModal({
    title: `Thêm kết nối ${connectorType}`,
    subtitle: 'Cấu hình kết nối mới',
    content: body,
    okText: 'Tạo kết nối',
    onOk: async () => {
      const name     = nameIn.value.trim();
      const base_url = urlIn.value.trim();
      const auth_type= authTypeIn.value;
      const username = usernameIn.value.trim() || undefined;
      const secret   = secretIn.value;
      if (!name) return { error: 'Vui lòng nhập tên kết nối' };
      try {
        const res = await authFetch(`${API}/connectors/${connectorType}/instances`, {
          method: 'POST',
          body: JSON.stringify({ name, base_url, auth_type, username, secret }),
        });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi tạo connector'); }
        showToast('Đã tạo kết nối thành công', 'success');
        loadConnectorCatalog();
        return true;
      } catch (e) { return { error: e.message }; }
    },
  });
};

// ── Edit Instance ─────────────────────────────────────────────────────────────

window.openEditConnector = function (connectorType, instanceId) {
  const tabs = (_dashboardData?.tabs || []);
  const tab = tabs.find(t => t.type === connectorType);
  const inst = (tab?.instances || []).find(i => String(i.instance_id) === String(instanceId));

  const body = document.createElement('div');
  body.className = 'kp-modal-form';

  const { wrap: w1, input: nameIn } = _kpBuildModalField({ id: 'cName', label: 'Tên kết nối', value: inst?.instance_name || '' });
  const { wrap: w2, input: urlIn } = _kpBuildModalField({ id: 'cUrl', label: 'Base URL', type: 'url', value: inst?.base_url || '' });
  const { wrap: w3, input: authTypeIn } = _kpBuildModalField({
    id: 'cAuthType', label: 'Kiểu xác thực', type: 'select',
    value: inst?.auth_type || 'token',
    options: [{ value: 'token', label: 'Token' }, { value: 'basic', label: 'Basic' }],
  });
  const { wrap: w4, input: usernameIn } = _kpBuildModalField({ id: 'cUsername', label: 'Username', value: inst?.username || '' });
  const { wrap: w5, input: secretIn } = _kpBuildModalField({ id: 'cSecret', label: 'Secret mới (để trống = không đổi)', type: 'password', placeholder: '••••••••' });

  body.append(w1, w2, w3, w4, w5);

  kpOpenModal({
    title: `Sửa kết nối: ${inst?.instance_name || instanceId}`,
    content: body,
    okText: 'Lưu thay đổi',
    onOk: async () => {
      const payload = {};
      const name     = nameIn.value.trim();
      const base_url = urlIn.value.trim();
      const auth_type= authTypeIn.value;
      const username = usernameIn.value.trim();
      const secret   = secretIn.value;
      if (name) payload.name = name;
      if (base_url) payload.base_url = base_url;
      if (auth_type) payload.auth_type = auth_type;
      if (username) payload.username = username;
      if (secret) payload.secret = secret;
      try {
        const res = await authFetch(`${API}/connectors/${connectorType}/instances/${instanceId}`, {
          method: 'PUT',
          body: JSON.stringify(payload),
        });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi cập nhật'); }
        showToast('Đã cập nhật kết nối', 'success');
        loadConnectorCatalog();
        return true;
      } catch (e) { return { error: e.message }; }
    },
  });
};

// ── Delete Instance ───────────────────────────────────────────────────────────

window.deleteConnectorInstance = async function (connectorType, instanceId) {
  const confirmed = await kpConfirm({
    title: '🗑 Xóa kết nối',
    message: 'Xóa kết nối này? Dữ liệu đã sync sẽ không bị ảnh hưởng.',
    okText: 'Xóa',
    cancelText: 'Huỷ',
    danger: true,
  });
  if (!confirmed) return;
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

  const body = document.createElement('div');
  body.className = 'kp-modal-form';

  // Enabled checkbox
  const enabledWrap = document.createElement('div');
  enabledWrap.className = 'kp-modal-field';
  const enabledLabel = document.createElement('label');
  enabledLabel.style.cssText = 'display:flex;align-items:center;gap:10px;cursor:pointer';
  const enabledCb = document.createElement('input');
  enabledCb.type = 'checkbox';
  enabledCb.id = 'cfgEnabled';
  enabledCb.checked = cfg.enabled !== false;
  enabledLabel.appendChild(enabledCb);
  enabledLabel.appendChild(document.createTextNode('Enabled (đang hoạt động)'));
  enabledWrap.appendChild(enabledLabel);

  // Auto sync checkbox
  const autoWrap = document.createElement('div');
  autoWrap.className = 'kp-modal-field';
  const autoLabel = document.createElement('label');
  autoLabel.style.cssText = 'display:flex;align-items:center;gap:10px;cursor:pointer';
  const autoCb = document.createElement('input');
  autoCb.type = 'checkbox';
  autoCb.id = 'cfgAutoSync';
  autoCb.checked = !!cfg.auto_sync;
  autoLabel.appendChild(autoCb);
  autoLabel.appendChild(document.createTextNode('Auto Sync (tự động)'));
  autoWrap.appendChild(autoLabel);

  const { wrap: w3, input: hourIn } = _kpBuildModalField({ id: 'cfgHour', label: 'Giờ sync (0–23)', type: 'number', value: String(cfg.schedule_hour ?? 2) });
  const { wrap: w4, input: minuteIn } = _kpBuildModalField({ id: 'cfgMinute', label: 'Phút (0–59)', type: 'number', value: String(cfg.schedule_minute ?? 0) });

  body.append(enabledWrap, autoWrap, w3, w4);

  kpOpenModal({
    title: `⚙️ Cấu hình: ${inst?.instance_name || instanceId}`,
    content: body,
    okText: 'Lưu cấu hình',
    onOk: async () => {
      const enabled        = enabledCb.checked;
      const auto_sync      = autoCb.checked;
      const schedule_hour  = parseInt(hourIn.value) || 2;
      const schedule_minute= parseInt(minuteIn.value) || 0;
      try {
        const res = await authFetch(`${API}/connectors/${connectorType}/instances/${instanceId}/config`, {
          method: 'PUT',
          body: JSON.stringify({ enabled, auto_sync, schedule_hour, schedule_minute }),
        });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi lưu config'); }
        showToast('Đã lưu cấu hình', 'success');
        loadConnectorCatalog();
        return true;
      } catch (e) { return { error: e.message }; }
    },
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
  const confirmed = await kpConfirm({
    title: '🔄 Sync tất cả',
    message: 'Sync tất cả connectors? Có thể mất vài phút.',
    okText: 'Sync',
    cancelText: 'Huỷ',
  });
  if (!confirmed) return;
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
      info.style.cssText = 'margin-top:12px;padding:12px;background:var(--glow);border-radius:8px;border:1px solid var(--border)';
      info.innerHTML = `
        <strong style="color:var(--accent)">🔍 Tìm thấy ${scopes.length} scope(s):</strong>
        <ul style="margin:8px 0 0;padding-left:20px;font-size:12px;color:var(--text-muted)">
          ${scopes.slice(0, 20).map(s => `<li>${escapeHtml(JSON.stringify(s))}</li>`).join('')}
        </ul>
      `;
      panel.appendChild(info);
    } else {
      showToast(`Tìm thấy ${scopes.length} scopes`, 'success');
    }
  } catch (e) { showToast(`Discover thất bại: ${e.message}`, 'error'); }
};

// ── Tab sync helpers ──────────────────────────────────────────────────────────

export function syncCurrentConnectorTab() {
  window.syncAllForType(_activeTab);
}

export async function clearCurrentConnectorTab() {
  const confirmed = await kpConfirm({
    title: '⚠️ Xóa dữ liệu tab',
    message: `Xóa toàn bộ dữ liệu đã sync cho tab "${_activeTab}"?`,
    okText: 'Xóa',
    danger: true,
  });
  if (!confirmed) return;
  try {
    const res = await authFetch(`${API}/connectors/${_activeTab}/clear`, { method: 'POST' });
    if (!res.ok) throw new Error('Clear failed');
    showToast('Đã xóa dữ liệu', 'success');
    loadConnectorCatalog();
  } catch (e) { showToast(e.message, 'error'); }
}

export async function clearAllKnowledgeBase() {
  const confirmed = await kpConfirm({
    title: '⚠️ Xóa TOÀN BỘ knowledge base',
    message: 'Hành động này sẽ xóa hết dữ liệu đã sync. Bạn có chắc chắn?',
    okText: 'Xóa tất cả',
    danger: true,
  });
  if (!confirmed) return;
  try {
    const res = await authFetch(`${API}/connectors/clear-all`, { method: 'POST' });
    if (!res.ok) throw new Error('Clear all failed');
    showToast('Đã xóa toàn bộ knowledge base', 'success');
    loadConnectorCatalog();
  } catch (e) { showToast(e.message, 'error'); }
}

export function openCreateConnectorInstance() {
  window.openCreateConnector(_activeTab);
}

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
