import { API, AUTH, authFetch } from '../api/client.js';
import { readApiError, escapeHtml, showToast, kpConfirm } from '../utils/ui.js';

export let adminDirectory = { users: [], groups: [] };
export let userEditorState = null;
export let groupEditorState = null;

export function normalizeUserRole(role, isAdmin) {
  if (isAdmin) return 'system_admin';
  const r = String(role || '').trim().toLowerCase();
  const aliases = {
    admin: 'system_admin',
    system_admin: 'system_admin',
    sysadmin: 'system_admin',
    knowledge_architect: 'knowledge_architect',
    prompt_engineer: 'knowledge_architect',
    pm: 'pm_po',
    po: 'pm_po',
    product_owner: 'pm_po',
    project_manager: 'pm_po',
    team_lead: 'pm_po',
    lead: 'pm_po',
    ba: 'ba_sa',
    sa: 'ba_sa',
    business_analyst: 'ba_sa',
    system_analyst: 'ba_sa',
    dev: 'dev_qa',
    developer: 'dev_qa',
    qa: 'dev_qa',
    qa_engineer: 'dev_qa',
    member: 'standard',
    standard: 'standard',
  };
  return aliases[r] || (r || 'standard');
}

export function getUserRoleLabel(roleCode) {
  const labels = {
    system_admin: 'System Administrator',
    knowledge_architect: 'Knowledge Architect / Prompt Engineer',
    pm_po: 'Project Manager / Product Owner',
    ba_sa: 'Business Analyst / System Analyst',
    dev_qa: 'Developer / QA Engineer',
    standard: 'Standard Member / Newcomer',
  };
  return labels[String(roleCode || '').toLowerCase()] || 'Standard Member / Newcomer';
}

export function getUserRoleTagClass(roleCode) {
  const code = String(roleCode || '').toLowerCase();
  if (code === 'system_admin') return 'tag-blue';
  if (code === 'knowledge_architect') return 'tag-purple';
  return 'tag-green';
}

export function getUserDisplayName(user) {
  return user.display_name || user.email || user.id;
}

export function renderUsersAccessDenied() {
  const usersBody = document.getElementById('usersTableBody');
  const groupsBody = document.getElementById('groupsTableBody');
  if (usersBody) {
    usersBody.innerHTML = `<tr><td colspan="6" class="muted-cell">Admin access required.</td></tr>`;
  }
  if (groupsBody) {
    groupsBody.innerHTML = `<tr><td colspan="4" class="muted-cell">Admin access required.</td></tr>`;
  }
  closeUserEditor();
  closeGroupEditor();
}

export async function loadUsersAdmin() {
  if (!AUTH.user.is_admin) {
    renderUsersAccessDenied();
    return;
  }

  const usersBody = document.getElementById('usersTableBody');
  const groupsBody = document.getElementById('groupsTableBody');
  if (usersBody) {
    usersBody.innerHTML = `<tr><td colspan="6" class="muted-cell">Loading users...</td></tr>`;
  }
  if (groupsBody) {
    groupsBody.innerHTML = `<tr><td colspan="4" class="muted-cell">Loading groups...</td></tr>`;
  }

  try {
    const response = await authFetch(`${API}/users`);
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    const data = await response.json();
    adminDirectory = {
      users: data.users || [],
      groups: data.groups || [],
    };

    renderUsersTable(adminDirectory.users);
    renderGroupsTable(adminDirectory.groups);

    if (userEditorState) renderUserEditor();
    if (groupEditorState) renderGroupEditor();
  } catch (error) {
    if (usersBody) {
      usersBody.innerHTML = `<tr><td colspan="6" class="muted-cell" style="color:var(--danger)">Failed to load users: ${escapeHtml(error.message)}</td></tr>`;
    }
    if (groupsBody) {
      groupsBody.innerHTML = `<tr><td colspan="4" class="muted-cell" style="color:var(--danger)">Failed to load groups: ${escapeHtml(error.message)}</td></tr>`;
    }
    showToast(error.message, 'error');
  }
}

