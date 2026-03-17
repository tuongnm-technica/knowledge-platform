import { API, AUTH, authFetch } from '../api/client.js';
import { readApiError, escapeHtml, showToast, kpConfirm, _kpBuildModalField } from '../utils/ui.js';

export let tasksDirectory = { drafts: [] };
export let taskSelection = new Set();
export let taskGroupCollapsed = {};

export async function loadTasksCount() {
  try {
    const response = await authFetch(`${API}/tasks/count`);
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json();
    updateTasksCount(data.count || 0);
  } catch (error) {
    console.warn('Cannot load task count:', error);
  }
}

export function updateTasksCount(count) {
  const badge = document.getElementById('tasksBadge');
  const panel = document.getElementById('tasksPanelCount');

  if (badge) {
    badge.textContent = count;
    badge.style.display = count ? 'inline-block' : 'none';
  }
  if (panel) {
    panel.textContent = `${count} open`;
  }
}

export function normalizeEvidence(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return [];
}

export function updateBulkBar() {
  const bar = document.getElementById('tasksBulkBar');
  const countEl = document.getElementById('tasksBulkCount');
  const count = taskSelection.size;
  if (countEl) countEl.textContent = `${count} selected`;
  if (bar) bar.style.display = count ? '' : 'none';
}

export function toggleTaskSelect(id, checked) {
  const key = String(id);
  if (checked) taskSelection.add(key);
  else taskSelection.delete(key);
  updateBulkBar();
}

export function clearTaskSelection() {
  taskSelection = new Set();
  document.querySelectorAll('input[data-task-select]').forEach(el => { el.checked = false; });
  updateBulkBar();
}

export function selectedTaskIds() {
  return Array.from(taskSelection.values());
}

