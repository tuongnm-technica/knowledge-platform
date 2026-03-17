import { API, AUTH, authFetch } from '../api/client.js';
import {
  readApiError, escapeHtml, formatDateTime, formatNumber,
  showToast, kpOpenModal, kpConfirm, _kpBuildModalField
} from '../utils/ui.js';

export let connectorDirectory = { summary: null, tabs: [] };
export let connectorIndex = {};
export let connectorActiveTab = localStorage.getItem('kp_connector_tab') || 'confluence';
export let connectorDiagnostics = {};
export let connectorScopeCache = {};

export async function syncConnector(name) {
  const conn = connectorIndex[String(name || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }
  const button = document.querySelector(`[data-connector-sync="${name}"]`);
  if (button) {
    button.disabled = true;
    button.classList.add('syncing');
    button.innerHTML = '<span class="spin">⟳</span> Syncing...';
  }

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}/sync`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json().catch(() => ({}));
    if (String(data.status || '') !== 'started') {
      showToast(data.reason || 'Sync skipped.', 'info');
      await loadConnectorStats(true);
      return;
    }

    const connectorKey = String(data.connector || `${conn.connector_type}:${conn.instance_id}`);
    showToast('Đã bắt đầu sync. Đang theo dõi tiến độ...', 'success');
    await openSyncProgressModal({
      title: `Sync progress`,
      connectors: [connectorKey],
    });
  } catch (error) {
    showToast(error.message || `Cannot sync ${name}.`, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.classList.remove('syncing');
      button.innerHTML = 'Sync now';
    }
  }
}

export async function openSyncProgressModal({ title = 'Sync progress', connectors = [], skipped = [] } = {}) {
  const keys = Array.isArray(connectors) ? connectors.map(k => String(k || '').trim()).filter(Boolean) : [];
  if (!keys.length) return;

  const body = document.createElement('div');
  body.className = 'kp-modal-form-wrap';

  const header = document.createElement('div');
  header.className = 'kp-modal-help';
  header.textContent = 'Mẹo: bạn có thể đóng cửa sổ này; sync vẫn chạy ở background.';
  body.appendChild(header);

  const list = document.createElement('div');
  list.style.display = 'flex';
  list.style.flexDirection = 'column';
  list.style.gap = '10px';
  list.style.marginTop = '10px';
  body.appendChild(list);

  const skippedBox = document.createElement('div');
  skippedBox.className = 'kp-modal-help';
  skippedBox.style.marginTop = '10px';
  body.appendChild(skippedBox);

  function labelForKey(key) {
    const c = connectorIndex[String(key)] || null;
    if (c && c.name) return `${c.name} (${key})`;
    return key;
  }

  function renderRow(key, run) {
    const status = run ? String(run.status || '') : 'never';
    const fetched = run ? Number(run.fetched || 0) : 0;
    const indexed = run ? Number(run.indexed || 0) : 0;
    const errors = run ? Number(run.errors || 0) : 0;
    const startedAt = run ? (run.started_at || '') : '';

    const indeterminate = status === 'running' && fetched <= 0;
    const pct = (status !== 'running')
      ? 100
      : (fetched > 0 ? Math.max(0, Math.min(99, Math.round((indexed / Math.max(1, fetched)) * 100))) : 0);
    const barClass = indeterminate ? 'connector-progress indeterminate' : 'connector-progress';
    const color = errors > 0 ? `linear-gradient(90deg, var(--warn), var(--danger))` : `linear-gradient(90deg, var(--accent3), var(--accent))`;

    return `
      <div style="border:1px solid var(--border);border-radius:16px;padding:10px 10px;background:rgba(255,255,255,0.62)">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px">
          <div style="font-weight:900">${escapeHtml(labelForKey(key))}</div>
          <div style="font-size:12px;color:var(--text-muted)">${escapeHtml(status)}${startedAt ? ` · ${escapeHtml(formatDateTime(startedAt))}` : ''}</div>
        </div>
        <div class="${barClass}"><div class="connector-progress-fill" style="width:${pct}%;background:${color}"></div></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;font-size:12px;color:var(--text-muted)">
          <span>Fetched ${formatNumber(fetched)}</span>
          <span>Indexed ${formatNumber(indexed)}</span>
          <span>Errors ${formatNumber(errors)}</span>
        </div>
      </div>
    `;
  }

  let stopped = false;
  let tick = 0;

  async function poll() {
    if (stopped) return;
    tick++;
    try {
      const r = await authFetch(`${API}/connectors/sync/status`, {
        method: 'POST',
        body: JSON.stringify({ connectors: keys }),
      });
      if (!r.ok) throw new Error(await readApiError(r));
      const data = await r.json();
      const statuses = (data && data.statuses) ? data.statuses : {};

      let doneCount = 0;
      list.innerHTML = keys.map(key => {
        const run = statuses[key] ? statuses[key].run : null;
        if (run && String(run.status || '') !== 'running' && run.finished_at) doneCount++;
        return renderRow(key, run);
      }).join('');

      if (Array.isArray(skipped) && skipped.length) {
        const txt = skipped.slice(0, 10).map(s => `${s.connector || ''}: ${s.reason || ''}`.trim()).filter(Boolean).join(' · ');
        skippedBox.textContent = `Skipped: ${txt}${skipped.length > 10 ? ' ...' : ''}`;
        skippedBox.style.display = '';
      } else {
        skippedBox.style.display = 'none';
      }

      if (doneCount === keys.length) {
        stopped = true;
        showToast('Sync hoàn tất.', 'success');
        await loadConnectorStats(true);
      }
    } catch (e) {
      if (tick > 2) {
        showToast(e.message || 'Không lấy được tiến độ sync.', 'error');
      }
    }
  }

  await poll();
  const intervalId = setInterval(poll, 1200);

  await kpOpenModal({
    title,
    subtitle: `${keys.length} connector(s)`,
    content: body,
    okText: 'Đóng',
    cancelText: '',
    onOk: () => true,
  });

  stopped = true;
  clearInterval(intervalId);
  await loadConnectorStats(true);
}

export function getConnectorBadgeClass(code) {
  const classes = {
    healthy: 'connected',
    syncing: 'syncing',
    attention: 'error',
    ready: 'empty',
    not_configured: 'warning',
  };
  return classes[code] || 'empty';
}

export function getConnectorTestClass(status) {
  if (status === 'ok') return 'success';
  if (status === 'error') return 'error';
  if (status === 'running') return 'running';
  return 'neutral';
}

export function getConnectorIcon(name) {
  const icons = {
    confluence: '📘',
    jira: '🟣',
    slack: '💬',
    files: '🗂️',
    file_server: '🗂️',
  };
  return icons[name] || '🔗';
}

export function renderConnectorSummary(summary) {
  const grid = document.getElementById('connectorsSummaryGrid');
  const pill = document.getElementById('connectorsSummaryPill');
  if (!grid || !summary) return;

  if (pill) {
    pill.textContent = `${summary.configured}/${summary.total} configured · ${summary.syncing} syncing`;
  }

  grid.innerHTML = [
    { label: 'Total connectors', value: summary.total, note: 'Registered data sources' },
    { label: 'Configured', value: summary.configured, note: 'Ready for manual or scheduled sync' },
    { label: 'Healthy', value: summary.healthy, note: 'Configured and already indexed' },
    { label: 'Attention', value: summary.attention, note: 'Need config or investigation' },
    { label: 'Documents', value: formatNumber(summary.documents), note: 'Indexed source documents' },
    { label: 'Chunks', value: formatNumber(summary.chunks), note: 'Retrieval units in storage' },
  ].map(item => `
    <div class="connector-summary-card">
      <span>${item.label}</span>
      <strong>${item.value}</strong>
      <small>${item.note}</small>
    </div>
  `).join('');
}

export function renderConnectorHistory(history) {
  if (!history || !history.length) {
    return `<div class="connector-history-empty">No sync history yet.</div>`;
  }
  return history.map(run => `
    <div class="connector-history-item">
      <div class="connector-history-head">
        <span class="connector-history-status status-${escapeHtml(run.status || 'unknown')}">${escapeHtml(run.status || 'unknown')}</span>
        <span>${formatDateTime(run.finished_at || run.started_at || run.last_sync_at)}</span>
      </div>
      <div class="connector-history-metrics">
        <span>Fetched ${formatNumber(run.fetched)}</span>
        <span>Indexed ${formatNumber(run.indexed)}</span>
        <span>Errors ${formatNumber(run.errors)}</span>
      </div>
    </div>
  `).join('');
}

export function renderConnectorProgress(run, running) {
  if (!running) return '';
  const fetched = Number((run || {}).fetched || 0) || 0;
  const indexed = Number((run || {}).indexed || 0) || 0;
  const errors = Number((run || {}).errors || 0) || 0;

  const indeterminate = fetched <= 0;
  let pct = 0;
  if (!indeterminate) {
    pct = Math.max(0, Math.min(99, Math.round((indexed / Math.max(1, fetched)) * 100)));
  }
  const color = errors > 0 ? `linear-gradient(90deg, var(--warn), var(--danger))` : `linear-gradient(90deg, var(--accent3), var(--accent))`;
  return `
    <div class="connector-progress ${indeterminate ? 'indeterminate' : ''}" title="${indeterminate ? 'Fetching...' : `${indexed}/${fetched}`}">
      <div class="connector-progress-fill" style="width:${pct}%;background:${color}"></div>
    </div>
  `;
}

export function pad2(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return '';
  return String(v).padStart(2, '0');
}

export function getConnectorSelectionList(connector) {
  const state = connector.state || {};
  const sel = state.selection || {};
  const t = connector.connector_type || String(connector.id || '').split(':')[0];
  if (t === 'confluence') return sel.spaces || [];
  if (t === 'jira') return sel.projects || [];
  if (t === 'slack') return sel.channels || [];
  if (t === 'file_server') return sel.folders || [];
  return [];
}

export function buildConnectorSelectionPayload(connectorId, values) {
  const unique = Array.from(new Set(values.map(v => String(v || '').trim()).filter(Boolean)));
  const t = String(connectorId || '').split(':')[0];
  if (t === 'confluence') return { spaces: unique };
  if (t === 'jira') return { projects: unique };
  if (t === 'slack') return { channels: unique };
  if (t === 'file_server') return { folders: unique };
  return {};
}

export function renderConnectorManage(connector) {
  if (!AUTH.user?.is_admin) return '';

  const state = connector.state || {};
  const enabled = !!state.enabled;
  const autoSync = !!state.auto_sync;
  const timeVal = (state.schedule_hour === null || state.schedule_hour === undefined || state.schedule_minute === null || state.schedule_minute === undefined)
    ? ''
    : `${pad2(state.schedule_hour)}:${pad2(state.schedule_minute)}`;

  const cached = connectorScopeCache[connector.id] || null;
  const selected = new Set(getConnectorSelectionList(connector).map(String));

  let scopeMarkup = `<div class="connector-scope-empty">Discover available ${escapeHtml((connector.config || {}).scope_label || 'scope')} to select.</div>`;
  if (cached && Array.isArray(cached.items)) {
    const items = cached.items.slice(0, 60);
    const allNote = selected.size === 0
      ? `<div class="connector-scope-empty">No items selected = sync ALL.</div>`
      : '';
    scopeMarkup = allNote + items.map(item => {
      const value = String(item.id || item.key || item.name || '').trim();
      const label = item.key
        ? `[${item.key}] ${item.name || item.key}`
        : item.id
          ? `${item.name || item.id}${item.is_private ? ' (private)' : ''}`
          : (item.name || value);
      const checked = selected.has(value) ? 'checked' : '';
      return `
        <label class="scope-item">
          <input type="checkbox" data-scope-checkbox="${escapeHtml(connector.id)}" data-scope-value="${escapeHtml(value)}" ${checked}>
          <span>${escapeHtml(label)}</span>
        </label>
      `;
    }).join('') + (cached.items.length > 60 ? `<div class="connector-scope-empty">Showing first 60 of ${formatNumber(cached.items.length)}.</div>` : '');
  }

  return `
    <div class="connector-manage">
      <div class="connector-section-title">Manage (Demo)</div>
      <div class="connector-manage-row">
        <label class="scope-toggle">
          <input type="checkbox" id="cfg_enabled_${escapeHtml(connector.id)}" ${enabled ? 'checked' : ''}>
          <span>Enabled</span>
        </label>
        <label class="scope-toggle">
          <input type="checkbox" id="cfg_auto_${escapeHtml(connector.id)}" ${autoSync ? 'checked' : ''}>
          <span>Auto sync</span>
        </label>
        <input class="time-input" type="time" id="cfg_time_${escapeHtml(connector.id)}" value="${escapeHtml(timeVal)}">
        <button class="secondary-btn" onclick="discoverConnectorScopes('${escapeHtml(connector.id)}')">Discover</button>
        <button class="primary-btn" onclick="saveConnectorConfig('${escapeHtml(connector.id)}')">Save</button>
        <button class="secondary-btn" onclick="editConnectorInstance('${escapeHtml(connector.id)}')">Edit</button>
        <button class="danger-btn" onclick="deleteConnectorInstance('${escapeHtml(connector.id)}')">Delete</button>
      </div>
      <div class="connector-scope-list">
        ${scopeMarkup}
      </div>
      <div class="connector-action-hint">Scope selection overrides .env defaults for demo.</div>
    </div>
  `;
}

export function renderConnectorCard(connector) {
  const status = connector.status || {};
  const sync = connector.sync || {};
  const config = connector.config || {};
  const data = connector.data || {};
  const actions = connector.actions || {};
  const latestCompleted = sync.latest_completed_run || null;
  const latestRun = sync.latest_run || null;
  const history = sync.history || [];
  const diagnostic = connectorDiagnostics[connector.id] || null;
  const statusClass = getConnectorBadgeClass(status.code);
  const canManage = !!actions.can_manage;
  const canTest = !!actions.can_test;
  const canSync = !!actions.can_sync;
  const liveTestMarkup = diagnostic
    ? `<div class="connector-live-test ${getConnectorTestClass(diagnostic.status)}">
        <strong>Live test</strong>
        <span>${escapeHtml(diagnostic.message || 'No details')}</span>
        <small>${diagnostic.latency_ms ? `${diagnostic.latency_ms} ms` : ''} ${diagnostic.checked_at ? `· ${formatDateTime(diagnostic.checked_at)}` : ''}</small>
      </div>`
    : '';
  const missingMarkup = connector.missing_settings && connector.missing_settings.length
    ? `<div class="connector-missing">Missing: ${connector.missing_settings.map(escapeHtml).join(', ')}</div>`
    : '';
  const syncStateText = sync.running
    ? `Running since ${formatDateTime((latestRun || {}).started_at)}`
    : `Last completed ${formatDateTime((latestCompleted || {}).finished_at || (latestCompleted || {}).last_sync_at)}.`;
  const actionHint = canManage ? '' : `<div class="connector-action-hint">Read-only for non-admin accounts.</div>`;
  const manageMarkup = renderConnectorManage(connector);

  return `
    <article class="connector-card connector-card-rich accent-${escapeHtml(connector.accent || 'default')}">
      <div class="connector-card-top">
        <div class="connector-header">
          <div class="connector-icon">${escapeHtml(getConnectorIcon(connector.icon || connector.connector_type || connector.id))}</div>
          <div>
            <div class="connector-name-row">
              <div class="connector-name">${escapeHtml(connector.name || connector.id)}</div>
              <span class="connector-kind">${escapeHtml(connector.kind || 'source')}</span>
            </div>
            <div class="connector-desc">${escapeHtml(connector.description || '')}</div>
          </div>
        </div>
        <div class="connector-status-badge ${statusClass}">
          <div class="status-dot-sm"></div><span>${escapeHtml(status.label || 'Unknown')}</span>
        </div>
      </div>
      <div class="connector-body">
        <div class="connector-body-copy">${escapeHtml(status.message || '')}</div>
        ${missingMarkup}
        <div class="connector-config-grid">
          <div class="connector-config-item">
            <span>${escapeHtml(config.target_label || 'Target')}</span>
            <strong>${escapeHtml(config.target_value || '—')}</strong>
          </div>
          <div class="connector-config-item">
            <span>${escapeHtml(config.scope_label || 'Scope')}</span>
            <strong>${escapeHtml(config.scope_value || '—')}</strong>
          </div>
          <div class="connector-config-item">
            <span>Auth</span>
            <strong>${escapeHtml(config.auth_label || 'Credentials')}: ${escapeHtml(config.auth_value || '—')}</strong>
          </div>
          <div class="connector-config-item">
            <span>Workspace binding</span>
            <strong>${escapeHtml(config.workspace_binding || '—')}</strong>
          </div>
        </div>
        <div class="connector-stats connector-stats-rich">
          <div class="stat-item">
            <div class="stat-value">${formatNumber(data.documents)}</div>
            <div class="stat-label">Documents</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">${formatNumber(data.chunks)}</div>
            <div class="stat-label">Chunks</div>
          </div>
          <div class="stat-item">
            <div class="stat-value stat-value-small">${formatDateTime((latestCompleted || {}).finished_at || (latestCompleted || {}).last_sync_at)}</div>
            <div class="stat-label">Last Completed Sync</div>
          </div>
        </div>
        <div class="connector-run-strip ${sync.running ? 'running' : ''}">
          <div>
            <strong>${escapeHtml(sync.schedule_label || 'Manual')}</strong>
            <span>${escapeHtml(syncStateText)}</span>
          </div>
          <div class="connector-run-metrics">
            <span>Fetched ${formatNumber((latestRun || {}).fetched)}</span>
            <span>Indexed ${formatNumber((latestRun || {}).indexed)}</span>
            <span>Errors ${formatNumber((latestRun || {}).errors)}</span>
          </div>
        </div>
        ${renderConnectorProgress(latestRun, sync.running)}
        <div class="connector-capabilities">
          ${(connector.capabilities || []).map(capability => `<span class="connector-capability">${escapeHtml(capability)}</span>`).join('')}
        </div>
        ${liveTestMarkup}
        ${manageMarkup}
        <div class="connector-actions-row">
          <button class="secondary-btn connector-action-btn" data-connector-test="${escapeHtml(connector.id)}" onclick="testConnector('${escapeHtml(connector.id)}')" ${canTest ? '' : 'disabled'}>
            Test connection
          </button>
          <button class="primary-btn connector-action-btn" data-connector-sync="${escapeHtml(connector.id)}" onclick="syncConnector('${escapeHtml(connector.id)}')" ${canSync ? '' : 'disabled'}>
            Sync now
          </button>
        </div>
        ${actionHint}
        <div class="connector-history">
          <div class="connector-section-title">Recent sync runs</div>
          ${renderConnectorHistory(history)}
        </div>
      </div>
    </article>
  `;
}

export function renderConnectorDashboard() {
  renderConnectorSummary(connectorDirectory.summary);

  const tabsEl = document.getElementById('connectorTabs');
  const tabs = connectorDirectory.tabs || [];
  if (tabsEl) {
    if (!tabs.length) {
      tabsEl.innerHTML = '';
    } else {
      tabsEl.innerHTML = tabs.map(tab => {
        const active = (String(tab.type) === String(connectorActiveTab)) ? 'active' : '';
        const count = Array.isArray(tab.instances) ? tab.instances.length : 0;
        return `<button class="connector-tab-btn ${active}" onclick="setActiveConnectorTab('${tab.type}')">${escapeHtml(tab.label || tab.type)} (${count})</button>`;
      }).join('');
    }
  }

  const syncBtn = document.getElementById('syncTabConnectorsBtn');
  const clearBtn = document.getElementById('clearTabDataBtn');
  const addBtn = document.getElementById('addConnectorBtn');
  const isAdmin = !!AUTH.user?.is_admin;
  if (syncBtn) {
    syncBtn.disabled = !isAdmin;
    syncBtn.textContent = `Sync ${String(connectorActiveTab || '').toUpperCase()}`;
  }
  if (clearBtn) {
    clearBtn.style.display = isAdmin ? '' : 'none';
    clearBtn.textContent = `Clear ${String(connectorActiveTab || '').toUpperCase()}`;
  }
  if (addBtn) {
    addBtn.style.display = isAdmin ? '' : 'none';
  }

  const grid = document.getElementById('connectorsGrid');
  if (!grid) return;

  const activeTab = (tabs || []).find(t => String(t.type) === String(connectorActiveTab)) || (tabs || [])[0] || null;
  const connectors = (activeTab && activeTab.instances) ? activeTab.instances : [];
  if (!Array.isArray(connectors) || connectors.length === 0) {
    grid.innerHTML = '<div class="connectors-empty">No connector instances yet. Add one to start.</div>';
    return;
  }

  grid.innerHTML = connectors.map(renderConnectorCard).join('');
}

export function setActiveConnectorTab(tabType) {
  connectorActiveTab = String(tabType || 'confluence');
  localStorage.setItem('kp_connector_tab', connectorActiveTab);
  renderConnectorDashboard();
}

export async function testConnector(name) {
  const conn = connectorIndex[String(name || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }
  connectorDiagnostics[name] = {
    status: 'running',
    message: 'Testing connection...',
    checked_at: new Date().toISOString(),
  };
  renderConnectorDashboard();

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}/test`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json();
    connectorDiagnostics[name] = data;
    renderConnectorDashboard();
    showToast(data.status === 'ok' ? `${name} connection is healthy.` : `${name} connection check needs attention.`, data.status === 'ok' ? 'success' : 'error');
  } catch (error) {
    connectorDiagnostics[name] = {
      status: 'error',
      message: error.message || 'Connection test failed.',
      checked_at: new Date().toISOString(),
    };
    renderConnectorDashboard();
    showToast(error.message || `Cannot test ${name}.`, 'error');
  }
}