export function renderUsersTable(users) {
  const body = document.getElementById('usersTableBody');
  if (!body) return;

  if (!users.length) {
    body.innerHTML = `<tr><td colspan="6" class="muted-cell">No users yet.</td></tr>`;
    return;
  }

  body.innerHTML = users.map(user => {
    const displayName = escapeHtml(getUserDisplayName(user));
    const email = escapeHtml(user.email);
    const initials = escapeHtml((displayName[0] || 'U').toUpperCase());
    const groups = (user.groups || []).map(group => (
      `<span class="tag ${group.id === 'group_admin' ? 'tag-blue' : 'tag-purple'}">${escapeHtml(group.name || group.id)}</span>`
    )).join(' ');
    const roleCode = normalizeUserRole(user.role, user.is_admin);
    const roleClass = getUserRoleTagClass(roleCode);
    const statusClass = user.is_active ? 'tag-green' : 'tag-purple';
    const toggleLabel = user.is_active ? 'Disable' : 'Enable';

    return `<tr>
      <td>
        <div class="user-td">
          <div class="avatar-sm">${initials}</div>
          <div>
            <div style="font-weight:600">${displayName}</div>
            <div class="muted-cell">${escapeHtml(user.id)}</div>
          </div>
        </div>
      </td>
      <td>${email}</td>
      <td>${groups || '<span class="muted-cell">No groups</span>'}</td>
      <td><span class="tag ${roleClass}">${escapeHtml(getUserRoleLabel(roleCode))}</span></td>
      <td><span class="tag ${statusClass}">${user.is_active ? 'Active' : 'Inactive'}</span></td>
      <td>
        <button class="action-btn" onclick="editUser('${escapeHtml(user.id)}')">Edit</button>
        <button class="action-btn" onclick="toggleUserActive('${escapeHtml(user.id)}')">${toggleLabel}</button>
      </td>
    </tr>`;
  }).join('');
}

export function renderGroupsTable(groups) {
  const body = document.getElementById('groupsTableBody');
  if (!body) return;

  if (!groups.length) {
    body.innerHTML = `<tr><td colspan="4" class="muted-cell">No groups yet.</td></tr>`;
    return;
  }

  body.innerHTML = groups.map(group => {
    const members = (group.members || [])
      .map(member => escapeHtml(member.display_name || member.email || member.id))
      .slice(0, 4);
    const extraCount = Math.max((group.member_count || 0) - members.length, 0);
    const membersLabel = members.length ? members.join(', ') : 'No members';
    const suffix = extraCount ? ` +${extraCount}` : '';

    return `<tr>
      <td>
        <div style="font-weight:600">${escapeHtml(group.name)}</div>
        <div class="muted-cell">${escapeHtml(group.id)}</div>
      </td>
      <td class="muted-cell">${membersLabel}${suffix}</td>
      <td><span class="tag tag-blue">${group.member_count || 0} users</span></td>
      <td><button class="action-btn" onclick="editGroup('${escapeHtml(group.id)}')">Edit</button></td>
    </tr>`;
  }).join('');
}

export function openCreateUser() {
  userEditorState = { mode: 'create', userId: null };
  renderUserEditor();
}

export function editUser(userId) {
  userEditorState = { mode: 'edit', userId };
  renderUserEditor();
}

export function closeUserEditor() {
  userEditorState = null;
  const panel = document.getElementById('userEditorPanel');
  if (!panel) return;
  panel.classList.remove('active');
  panel.innerHTML = '';
}

