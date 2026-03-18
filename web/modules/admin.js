// admin.js — Full CRUD: Users, Groups, Overrides — using shared kpOpenModal/kpConfirm
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml, kpOpenModal, kpConfirm, _kpBuildModalField } from '../utils/ui.js';

const ROLES = [
  { value: 'system_admin', label: 'System Admin' },
  { value: 'knowledge_architect', label: 'Knowledge Architect' },
  { value: 'pm_po', label: 'PM / PO' },
  { value: 'ba_sa', label: 'BA / SA' },
  { value: 'dev_qa', label: 'Dev / QA' },
  { value: 'standard', label: 'Standard' },
];

let _adminData = { users: [], groups: [] };

// ── Load ─────────────────────────────────────────────────────────────────────

export async function loadUsersAdmin() {
  console.log('[Admin] loadUsersAdmin');
  try {
    const res = await authFetch(`${API}/users`);
    if (!res.ok) throw new Error('Users API failed');
    _adminData = await res.json();
    renderUsersTable(document.getElementById('usersTableContainer'), _adminData.users || []);
    renderGroupsTable(document.getElementById('groupsTableContainer'), _adminData.groups || []);
  } catch (e) {
    console.error('[Admin] fail:', e);
    showToast('Không tải được dữ liệu admin', 'error');
  }
}

// ── Render Users ─────────────────────────────────────────────────────────────