export async function discoverConnectorScopes(name) {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const conn = connectorIndex[String(name || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}/discover`);
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    connectorScopeCache[name] = { items: data.items || [] };
    renderConnectorDashboard();
    showToast(`Discovered ${formatNumber((data.items || []).length)} items for ${name}.`);
  } catch (error) {
    showToast(error.message || 'Discovery failed.', 'error');
  }
}

export async function saveConnectorConfig(name) {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const conn = connectorIndex[String(name || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }

  const enabledEl = document.getElementById(`cfg_enabled_${name}`);
  const autoEl = document.getElementById(`cfg_auto_${name}`);
  const timeEl = document.getElementById(`cfg_time_${name}`);

  const enabled = enabledEl ? !!enabledEl.checked : true;
  const auto_sync = autoEl ? !!autoEl.checked : false;
  const timeVal = timeEl ? (timeEl.value || '').trim() : '';

  if (auto_sync && !timeVal) {
    showToast('Please set a time for auto sync.', 'error');
    return;
  }

  let schedule_hour = null;
  let schedule_minute = null;
  if (auto_sync && timeVal.includes(':')) {
    const [hh, mm] = timeVal.split(':');
    schedule_hour = Number(hh);
    schedule_minute = Number(mm);
  }

  const safeName = (window.CSS && CSS.escape) ? CSS.escape(name) : name;
  const checks = Array.from(document.querySelectorAll(`input[data-scope-checkbox="${safeName}"]`));
  const selected = checks
    .filter(el => el.checked)
    .map(el => el.getAttribute('data-scope-value'))
    .filter(Boolean);

  const selection = buildConnectorSelectionPayload(name, selected);

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}/config`, {
      method: 'PUT',
      body: JSON.stringify({
        enabled,
        auto_sync,
        schedule_hour,
        schedule_minute,
        selection,
      }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Saved ${name} configuration.`);
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Save failed.', 'error');
  }
}

export function _connectorTypeFromKey(key) {
  return String(key || '').split(':')[0] || '';
}

export function _instanceIdFromKey(key) {
  return String(key || '').split(':')[1] || '';
}

export async function openCreateConnectorInstance() {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const type = String(connectorActiveTab || 'confluence');

  const created = await openConnectorInstanceModal({ mode: 'create', type });
  if (!created) return;
  const { name, base_url, auth_type, username, secret, extra } = created;

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(type)}/instances`, {
      method: 'POST',
      body: JSON.stringify({ name, base_url, auth_type, username, secret, extra }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast('Connector instance created.', 'success');
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Cannot create connector.', 'error');
  }
}

export async function editConnectorInstance(connectorKey) {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const conn = connectorIndex[String(connectorKey || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }
  const type = String(conn.connector_type || _connectorTypeFromKey(connectorKey));
  const instance_id = String(conn.instance_id || _instanceIdFromKey(connectorKey));

  const updated = await openConnectorInstanceModal({ mode: 'edit', type, conn });
  if (!updated) return;
  const payload = updated;

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(type)}/instances/${encodeURIComponent(instance_id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast('Connector updated.', 'success');
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Update failed.', 'error');
  }
}

export async function deleteConnectorInstance(connectorKey) {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const conn = connectorIndex[String(connectorKey || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }
  const ok = await kpConfirm({
    title: 'Delete connector',
    message: `Delete connector instance "${conn.instance_name || conn.name || conn.id}"?`,
    okText: 'Delete',
    cancelText: 'Cancel',
    danger: true,
  });
  if (!ok) return;

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast('Connector deleted.', 'success');
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Delete failed.', 'error');
  }
}

export function _kpParseSmbBaseUrl(baseUrl) {
  const s = String(baseUrl || '');
  const m = s.match(/^\\\\([^\\]+)\\([^\\]+)/);
  if (!m) return { host: '', share: '' };
  return { host: m[1] || '', share: m[2] || '' };
}

export async function openConnectorInstanceModal({ mode, type, conn } = {}) {
  const connectorType = String(type || '');
  const isEdit = String(mode) === 'edit';

  const currentName = isEdit ? String(conn?.instance_name || conn?.name || '') : `New ${connectorType}`;
  const currentBaseUrl = isEdit ? String((conn?.config || {}).target_value || '') : '';
  const currentAuthType = isEdit ? String((conn?.config || {}).auth_type || 'token') : 'token';
  const currentUsername = isEdit ? String((conn?.config || {}).username || '') : '';
  const currentInstanceId = isEdit ? String(conn?.instance_id || '') : '';

  let existingExtra = null;
  if (isEdit && connectorType === 'file_server' && currentInstanceId) {
    try {
      const resp = await authFetch(`${API}/connectors/${encodeURIComponent(connectorType)}/instances`);
      if (resp.ok) {
        const data = await resp.json();
        const inst = (data.instances || []).find(x => String(x.id || '') === currentInstanceId) || null;
        existingExtra = (inst && inst.extra && typeof inst.extra === 'object') ? inst.extra : {};
      }
    } catch (_) {
      existingExtra = existingExtra || {};
    }
  }

  const body = document.createElement('div');
  body.className = 'kp-modal-form-wrap';

  const form = document.createElement('form');
  form.className = 'kp-modal-form';
  body.appendChild(form);

  const fields = {};
  fields.name = _kpBuildModalField({
    id: 'kp_conn_name',
    label: 'Name',
    type: 'text',
    value: currentName,
    placeholder: 'Connector name',
    required: true,
  });
  form.appendChild(fields.name.wrap);

  if (connectorType === 'confluence' || connectorType === 'jira') {
    fields.base_url = _kpBuildModalField({
      id: 'kp_conn_base_url',
      label: 'Base URL',
      type: 'text',
      value: currentBaseUrl,
      placeholder: 'https://...',
      required: true,
    });
    form.appendChild(fields.base_url.wrap);

    fields.auth_type = _kpBuildModalField({
      id: 'kp_conn_auth_type',
      label: 'Auth type',
      type: 'select',
      value: (isEdit ? currentAuthType : 'token'),
      options: [
        { value: 'token', label: 'Token' },
        { value: 'basic', label: 'Basic' },
      ],
      required: true,
    });
    form.appendChild(fields.auth_type.wrap);

    fields.username = _kpBuildModalField({
      id: 'kp_conn_username',
      label: 'Email/Username',
      type: 'text',
      value: currentUsername,
      placeholder: 'you@example.com',
      required: false,
    });
    form.appendChild(fields.username.wrap);

    fields.secret = _kpBuildModalField({
      id: 'kp_conn_secret',
      label: 'API token',
      type: 'password',
      value: '',
      placeholder: isEdit ? 'Leave empty to keep current' : '',
      required: !isEdit,
    });
    form.appendChild(fields.secret.wrap);

    const syncUsernameVisibility = () => {
      const auth = String(fields.auth_type.input.value || 'token').toLowerCase().trim();
      const show = auth === 'basic';
      fields.username.wrap.style.display = show ? '' : 'none';
      fields.username.input.disabled = !show;
      if (!show) fields.username.input.value = '';
    };

    fields.auth_type.input.addEventListener('change', syncUsernameVisibility);
    syncUsernameVisibility();
  } else if (connectorType === 'slack') {
    fields.secret = _kpBuildModalField({
      id: 'kp_conn_secret',
      label: 'Slack bot token',
      type: 'password',
      value: '',
      placeholder: isEdit ? 'Leave empty to keep current' : 'xoxb-...',
      required: !isEdit,
    });
    form.appendChild(fields.secret.wrap);
  } else if (connectorType === 'file_server') {
    const smbFromExtra = existingExtra && typeof existingExtra === 'object' ? existingExtra : null;
    const smbParsed = _kpParseSmbBaseUrl(currentBaseUrl);
    const hostValue = (smbFromExtra && smbFromExtra.host) ? String(smbFromExtra.host) : smbParsed.host;
    const shareValue = (smbFromExtra && smbFromExtra.share) ? String(smbFromExtra.share) : smbParsed.share;
    const basePathValue = (smbFromExtra && smbFromExtra.base_path) ? String(smbFromExtra.base_path) : '\\';
    fields.host = _kpBuildModalField({
      id: 'kp_conn_smb_host',
      label: 'SMB host',
      type: 'text',
      value: hostValue,
      placeholder: 'fileserver.local',
      required: false,
      help: 'Leave empty to use server default (SMB_HOST) if configured.',
    });
    form.appendChild(fields.host.wrap);

    fields.share = _kpBuildModalField({
      id: 'kp_conn_smb_share',
      label: 'SMB share',
      type: 'text',
      value: shareValue,
      placeholder: 'ShareName',
      required: false,
      help: 'Leave empty to use server default (SMB_SHARE) if configured.',
    });
    form.appendChild(fields.share.wrap);

    fields.base_path = _kpBuildModalField({
      id: 'kp_conn_smb_base_path',
      label: 'Base path',
      type: 'text',
      value: basePathValue,
      placeholder: '\\\\ or folder',
      required: false,
      help: 'Default is \\\\ .',
    });
    form.appendChild(fields.base_path.wrap);

    fields.username = _kpBuildModalField({
      id: 'kp_conn_username',
      label: 'SMB username',
      type: 'text',
      value: currentUsername,
      placeholder: 'Username',
      required: !isEdit,
    });
    form.appendChild(fields.username.wrap);

    fields.secret = _kpBuildModalField({
      id: 'kp_conn_secret',
      label: 'SMB password',
      type: 'password',
      value: '',
      placeholder: isEdit ? 'Leave empty to keep current' : '',
      required: !isEdit,
    });
    form.appendChild(fields.secret.wrap);
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const okBtn = document.getElementById('kpModalOkBtn');
    if (okBtn) okBtn.click();
  });

  const title = isEdit ? 'Edit connector' : 'Add connector';
  const subtitle = connectorType ? String(connectorType).toUpperCase() : '';

  const result = await kpOpenModal({
    title,
    subtitle,
    content: body,
    okText: isEdit ? 'Save' : 'Create',
    cancelText: 'Cancel',
    okClass: 'primary-btn',
    onOk: () => {
      const name = String(fields.name?.input?.value || '').trim();
      if (!name) return { error: 'Name is required.' };

      if (connectorType === 'confluence' || connectorType === 'jira') {
        const base_url = String(fields.base_url.input.value || '').trim();
        const auth_type = String(fields.auth_type.input.value || 'token').toLowerCase().trim();
        const username = auth_type === 'basic' ? String(fields.username.input.value || '').trim() : '';
        const secret = String(fields.secret.input.value || '').trim();

        if (!base_url) return { error: 'Base URL is required.' };
        if (auth_type !== 'token' && auth_type !== 'basic') return { error: 'Auth type must be token or basic.' };
        if (auth_type === 'basic' && !username) return { error: 'Username is required for basic auth.' };
        if (!isEdit && !secret) return { error: 'API token is required.' };

        const payload = { name, base_url, auth_type, username };
        if (secret) payload.secret = secret;
        return payload;
      }

      if (connectorType === 'slack') {
        const secret = String(fields.secret.input.value || '').trim();
        if (!isEdit && !secret) return { error: 'Slack bot token is required.' };
        const payload = { name };
        if (secret) payload.secret = secret;
        return payload;
      }

      if (connectorType === 'file_server') {
        const host = String(fields.host.input.value || '').trim();
        const share = String(fields.share.input.value || '').trim();
        const base_path = String(fields.base_path.input.value || '').trim();
        const username = String(fields.username.input.value || '').trim();
        const secret = String(fields.secret.input.value || '').trim();

        if (!isEdit && !username) return { error: 'SMB username is required.' };
        if (!isEdit && !secret) return { error: 'SMB password is required.' };

        const prev = (existingExtra && typeof existingExtra === 'object') ? existingExtra : {};
        const finalHost = host || String(prev.host || '').trim() || '';
        const finalShare = share || String(prev.share || '').trim() || '';
        const finalBasePath = base_path || String(prev.base_path || '').trim() || '\\';
        const finalUsername = username || (isEdit ? currentUsername : '') || '';

        const base_url = (finalHost && finalShare) ? `\\\\${finalHost}\\${finalShare}` : (currentBaseUrl || '');
        const payload = {
          name,
          base_url,
          auth_type: 'basic',
          username: finalUsername,
          extra: { host: finalHost, share: finalShare, base_path: finalBasePath },
        };
        if (secret) payload.secret = secret;
        return payload;
      }

      return { name };
    },
  });

  if (!result) return null;
  if (typeof result !== 'object') return null;

  if (!isEdit) {
    return {
      name: result.name,
      base_url: result.base_url ?? null,
      auth_type: result.auth_type ?? 'token',
      username: result.username ?? null,
      secret: result.secret ?? null,
      extra: result.extra ?? null,
    };
  }

  return result;
}

export async function syncCurrentConnectorTab() {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const tab = String(connectorActiveTab || 'confluence');
  const button = document.getElementById('syncTabConnectorsBtn');
  if (button) {
    button.disabled = true;
    button.textContent = 'Starting...';
  }

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(tab)}/sync-all`, { method: 'POST' });
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const started = data.started || [];
    const skipped = data.skipped || [];
    if (!started.length) {
      showToast(`Không có connector nào được sync cho ${tab}.`, skipped.length ? 'info' : 'error');
      await loadConnectorStats(true);
      return;
    }

    showToast(`Đã bắt đầu ${started.length} sync cho ${tab}.`, 'success');
    await openSyncProgressModal({
      title: `Sync progress · ${tab.toUpperCase()}`,
      connectors: started,
      skipped,
    });
  } catch (error) {
    showToast(error.message || `Cannot sync ${tab}.`, 'error');
  } finally {
    if (button) {
      button.disabled = !AUTH.user.is_admin;
      button.textContent = `Sync ${tab.toUpperCase()}`;
    }
  }
}

export async function clearCurrentConnectorTab() {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const tab = String(connectorActiveTab || 'confluence');
  const ok = await kpConfirm({
    title: 'Clear connector data',
    message: `Clear ALL synced data from ${tab} (Postgres + Qdrant) for demo? This cannot be undone.`,
    okText: 'Clear',
    cancelText: 'Cancel',
    danger: true,
  });
  if (!ok) return;

  const btn = document.getElementById('clearTabDataBtn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Clearing...';
  }

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(tab)}/clear`, { method: 'POST' });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Cleared ${tab} demo data.`);
    connectorDiagnostics = {};
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Clear failed.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = `Clear ${tab.toUpperCase()}`;
    }
  }
}

export async function clearAllKnowledgeBase() {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const ok = await kpConfirm({
    title: 'Clear ALL data',
    message: 'Clear ALL synced data (Postgres + Qdrant)? This cannot be undone.',
    okText: 'Clear ALL',
    cancelText: 'Cancel',
    danger: true,
  });
  if (!ok) return;

  const btn = document.getElementById('clearAllDataBtn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Clearing...';
  }

  try {
    const response = await authFetch(`${API}/connectors/clear`, { method: 'POST' });
    if (!response.ok) throw new Error(await readApiError(response));
    connectorDiagnostics = {};
    showToast('Cleared ALL demo data.', 'success');
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Clear failed.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Clear ALL';
    }
  }
}

export async function loadConnectorStats(force = false) {
  if (!AUTH.token) return;
  if (!force && document.getElementById('page-connectors') && !document.getElementById('page-connectors').classList.contains('active')) {
    // Keep catalog warm in background, but skip expensive rerenders if the page is not active.
  }

  try {
    const response = await authFetch(`${API}/connectors`);
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json();
    Object.assign(connectorDirectory, data);

    // Build fast lookup
    for (const key in connectorIndex) delete connectorIndex[key];
    (connectorDirectory.tabs || []).forEach(tab => {
      (tab.instances || []).forEach(conn => {
        if (conn && conn.id) connectorIndex[String(conn.id)] = conn;
      });
    });
    if (!(connectorDirectory.tabs || []).some(t => String(t.type) === String(connectorActiveTab))) {
      connectorActiveTab = ((connectorDirectory.tabs || [])[0] || {}).type || 'confluence';
      localStorage.setItem('kp_connector_tab', connectorActiveTab);
    }
    renderConnectorDashboard();
  } catch (error) {
    console.warn('Cannot load connector stats:', error);
    const grid = document.getElementById('connectorsGrid');
    if (grid && document.getElementById('page-connectors')?.classList.contains('active')) {
      grid.innerHTML = `<div class="connectors-empty" style="color:var(--danger)">Failed to load connectors: ${escapeHtml(error.message || 'API error')}</div>`;
    }
  }
}