export function renderUserEditor() {
  const panel = document.getElementById('userEditorPanel');
  if (!panel) return;
  if (!userEditorState) {
    closeUserEditor();
    return;
  }

  const isEdit = userEditorState.mode === 'edit';
  const user = isEdit
    ? adminDirectory.users.find(item => item.id === userEditorState.userId)
    : null;

  if (isEdit && !user) {
    closeUserEditor();
    showToast('User no longer exists.', 'error');
    return;
  }

  const selectedGroupIds = new Set(user?.group_ids || []);
  const selectedRoleCode = normalizeUserRole(user?.role, user?.is_admin);
  const roleOptions = [
    'standard',
    'dev_qa',
    'ba_sa',
    'pm_po',
    'knowledge_architect',
    'system_admin',
  ].map(code => `
    <option value="${escapeHtml(code)}" ${code === selectedRoleCode ? 'selected' : ''}>
      ${escapeHtml(getUserRoleLabel(code))}
    </option>
  `).join('');
  const groupOptions = adminDirectory.groups.length
    ? adminDirectory.groups.map(group => `
        <label class="admin-group-option">
          <input
            type="checkbox"
            name="group_ids"
            value="${escapeHtml(group.id)}"
            ${selectedGroupIds.has(group.id) ? 'checked' : ''}
          />
          <span>${escapeHtml(group.name)}</span>
        </label>
      `).join('')
    : `<div class="admin-editor-note">No groups yet. Create groups first or save without groups.</div>`;

  panel.classList.add('active');
  panel.innerHTML = `
    <form onsubmit="submitUserEditor(event)">
      <div class="admin-editor-head">
        <div>
          <div class="admin-editor-title">${isEdit ? 'Edit user' : 'Create user'}</div>
          <div class="admin-editor-note">${isEdit ? escapeHtml(user.id) : 'New user account and access settings'}</div>
        </div>
        <button type="button" class="admin-secondary" onclick="closeUserEditor()">Close</button>
      </div>

      <div class="admin-form-grid">
        <div class="admin-field">
          <label for="user-display-name">Display name</label>
          <input id="user-display-name" name="display_name" value="${escapeHtml(user?.display_name || '')}" required />
        </div>
        <div class="admin-field">
          <label for="user-email">Email</label>
          <input id="user-email" name="email" type="email" value="${escapeHtml(user?.email || '')}" required />
        </div>
        <div class="admin-field">
          <label for="user-role">Role</label>
          <select id="user-role" name="role">${roleOptions}</select>
        </div>
        <div class="admin-field">
          <label for="user-password">${isEdit ? 'New password (optional)' : 'Password'}</label>
          <input id="user-password" name="password" type="password" ${isEdit ? '' : 'required'} minlength="8" />
        </div>
      </div>

      <div class="admin-inline-checks">
        <label class="admin-check">
          <input type="checkbox" name="is_active" ${user?.is_active === false ? '' : 'checked'} />
          <span>Active</span>
        </label>
      </div>

      <div class="admin-editor-note" style="margin-top:14px">Group membership</div>
      <div class="admin-group-picker">${groupOptions}</div>

      <div class="admin-editor-actions">
        <button type="submit" class="add-btn" data-submit-label>${isEdit ? 'Save changes' : 'Create user'}</button>
        <button type="button" class="admin-secondary" onclick="closeUserEditor()">Cancel</button>
      </div>
    </form>
  `;
}