export async function bulkConfirmTasks() {
  const ids = selectedTaskIds();
  if (!ids.length) return;
  try {
    const response = await authFetch(`${API}/tasks/batch/confirm`, {
      method: 'POST',
      body: JSON.stringify({ ids }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Confirmed ${ids.length} tasks.`, 'success');
    clearTaskSelection();
    await loadTasks();
    await loadTasksCount();
  } catch (error) {
    showToast(error.message || 'Bulk confirm failed.', 'error');
  }
}

export async function bulkRejectTasks() {
  const ids = selectedTaskIds();
  if (!ids.length) return;
  const ok = await kpConfirm({
    title: 'Dismiss tasks',
    message: `Dismiss ${ids.length} selected tasks?`,
    okText: 'Dismiss',
    cancelText: 'Cancel',
    danger: true,
  });
  if (!ok) return;
  try {
    const response = await authFetch(`${API}/tasks/batch/reject`, {
      method: 'POST',
      body: JSON.stringify({ ids }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Dismissed ${ids.length} tasks.`, 'success');
    clearTaskSelection();
    await loadTasks();
    await loadTasksCount();
  } catch (error) {
    showToast(error.message || 'Bulk dismiss failed.', 'error');
  }
}

export async function bulkAssignTasks() {
  const ids = selectedTaskIds();
  if (!ids.length) return;
  const assigneeEl = document.getElementById('bulkAssigneeInput');
  const suggested_assignee = assigneeEl ? (assigneeEl.value || '').trim() : '';
  if (!suggested_assignee) {
    showToast('Please enter an assignee (email/name).', 'error');
    return;
  }
  try {
    const response = await authFetch(`${API}/tasks/batch/update`, {
      method: 'POST',
      body: JSON.stringify({ ids, suggested_assignee }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Assigned ${ids.length} tasks.`, 'success');
    clearTaskSelection();
    await loadTasks();
  } catch (error) {
    showToast(error.message || 'Bulk assign failed.', 'error');
  }
}

export async function bulkSetIssueType() {
  const ids = selectedTaskIds();
  if (!ids.length) return;
  const el = document.getElementById('bulkIssueTypeInput');
  const issue_type = el ? (el.value || '').trim() : '';
  if (!issue_type || !['Task', 'Story', 'Bug', 'Epic'].includes(issue_type)) {
    showToast('Issue type must be one of: Task, Story, Bug, Epic.', 'error');
    return;
  }
  try {
    const response = await authFetch(`${API}/tasks/batch/update`, {
      method: 'POST',
      body: JSON.stringify({ ids, issue_type }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Updated type for ${ids.length} tasks.`, 'success');
    await loadTasks();
  } catch (error) {
    showToast(error.message || 'Bulk update failed.', 'error');
  }
}

export function toggleTaskGroup(groupId) {
  const key = String(groupId || '');
  taskGroupCollapsed[key] = !taskGroupCollapsed[key];
  const body = document.getElementById(`taskGroupBody-${key}`);
  const chev = document.getElementById(`taskGroupChevron-${key}`);
  if (body) body.style.display = taskGroupCollapsed[key] ? 'none' : 'block';
  if (chev) chev.textContent = taskGroupCollapsed[key] ? '▸' : '▾';
}

export function setTaskSelection(ids, selected) {
  (ids || []).forEach(id => {
    const safeId = String(id || '');
    if (!safeId) return;
    if (selected) taskSelection.add(safeId); else taskSelection.delete(safeId);
    const input = document.querySelector(`input[data-task-select][data-task-id="${safeId}"]`);
    if (input) input.checked = selected;
  });
  updateBulkBar();
}

export function selectTaskGroup(groupId, selected) {
  const gid = String(groupId || '');
  const group = (tasksDirectory.groups || []).find(g => String(g.id || '') === gid);
  if (!group) return;
  setTaskSelection(group.draft_ids || [], !!selected);
}

export function renderTaskGroups(groups, drafts) {
  const byId = new Map();
  (drafts || []).forEach(d => byId.set(String(d.id || ''), d));

  return (groups || []).map(g => {
    const gid = String(g.id || '');
    const collapsed = !!taskGroupCollapsed[gid];
    const items = (g.draft_ids || []).map(id => byId.get(String(id || ''))).filter(Boolean);
    const cards = items.map(renderTaskCard).join('');
    const title = escapeHtml(g.title || gid);
    const count = Number(g.count || items.length || 0);
    return `
      <div class="task-group" data-group-id="${escapeHtml(gid)}">
        <div class="task-group-head">
          <button class="task-group-toggle" onclick="toggleTaskGroup('${escapeHtml(gid)}')" aria-label="Toggle group">
            <span id="taskGroupChevron-${escapeHtml(gid)}">${collapsed ? '▸' : '▾'}</span>
          </button>
          <div class="task-group-title">${title}</div>
          <span class="count-pill">${count} items</span>
          <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
            <button class="secondary-btn mini" onclick="selectTaskGroup('${escapeHtml(gid)}', true)">Select</button>
            <button class="secondary-btn mini" onclick="selectTaskGroup('${escapeHtml(gid)}', false)">Clear</button>
          </div>
        </div>
        <div class="task-group-body" id="taskGroupBody-${escapeHtml(gid)}" style="display:${collapsed ? 'none' : 'block'}">
          ${cards || `<div class="tasks-empty">No items.</div>`}
        </div>
      </div>
    `;
  }).join('');
}

export function renderTaskCard(draft) {
  const srcType = String(draft.source_type || '').toLowerCase();
  const srcIcon = srcType === 'slack' ? '💬' : (srcType === 'confluence' ? '📘' : '🤖');
  const srcRefSafe = escapeHtml(draft.source_ref || '');
  const srcLabel = srcType === 'slack' ? `Slack ${srcRefSafe}` : (srcType === 'confluence' ? 'Confluence' : 'Chat');
  const issueType = escapeHtml(draft.issue_type || 'Task');
  const issueTypeChip = `<span class="task-chip" style="background:rgba(15,118,110,0.10);border-color:rgba(15,118,110,0.18);color:var(--text)">#${issueType}</span>`;
  const status = String(draft.status || '');
  const statusPill = status === 'confirmed'
    ? `<span class="task-chip" style="background:#dcfce7;color:#166534;border:1px solid rgba(34,197,94,0.25)">Confirmed</span>`
    : (status === 'submitted'
      ? `<span class="task-chip" style="background:rgba(59,130,246,0.12);color:#1d4ed8;border:1px solid rgba(59,130,246,0.18)">Submitted</span>`
      : (status === 'done'
        ? `<span class="task-chip" style="background:rgba(34,197,94,0.12);color:#166534;border:1px solid rgba(34,197,94,0.18)">Done</span>`
        : ''));
  const priBadge = {
    High: 'background:#fee2e2;color:#b91c1c',
    Medium: 'background:#fef3c7;color:#b45309',
    Low: 'background:#dcfce7;color:#166534',
  }[draft.priority] || 'background:rgba(255,255,255,0.72);color:var(--text-muted)';
  const labels = (draft.labels || []).map(label => `<span class="task-chip">${label}</span>`).join('');
  const assignee = draft.suggested_assignee ? `<span class="task-chip">👤 ${escapeHtml(draft.suggested_assignee)}</span>` : '';
  const sourceLink = draft.source_url
    ? `<a class="task-chip" href="${escapeHtml(draft.source_url)}" target="_blank" rel="noopener" style="text-decoration:none">🔗 Open source</a>`
    : '';
  const jiraKey = String(draft.jira_key || '').trim();
  const jiraUrl = String(draft.jira_url || '').trim();
  const jiraLink = jiraKey && jiraUrl
    ? `<a class="task-chip" href="${escapeHtml(jiraUrl)}" target="_blank" rel="noopener" style="text-decoration:none">Jira ${escapeHtml(jiraKey)}</a>`
    : (jiraKey ? `<span class="task-chip">Jira ${escapeHtml(jiraKey)}</span>` : '');
  const jiraStatus = draft.suggested_fields && (draft.suggested_fields.jira_status || '');
  const jiraStatusChip = jiraStatus ? `<span class="task-chip">Jira: ${escapeHtml(jiraStatus)}</span>` : '';

  const summary = draft.source_summary
    ? `<div class="task-summary">${escapeHtml(draft.source_summary.substring(0, 180))}...</div>`
    : '';

  const isSelected = taskSelection.has(String(draft.id));
  const safeId = String(draft.id || '').replace(/'/g, '');
  const selectBox = `<label class="task-select"><input data-task-select data-task-id="${safeId}" type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleTaskSelect('${safeId}', this.checked)"></label>`;

  const evidenceItems = normalizeEvidence(draft.evidence);
  let evidenceMarkup = '';
  if (evidenceItems.length) {
    const items = evidenceItems.slice(0, 2).map(ev => {
      const evUrl = String(ev.url || '').trim();
      const evQuote = String(ev.quote || '').trim();
      const evSource = String(ev.source || '').trim();
      const evTitle = String(ev.title || '').trim();
      const link = evUrl ? `<a href="${escapeHtml(evUrl)}" target="_blank" rel="noopener" class="task-chip" style="text-decoration:none">Open</a>` : '';
      return `
        <div class="evidence-item">
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <span class="task-chip">${escapeHtml(evSource || 'source')}</span>
            ${evTitle ? `<span class="task-chip">${escapeHtml(evTitle)}</span>` : ''}
            ${link}
          </div>
          ${evQuote ? `<div class="evidence-quote">${escapeHtml(evQuote)}</div>` : ''}
        </div>
      `;
    }).join('');
    evidenceMarkup = `
      <div class="task-evidence">
        <div class="task-evidence-title">Evidence</div>
        ${items}
      </div>
    `;
  }

  const isLocked = status === 'submitted' || status === 'done';
  const primaryAction = isLocked
    ? (jiraUrl
      ? `<a href="${escapeHtml(jiraUrl)}" target="_blank" rel="noopener" class="task-action primary" style="text-decoration:none;display:inline-flex;align-items:center;justify-content:center">Open Jira</a>`
      : `<button class="task-action primary" disabled>Submitted</button>`)
    : `<button onclick="submitTask('${draft.id}')" class="task-action primary">Create Jira</button>`;
  const editAction = isLocked
    ? ''
    : `<button onclick="confirmTask('${draft.id}')" class="task-action ghost">${status === 'confirmed' ? 'Edit' : 'Edit & Confirm'}</button>`;
  const dismissAction = isLocked
    ? ''
    : `<button onclick="rejectTask('${draft.id}')" class="task-action danger">Dismiss</button>`;

  return `<div id="task-${draft.id}" class="task-card">
    <div class="task-head">
      <div style="flex:1">
        <div class="task-title">${escapeHtml(draft.title || '')}</div>
        <div class="task-desc">${escapeHtml(draft.description || '')}</div>
      </div>
      <span class="priority-pill" style="${priBadge}">${draft.priority}</span>
    </div>
    <div class="task-meta">
      ${selectBox}
      <span class="task-chip">${srcIcon} ${srcLabel}</span>
      ${issueTypeChip}
      ${statusPill}
      ${assignee}
      ${labels}
      ${sourceLink}
      ${jiraLink}
      ${jiraStatusChip}
    </div>
    ${summary}
    ${evidenceMarkup}
    <div class="task-actions">
      ${primaryAction}
      ${editAction}
      ${dismissAction}
    </div>
  </div>`;
}

export function loadTasks() {
  const includeSubmitted = !!document.getElementById('tasksIncludeSubmitted')?.checked;
  const url = includeSubmitted ? `${API}/tasks?include_submitted=true` : `${API}/tasks`;
  return authFetch(url)
    .then(async response => {
      if (!response.ok) {
        throw new Error(await readApiError(response));
      }
      return response.json();
    })
    .then(data => {
      const drafts = data.drafts || [];
      const groups = data.groups || [];
      tasksDirectory.drafts = drafts;
      tasksDirectory.groups = groups;
      const list = document.getElementById('tasksList');
      if (!list) return;

      if (!drafts.length) {
        list.innerHTML = `<div class="tasks-empty">No draft tasks yet. Click scan to start.</div>`;
        updateTasksCount(0);
        return;
      }

      if (groups && groups.length) {
        list.innerHTML = renderTaskGroups(groups, drafts);
      } else {
        list.innerHTML = drafts.map(renderTaskCard).join('');
      }
      updateTasksCount(drafts.length);
      updateBulkBar();
    })
    .catch(error => {
      console.error('[Tasks] loadTasks error:', error);
      const list = document.getElementById('tasksList');
      if (list) {
        list.innerHTML = `<div class="tasks-empty" style="color:var(--danger)">Failed to load tasks.</div>`;
      }
    });
}

export async function submitTask(id) {
  const ok = await kpConfirm({
    title: 'Create Jira task',
    message: 'Create Jira task from this draft?',
    okText: 'Create',
    cancelText: 'Cancel',
  });
  if (!ok) return;
  try {
    const response = await authFetch(`${API}/tasks/${id}/submit`, { method: 'POST' });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json();
    const card = document.getElementById(`task-${id}`);
    if (card) {
      const jiraLink = data.jira_url
        ? `<a href="${data.jira_url}" target="_blank" style="color:#166534">${data.jira_key}</a>`
        : escapeHtml(data.jira_key || 'created');
      card.innerHTML = `<div class="task-summary" style="background:#dcfce7;color:#166534;border-left-color:#22c55e;font-weight:700">Created ${jiraLink}</div>`;
    }
    await loadTasks();
    loadTasksCount();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

export async function triggerScan() {
  const btn = document.getElementById('scanBtn');
  const slackDaysEl = document.getElementById('slackDaysInput');
  const confDaysEl = document.getElementById('confluenceDaysInput');
  const slack_days = Math.max(1, Number(slackDaysEl ? slackDaysEl.value : 1) || 1);
  const confluence_days = Math.max(1, Number(confDaysEl ? confDaysEl.value : 1) || 1);
  if (btn) {
    btn.textContent = 'Scanning...';
    btn.disabled = true;
  }

  try {
    const response = await authFetch(`${API}/tasks/scan`, {
      method: 'POST',
      body: JSON.stringify({ slack_days, confluence_days }),
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    showToast('Scanning sources. Results will appear shortly.');
    setTimeout(async () => {
      await loadTasks();
      if (btn) {
        btn.textContent = 'Scan Slack + Confluence';
        btn.disabled = false;
      }
    }, 15000);
  } catch (error) {
    if (btn) {
      btn.textContent = 'Scan Slack + Confluence';
      btn.disabled = false;
    }
    showToast(error.message, 'error');
  }
}

export async function rejectTask(id) {
  try {
    const response = await authFetch(`${API}/tasks/${id}/reject`, { method: 'POST' });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const card = document.getElementById(`task-${id}`);
    if (card) card.style.opacity = '0.3';
    setTimeout(() => {
      const current = document.getElementById(`task-${id}`);
      if (current) current.remove();
      loadTasksCount();
    }, 280);
  } catch (error) {
    showToast(error.message, 'error');
  }
}

export async function confirmTask(id) {
  const current = (tasksDirectory.drafts || []).find(d => String(d.id) === String(id)) || {};
  const body = document.createElement('div');
  body.className = 'kp-modal-form-wrap';

  const form = document.createElement('form');
  form.className = 'kp-modal-form';
  body.appendChild(form);

  const fields = {};
  fields.issue_type = _kpBuildModalField({
    id: `kp_task_issue_type_${id}`,
    label: 'Issue type',
    type: 'select',
    value: String(current.issue_type || 'Task'),
    options: [
      { value: 'Task', label: 'Task' },
      { value: 'Story', label: 'Story' },
      { value: 'Bug', label: 'Bug' },
      { value: 'Epic', label: 'Epic' },
    ],
    required: true,
  });
  form.appendChild(fields.issue_type.wrap);

  fields.epic_key = _kpBuildModalField({
    id: `kp_task_epic_key_${id}`,
    label: 'Epic key (optional)',
    type: 'text',
    value: String(current.epic_key || ''),
    placeholder: 'EPIC-123',
    help: 'Link this draft to an Epic (leave empty to skip).',
  });
  form.appendChild(fields.epic_key.wrap);

  fields.title = _kpBuildModalField({
    id: `kp_task_title_${id}`,
    label: 'Title',
    type: 'text',
    value: String(current.title || ''),
    placeholder: 'Short summary',
    required: true,
  });
  form.appendChild(fields.title.wrap);

  fields.description = _kpBuildModalField({
    id: `kp_task_desc_${id}`,
    label: 'Description',
    type: 'textarea',
    value: String(current.description || ''),
    placeholder: 'Details (optional)',
  });
  form.appendChild(fields.description.wrap);

  fields.assignee = _kpBuildModalField({
    id: `kp_task_assignee_${id}`,
    label: 'Suggested assignee (optional)',
    type: 'text',
    value: String(current.suggested_assignee || ''),
    placeholder: 'email or name',
  });
  form.appendChild(fields.assignee.wrap);

  fields.priority = _kpBuildModalField({
    id: `kp_task_priority_${id}`,
    label: 'Priority',
    type: 'select',
    value: String(current.priority || 'Medium'),
    options: [
      { value: 'High', label: 'High' },
      { value: 'Medium', label: 'Medium' },
      { value: 'Low', label: 'Low' },
    ],
    required: true,
  });
  form.appendChild(fields.priority.wrap);

  fields.labels = _kpBuildModalField({
    id: `kp_task_labels_${id}`,
    label: 'Labels (optional)',
    type: 'text',
    value: (current.labels || []).join(', '),
    placeholder: 'comma-separated',
  });
  form.appendChild(fields.labels.wrap);

  fields.components = _kpBuildModalField({
    id: `kp_task_components_${id}`,
    label: 'Components (optional)',
    type: 'text',
    value: (current.components || []).join(', '),
    placeholder: 'comma-separated',
  });
  form.appendChild(fields.components.wrap);

  fields.due_date = _kpBuildModalField({
    id: `kp_task_due_${id}`,
    label: 'Due date (optional)',
    type: 'date',
    value: String(current.due_date || ''),
    help: 'YYYY-MM-DD',
  });
  form.appendChild(fields.due_date.wrap);

  fields.jira_project = _kpBuildModalField({
    id: `kp_task_project_${id}`,
    label: 'Jira project key (optional)',
    type: 'text',
    value: String(current.jira_project || ''),
    placeholder: 'e.g. TECH',
  });
  form.appendChild(fields.jira_project.wrap);

  const syncEpicVisibility = () => {
    const issueType = String(fields.issue_type.input.value || 'Task').trim();
    const showEpic = issueType !== 'Epic';
    fields.epic_key.wrap.style.display = showEpic ? '' : 'none';
    fields.epic_key.input.disabled = !showEpic;
    if (!showEpic) fields.epic_key.input.value = '';
  };
  fields.issue_type.input.addEventListener('change', syncEpicVisibility);
  syncEpicVisibility();

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const okBtn = document.getElementById('kpModalOkBtn');
    if (okBtn) okBtn.click();
  });

  const result = await kpOpenModal({
    title: 'Confirm task draft',
    subtitle: 'Jira fields',
    content: body,
    okText: 'Confirm',
    cancelText: 'Cancel',
    okClass: 'primary-btn',
    onOk: () => {
      const issue_type = String(fields.issue_type.input.value || '').trim();
      const title = String(fields.title.input.value || '').trim();
      const description = String(fields.description.input.value || '').trim();
      const suggested_assignee = String(fields.assignee.input.value || '').trim();
      const priority = String(fields.priority.input.value || '').trim();
      const labelsRaw = String(fields.labels.input.value || '');
      const componentsRaw = String(fields.components.input.value || '');
      const due_date = String(fields.due_date.input.value || '').trim();
      const jira_project = String(fields.jira_project.input.value || '').trim();
      const epic_key = fields.epic_key.input.disabled ? '' : String(fields.epic_key.input.value || '').trim();

      if (!issue_type || !['Task', 'Story', 'Bug', 'Epic'].includes(issue_type)) return { error: 'Issue type must be Task/Story/Bug/Epic.' };
      if (!priority || !['High', 'Medium', 'Low'].includes(priority)) return { error: 'Priority must be High/Medium/Low.' };
      if (!title) return { error: 'Title is required.' };
      if (due_date && !/^\d{4}-\d{2}-\d{2}$/.test(due_date)) return { error: 'Due date must be YYYY-MM-DD.' };

      const labels = labelsRaw.split(',').map(s => s.trim()).filter(Boolean);
      const components = componentsRaw.split(',').map(s => s.trim()).filter(Boolean);

      return {
        issue_type,
        epic_key: epic_key || null,
        title,
        description: description || null,
        suggested_assignee: suggested_assignee || null,
        priority: priority || null,
        jira_project: jira_project || null,
        labels: labels.length ? labels : null,
        components: components.length ? components : null,
        due_date: due_date || null,
      };
    },
  });
  if (!result) return;
  try {
    const response = await authFetch(`${API}/tasks/${id}/confirm`, {
      method: 'POST',
      body: JSON.stringify(result),
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    showToast('Draft confirmed. You can submit it to Jira now.');
    await loadTasks();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

export async function syncJiraStatuses() {
  if (!AUTH.user.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  try {
    const response = await authFetch(`${API}/tasks/sync-jira-status?limit=80`, { method: 'POST' });
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const stats = data.stats || {};
    showToast(`Jira sync: checked ${stats.checked || 0}, updated ${stats.updated || 0}.`, 'success');
    await loadTasks();
  } catch (error) {
    showToast(error.message || 'Jira sync failed.', 'error');
  }
}