function renderUsersTable(container, users) {
  if (!container) return;
  if (!users.length) {
    container.innerHTML = '<div class="connectors-empty">Chưa có user nào.</div>';
    return;
  }
  container.innerHTML = `
    <table class="admin-table">
      <thead><tr><th>Tên</th><th>Email</th><th>Role</th><th>Trạng thái</th><th>Groups</th><th>Hành động</th></tr></thead>
      <tbody>
        ${users.map(u => `
          <tr>
            <td>${escapeHtml(u.display_name || u.email)}</td>
            <td>${escapeHtml(u.email)}</td>
            <td><span class="role-badge role-${u.role || 'standard'}">${escapeHtml(u.role || 'standard')}</span></td>
            <td>${u.is_active ? '<span class="badge-ok">Active</span>' : '<span class="badge-err">Inactive</span>'}</td>
            <td>${(u.groups || []).map(g => escapeHtml(g.name)).join(', ') || '—'}</td>
            <td style="white-space:nowrap">
              <button class="secondary-btn mini" onclick="window.adminOpenEditUser('${u.id}')">✏️ Sửa</button>
              <button class="secondary-btn mini" onclick="window.adminToggleActive('${u.id}', ${u.is_active})">${u.is_active ? '🔒 Khóa' : '🔓 Kích hoạt'}</button>
              <button class="secondary-btn mini" onclick="window.adminViewOverrides('${u.id}')">🔐 Overrides</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

// ── Render Groups ─────────────────────────────────────────────────────────────

function renderGroupsTable(container, groups) {
  if (!container) return;
  if (!groups.length) {
    container.innerHTML = '<div class="connectors-empty">Chưa có group nào.</div>';
    return;
  }
  container.innerHTML = `
    <table class="admin-table">
      <thead><tr><th>Tên group</th><th>Thành viên</th><th>Hành động</th></tr></thead>
      <tbody>
        ${groups.map(g => `
          <tr>
            <td><strong>${escapeHtml(g.name)}</strong><br><small style="color:var(--text-muted)">${escapeHtml(g.id)}</small></td>
            <td>${g.member_count || 0} users</td>
            <td>
              <button class="secondary-btn mini" onclick="window.adminOpenEditGroup('${g.id}', '${escapeHtml(g.name)}')">✏️ Sửa</button>
            </td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function groupCheckboxesHtml(userGroupIds = []) {
  const groups = _adminData.groups || [];
  if (!groups.length) return '<p style="color:var(--text-muted)">Chưa có group nào.</p>';
  const frag = document.createElement('div');
  groups.forEach(g => {
    const label = document.createElement('label');
    label.style.cssText = 'display:flex;align-items:center;gap:8px;margin-bottom:6px';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.name = 'group_ids';
    cb.value = g.id;
    if (userGroupIds.includes(g.id)) cb.checked = true;
    label.appendChild(cb);
    label.appendChild(document.createTextNode(g.name));
    frag.appendChild(label);
  });
  return frag;
}

function roleSelectEl(selected = 'standard') {
  const sel = document.createElement('select');
  sel.id = 'aRole';
  sel.className = 'time-input kp-modal-input';
  ROLES.forEach(r => {
    const o = document.createElement('option');
    o.value = r.value;
    o.textContent = r.label;
    if (r.value === selected) o.selected = true;
    sel.appendChild(o);
  });
  return sel;
}

function getCheckedGroups() {
  return [...document.querySelectorAll('input[name="group_ids"]:checked')].map(cb => cb.value);
}

// ── Create User ───────────────────────────────────────────────────────────────

export function openCreateUser() { window.adminOpenCreateUser(); }

window.adminOpenCreateUser = function () {
  const body = document.createElement('div');
  body.className = 'kp-modal-form';

  const { wrap: w1, input: emailIn } = _kpBuildModalField({ id: 'aEmail', label: 'Email', type: 'email', placeholder: 'user@example.com', required: true });
  const { wrap: w2, input: nameIn } = _kpBuildModalField({ id: 'aName', label: 'Tên hiển thị', placeholder: 'Nguyễn Văn A', required: true });
  const { wrap: w3, input: pwdIn } = _kpBuildModalField({ id: 'aPwd', label: 'Mật khẩu', type: 'password', placeholder: 'Tối thiểu 8 ký tự', required: true });
  
  const w4 = document.createElement('div');
  w4.className = 'kp-modal-field';
  const lab4 = document.createElement('label');
  lab4.className = 'kp-modal-label';
  lab4.textContent = 'Role';
  w4.appendChild(lab4);
  w4.appendChild(roleSelectEl('standard'));

  const w5 = document.createElement('div');
  w5.className = 'kp-modal-field';
  const lab5 = document.createElement('label');
  lab5.className = 'kp-modal-label';
  lab5.textContent = 'Groups';
  w5.appendChild(lab5);
  w5.appendChild(groupCheckboxesHtml());

  body.append(w1, w2, w3, w4, w5);

  kpOpenModal({
    title: 'Thêm user mới',
    subtitle: 'Tạo tài khoản mới cho hệ thống',
    content: body,
    okText: 'Tạo user',
    onOk: async () => {
      const email = emailIn.value.trim();
      const displayName = nameIn.value.trim();
      const password = pwdIn.value;
      const role = document.getElementById('aRole')?.value;
      const groupIds = getCheckedGroups();
      if (!email || !password || !displayName) return { error: 'Vui lòng điền đầy đủ thông tin' };
      try {
        const res = await authFetch(`${API}/users`, {
          method: 'POST',
          body: JSON.stringify({ email, display_name: displayName, password, role, group_ids: groupIds }),
        });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi tạo user'); }
        showToast('Đã tạo user thành công', 'success');
        loadUsersAdmin();
        return true;
      } catch (e) { return { error: e.message }; }
    },
  });
};

// ── Edit User ─────────────────────────────────────────────────────────────────

window.adminOpenEditUser = function (userId) {
  const u = (_adminData.users || []).find(x => x.id === userId);
  if (!u) return;

  const body = document.createElement('div');
  body.className = 'kp-modal-form';

  const { wrap: w1, input: nameIn } = _kpBuildModalField({ id: 'aName', label: 'Tên hiển thị', value: u.display_name || '' });
  const { wrap: w2, input: emailIn } = _kpBuildModalField({ id: 'aEmail', label: 'Email', type: 'email', value: u.email });
  const { wrap: w3, input: pwdIn } = _kpBuildModalField({ id: 'aPwd', label: 'Mật khẩu mới (để trống = không đổi)', type: 'password', placeholder: '••••••••' });
  
  const w4 = document.createElement('div');
  w4.className = 'kp-modal-field';
  const lab4 = document.createElement('label');
  lab4.className = 'kp-modal-label';
  lab4.textContent = 'Role';
  w4.appendChild(lab4);
  w4.appendChild(roleSelectEl(u.role || 'standard'));

  const w5 = document.createElement('div');
  w5.className = 'kp-modal-field';
  const lab5 = document.createElement('label');
  lab5.className = 'kp-modal-label';
  lab5.textContent = 'Groups';
  w5.appendChild(lab5);
  w5.appendChild(groupCheckboxesHtml(u.group_ids || []));

  body.append(w1, w2, w3, w4, w5);

  kpOpenModal({
    title: `Sửa user: ${u.email}`,
    subtitle: 'Cập nhật thông tin tài khoản',
    content: body,
    okText: 'Lưu thay đổi',
    onOk: async () => {
      const payload = {};
      const name = nameIn.value.trim();
      const email = emailIn.value.trim();
      const pwd = pwdIn.value;
      const role = document.getElementById('aRole')?.value;
      if (name) payload.display_name = name;
      if (email && email !== u.email) payload.email = email;
      if (pwd) payload.password = pwd;
      if (role) payload.role = role;
      payload.group_ids = getCheckedGroups();
      try {
        const res = await authFetch(`${API}/users/${userId}`, { method: 'PATCH', body: JSON.stringify(payload) });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi cập nhật'); }
        showToast('Đã cập nhật user', 'success');
        loadUsersAdmin();
        return true;
      } catch (e) { return { error: e.message }; }
    },
  });
};

// ── Toggle Active ─────────────────────────────────────────────────────────────

window.adminToggleActive = async function (userId, currentlyActive) {
  const action = currentlyActive ? 'khóa' : 'kích hoạt';
  const confirmed = await kpConfirm({
    title: `${currentlyActive ? '🔒' : '🔓'} Xác nhận ${action} user`,
    message: `Bạn có chắc muốn ${action} user này không?`,
    okText: action.charAt(0).toUpperCase() + action.slice(1),
    cancelText: 'Huỷ',
    danger: currentlyActive,
  });
  if (!confirmed) return;
  try {
    const res = await authFetch(`${API}/users/${userId}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: !currentlyActive }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi'); }
    showToast(`Đã ${action} user`, 'success');
    loadUsersAdmin();
  } catch (e) { showToast(e.message, 'error'); }
};

// ── Create Group ──────────────────────────────────────────────────────────────

export function openCreateGroup() { window.adminOpenCreateGroup(); }

window.adminOpenCreateGroup = function () {
  const body = document.createElement('div');
  body.className = 'kp-modal-form';
  const { wrap: w1, input: nameIn } = _kpBuildModalField({ id: 'gName', label: 'Tên group', placeholder: 'Tên nhóm', required: true });
  const { wrap: w2, input: idIn } = _kpBuildModalField({ id: 'gId', label: 'ID (tùy chọn — để tự động sinh)', placeholder: 'vd: group_dev' });
  body.append(w1, w2);

  kpOpenModal({
    title: 'Thêm group mới',
    subtitle: 'Tạo nhóm quyền mới',
    content: body,
    okText: 'Tạo group',
    onOk: async () => {
      const name = nameIn.value.trim();
      const id = idIn.value.trim() || undefined;
      if (!name) return { error: 'Vui lòng nhập tên group' };
      try {
        const res = await authFetch(`${API}/users/groups`, {
          method: 'POST',
          body: JSON.stringify({ name, ...(id ? { id } : {}) }),
        });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi tạo group'); }
        showToast('Đã tạo group thành công', 'success');
        loadUsersAdmin();
        return true;
      } catch (e) { return { error: e.message }; }
    },
  });
};

// ── Edit Group ────────────────────────────────────────────────────────────────

window.adminOpenEditGroup = function (groupId, groupName) {
  const body = document.createElement('div');
  body.className = 'kp-modal-form';
  const { wrap: w1, input: nameIn } = _kpBuildModalField({ id: 'gName', label: 'Tên mới', value: groupName });
  body.append(w1);

  kpOpenModal({
    title: `Sửa group: ${groupName}`,
    content: body,
    okText: 'Lưu thay đổi',
    onOk: async () => {
      const name = nameIn.value.trim();
      if (!name) return { error: 'Tên không được để trống' };
      try {
        const res = await authFetch(`${API}/users/groups/${groupId}`, {
          method: 'PATCH',
          body: JSON.stringify({ name }),
        });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi cập nhật'); }
        showToast('Đã cập nhật group', 'success');
        loadUsersAdmin();
        return true;
      } catch (e) { return { error: e.message }; }
    },
  });
};

// ── User Overrides ────────────────────────────────────────────────────────────

window.adminViewOverrides = async function (userId) {
  const u = (_adminData.users || []).find(x => x.id === userId);

  // Open a modal with loading state, then populate it
  const body = document.createElement('div');
  body.innerHTML = '<div class="kp-modal-confirm-text">Đang tải...</div>';

  kpOpenModal({
    title: `🔐 Overrides: ${u?.email || userId}`,
    content: body,
    okText: 'Đóng',
    cancelText: '',
    onOk: () => true,
  });

  try {
    const res = await authFetch(`${API}/users/${userId}/overrides`);
    if (!res.ok) throw new Error('Không tải được overrides');
    const data = await res.json();
    const groupOverrides = data.group_overrides || [];
    const docOverrides   = data.document_overrides || [];

    body.innerHTML = `
      <div style="margin-bottom:20px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
          <strong style="color:var(--text)">Group Denies (${groupOverrides.length})</strong>
          <button class="secondary-btn mini" onclick="window.adminDenyGroup('${userId}')">+ Thêm deny</button>
        </div>
        ${groupOverrides.length === 0 ? '<p style="color:var(--text-muted);font-size:13px">Không có group override nào</p>' : `
          <div style="display:flex;flex-direction:column;gap:6px">
            ${groupOverrides.map(o => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:rgba(239,68,68,0.08);border-radius:6px;border:1px solid rgba(239,68,68,0.2)">
                <span style="font-size:13px;color:var(--text)">🚫 ${escapeHtml(o.group_name || o.group_id)}</span>
                <button class="secondary-btn mini" onclick="window.adminRemoveGroupOverride('${userId}', '${o.group_id}')">✕ Gỡ</button>
              </div>
            `).join('')}
          </div>
        `}
      </div>
      <div>
        <strong style="color:var(--text)">Document Denies (${docOverrides.length})</strong>
        ${docOverrides.length === 0 ? '<p style="color:var(--text-muted);font-size:13px;margin-top:6px">Không có document override nào</p>' : `
          <div style="display:flex;flex-direction:column;gap:6px;margin-top:10px">
            ${docOverrides.map(o => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:rgba(239,68,68,0.08);border-radius:6px;border:1px solid rgba(239,68,68,0.2)">
                <div>
                  <span style="font-size:13px;color:var(--text)">🚫 ${escapeHtml(o.document_title || o.document_id)}</span>
                  ${o.reason ? `<br><small style="color:var(--text-muted)">${escapeHtml(o.reason)}</small>` : ''}
                </div>
                <button class="secondary-btn mini" onclick="window.adminRemoveDocOverride('${userId}', '${o.document_id}')">✕ Gỡ</button>
              </div>
            `).join('')}
          </div>
        `}
      </div>
    `;
  } catch (e) {
    showToast(e.message, 'error');
  }
};

window.adminDenyGroup = function (userId) {
  const groups = _adminData.groups || [];
  const body = document.createElement('div');
  body.className = 'kp-modal-form';
  const { wrap: w1, input: selIn } = _kpBuildModalField({
    id: 'denyGroupId', label: 'Chọn group', type: 'select',
    options: groups.map(g => ({ value: g.id, label: g.name })),
  });
  const { wrap: w2, input: reasonIn } = _kpBuildModalField({ id: 'denyReason', label: 'Lý do (tùy chọn)', placeholder: 'Vì sao deny?' });
  body.append(w1, w2);

  kpOpenModal({
    title: '🚫 Deny group cho user',
    content: body,
    okText: 'Deny group',
    okClass: 'danger-btn',
    onOk: async () => {
      const group_id = selIn.value;
      const reason = reasonIn.value.trim() || undefined;
      if (!group_id) return { error: 'Chọn group' };
      try {
        const res = await authFetch(`${API}/users/${userId}/overrides/groups`, {
          method: 'POST',
          body: JSON.stringify({ group_id, reason }),
        });
        if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi'); }
        showToast('Đã deny group cho user', 'success');
        window.adminViewOverrides(userId);
        return true;
      } catch (e) { return { error: e.message }; }
    },
  });
};

window.adminRemoveGroupOverride = async function (userId, groupId) {
  const confirmed = await kpConfirm({
    title: '🚫 Gỡ group override',
    message: 'Gỡ bỏ group deny này?',
    okText: 'Gỡ bỏ',
    cancelText: 'Huỷ',
    danger: true,
  });
  if (!confirmed) return;
  try {
    const res = await authFetch(`${API}/users/${userId}/overrides/groups/${groupId}`, { method: 'DELETE' });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi'); }
    showToast('Đã gỡ override', 'success');
    window.adminViewOverrides(userId);
  } catch (e) { showToast(e.message, 'error'); }
};

window.adminRemoveDocOverride = async function (userId, documentId) {
  const confirmed = await kpConfirm({
    title: '🚫 Gỡ document override',
    message: 'Gỡ bỏ document deny này?',
    okText: 'Gỡ bỏ',
    cancelText: 'Huỷ',
    danger: true,
  });
  if (!confirmed) return;
  try {
    const res = await authFetch(`${API}/users/${userId}/overrides/documents/${documentId}`, { method: 'DELETE' });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi'); }
    showToast('Đã gỡ override', 'success');
    window.adminViewOverrides(userId);
  } catch (e) { showToast(e.message, 'error'); }
};