export async function submitUserEditor(event) {
  event.preventDefault();
  if (!userEditorState) return;

  const form = event.target;
  const button = form.querySelector('[data-submit-label]');
  const actionMode = userEditorState.mode;
  const targetUserId = userEditorState.userId;
  const payload = {
    display_name: form.display_name.value.trim(),
    email: form.email.value.trim(),
    role: form.role.value,
    is_active: form.is_active.checked,
    group_ids: [...form.querySelectorAll('input[name="group_ids"]:checked')].map(input => input.value),
  };
  const password = form.password.value.trim();

  if (!payload.display_name || !payload.email) {
    showToast('Display name and email are required.', 'error');
    return;
  }

  if (button) {
    button.disabled = true;
    button.textContent = actionMode === 'edit' ? 'Saving...' : 'Creating...';
  }

  try {
    let response;
    if (actionMode === 'create') {
      if (!password) {
        throw new Error('Password is required for new users.');
      }
      payload.password = password;
      response = await authFetch(`${API}/users`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    } else {
      if (password) payload.password = password;
      response = await authFetch(`${API}/users/${encodeURIComponent(targetUserId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    }

    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    closeUserEditor();
    await loadUsersAdmin();
    showToast(actionMode === 'edit' ? 'User updated.' : 'User created.');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = actionMode === 'edit' ? 'Save changes' : 'Create user';
    }
  }
}

export async function toggleUserActive(userId) {
  const user = adminDirectory.users.find(item => item.id === userId);
  if (!user) return;

  const nextStatus = !user.is_active;
  const confirmText = nextStatus
    ? `Enable ${getUserDisplayName(user)}?`
    : `Disable ${getUserDisplayName(user)}?`;

  const ok = await kpConfirm({
    title: nextStatus ? 'Enable user' : 'Disable user',
    message: confirmText,
    okText: nextStatus ? 'Enable' : 'Disable',
    cancelText: 'Cancel',
    danger: !nextStatus,
  });
  if (!ok) return;

  try {
    const response = await authFetch(`${API}/users/${encodeURIComponent(userId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: nextStatus }),
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    await loadUsersAdmin();
    showToast(nextStatus ? 'User enabled.' : 'User disabled.');
  } catch (error) {
    showToast(error.message, 'error');
  }
}

export function openCreateGroup() {
  groupEditorState = { mode: 'create', groupId: null };
  renderGroupEditor();
}

export function editGroup(groupId) {
  groupEditorState = { mode: 'edit', groupId };
  renderGroupEditor();
}

export function closeGroupEditor() {
  groupEditorState = null;
  const panel = document.getElementById('groupEditorPanel');
  if (!panel) return;
  panel.classList.remove('active');
  panel.innerHTML = '';
}

export function renderGroupEditor() {
  const panel = document.getElementById('groupEditorPanel');
  if (!panel) return;
  if (!groupEditorState) {
    closeGroupEditor();
    return;
  }

  const isEdit = groupEditorState.mode === 'edit';
  const group = isEdit
    ? adminDirectory.groups.find(item => item.id === groupEditorState.groupId)
    : null;

  if (isEdit && !group) {
    closeGroupEditor();
    showToast('Group no longer exists.', 'error');
    return;
  }

  const members = (group?.members || [])
    .map(member => escapeHtml(member.display_name || member.email || member.id))
    .join(', ');

  panel.classList.add('active');
  panel.innerHTML = `
    <form onsubmit="submitGroupEditor(event)">
      <div class="admin-editor-head">
        <div>
          <div class="admin-editor-title">${isEdit ? 'Edit group' : 'Create group'}</div>
          <div class="admin-editor-note">${isEdit ? escapeHtml(group.id) : 'Create a reusable access group'}</div>
        </div>
        <button type="button" class="admin-secondary" onclick="closeGroupEditor()">Close</button>
      </div>

      <div class="admin-form-grid">
        <div class="admin-field">
          <label for="group-name">Group name</label>
          <input id="group-name" name="name" value="${escapeHtml(group?.name || '')}" required />
        </div>
        ${isEdit ? '' : `
        <div class="admin-field">
          <label for="group-id">Custom group id (optional)</label>
          <input id="group-id" name="id" placeholder="group_engineering" />
        </div>`}
      </div>

      ${isEdit ? `<div class="admin-editor-note" style="margin-top:14px">Members: ${members || 'No members yet.'}</div>` : ''}

      <div class="admin-editor-actions">
        <button type="submit" class="add-btn" data-group-submit>${isEdit ? 'Save group' : 'Create group'}</button>
        <button type="button" class="admin-secondary" onclick="closeGroupEditor()">Cancel</button>
      </div>
    </form>
  `;
}

export async function submitGroupEditor(event) {
  event.preventDefault();
  if (!groupEditorState) return;

  const form = event.target;
  const button = form.querySelector('[data-group-submit]');
  const actionMode = groupEditorState.mode;
  const targetGroupId = groupEditorState.groupId;
  const payload = {
    name: form.name.value.trim(),
  };
  const customIdField = form.querySelector('[name="id"]');

  if (customIdField && customIdField.value.trim()) {
    payload.id = customIdField.value.trim();
  }

  if (!payload.name) {
    showToast('Group name is required.', 'error');
    return;
  }

  if (button) {
    button.disabled = true;
    button.textContent = actionMode === 'edit' ? 'Saving...' : 'Creating...';
  }

  try {
    const response = await authFetch(
      actionMode === 'edit'
        ? `${API}/users/groups/${encodeURIComponent(targetGroupId)}`
        : `${API}/users/groups`,
      {
        method: actionMode === 'edit' ? 'PATCH' : 'POST',
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    closeGroupEditor();
    await loadUsersAdmin();
    showToast(actionMode === 'edit' ? 'Group updated.' : 'Group created.');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = actionMode === 'edit' ? 'Save group' : 'Create group';
    }
  }
}