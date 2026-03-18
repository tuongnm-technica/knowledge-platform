// admin.js — Full CRUD: Users, Groups, Overrides
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

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
    <div style="margin-bottom:12px">
      <button class="primary-btn" onclick="window.adminOpenCreateUser()">+ Thêm user</button>
    </div>
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
    container.innerHTML = `
      <div style="margin-bottom:12px">
        <button class="primary-btn" onclick="window.adminOpenCreateGroup()">+ Thêm group</button>
      </div>
      <div class="connectors-empty">Chưa có group nào.</div>
    `;
    return;
  }
  container.innerHTML = `
    <div style="margin-bottom:12px">
      <button class="primary-btn" onclick="window.adminOpenCreateGroup()">+ Thêm group</button>
    </div>
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

// ── Modal helpers ─────────────────────────────────────────────────────────────

function showModal(title, bodyHtml, onConfirm) {
  let overlay = document.getElementById('adminModalOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'adminModalOverlay';
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:9000;display:flex;align-items:center;justify-content:center;';
    document.body.appendChild(overlay);
  }
  overlay.innerHTML = `
    <div style="background:var(--surface,#1e2130);border-radius:12px;padding:28px 32px;min-width:420px;max-width:560px;width:90%;box-shadow:0 8px 40px rgba(0,0,0,0.4);">
      <h3 style="margin:0 0 20px;color:var(--text-primary,#fff)">${title}</h3>
      <div id="adminModalBody">${bodyHtml}</div>
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:20px">
        <button class="secondary-btn" id="adminModalCancel">Huỷ</button>
        <button class="primary-btn" id="adminModalConfirm">Xác nhận</button>
      </div>
    </div>
  `;
  overlay.style.display = 'flex';
  document.getElementById('adminModalCancel').onclick = closeModal;
  overlay.onclick = (e) => { if (e.target === overlay) closeModal(); };
  document.getElementById('adminModalConfirm').onclick = onConfirm;
}

function closeModal() {
  const overlay = document.getElementById('adminModalOverlay');
  if (overlay) overlay.style.display = 'none';
}

function groupCheckboxes(userGroupIds = []) {
  const groups = _adminData.groups || [];
  if (!groups.length) return '<p style="color:var(--text-muted)">Chưa có group nào.</p>';
  return groups.map(g => `
    <label style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
      <input type="checkbox" name="group_ids" value="${escapeHtml(g.id)}" ${userGroupIds.includes(g.id) ? 'checked' : ''}>
      ${escapeHtml(g.name)}
    </label>
  `).join('');
}

function roleOptions(selected = 'standard') {
  return ROLES.map(r => `<option value="${r.value}" ${r.value === selected ? 'selected' : ''}>${r.label}</option>`).join('');
}

function getCheckedGroups() {
  return [...document.querySelectorAll('input[name="group_ids"]:checked')].map(cb => cb.value);
}

// ── Create User ───────────────────────────────────────────────────────────────

export function openCreateUser() { window.adminOpenCreateUser(); }

window.adminOpenCreateUser = function () {
  showModal('Thêm user mới', `
    <div style="display:grid;gap:12px">
      <label>Email<br><input id="aEmail" type="email" class="admin-input" placeholder="user@example.com" style="width:100%"></label>
      <label>Tên hiển thị<br><input id="aName" type="text" class="admin-input" placeholder="Nguyễn Văn A" style="width:100%"></label>
      <label>Mật khẩu<br><input id="aPwd" type="password" class="admin-input" placeholder="Tối thiểu 8 ký tự" style="width:100%"></label>
      <label>Role<br><select id="aRole" class="admin-input" style="width:100%">${roleOptions('standard')}</select></label>
      <div><p style="margin:0 0 6px;color:var(--text-primary)">Groups</p>${groupCheckboxes()}</div>
    </div>
  `, async () => {
    const email = document.getElementById('aEmail')?.value.trim();
    const displayName = document.getElementById('aName')?.value.trim();
    const password = document.getElementById('aPwd')?.value;
    const role = document.getElementById('aRole')?.value;
    const groupIds = getCheckedGroups();
    if (!email || !password || !displayName) return showToast('Vui lòng điền đầy đủ thông tin', 'error');
    const btn = document.getElementById('adminModalConfirm');
    btn.disabled = true; btn.textContent = 'Đang tạo...';
    try {
      const res = await authFetch(`${API}/users`, {
        method: 'POST',
        body: JSON.stringify({ email, display_name: displayName, password, role, group_ids: groupIds }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi tạo user'); }
      showToast('Đã tạo user thành công', 'success');
      closeModal();
      loadUsersAdmin();
    } catch (e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = 'Xác nhận'; }
  });
};

// ── Edit User ─────────────────────────────────────────────────────────────────

window.adminOpenEditUser = function (userId) {
  const u = (_adminData.users || []).find(x => x.id === userId);
  if (!u) return;
  showModal(`Sửa user: ${escapeHtml(u.email)}`, `
    <div style="display:grid;gap:12px">
      <label>Tên hiển thị<br><input id="aName" type="text" class="admin-input" value="${escapeHtml(u.display_name || '')}" style="width:100%"></label>
      <label>Email<br><input id="aEmail" type="email" class="admin-input" value="${escapeHtml(u.email)}" style="width:100%"></label>
      <label>Mật khẩu mới (để trống = không đổi)<br><input id="aPwd" type="password" class="admin-input" placeholder="••••••••" style="width:100%"></label>
      <label>Role<br><select id="aRole" class="admin-input" style="width:100%">${roleOptions(u.role || 'standard')}</select></label>
      <div><p style="margin:0 0 6px;color:var(--text-primary)">Groups</p>${groupCheckboxes((u.group_ids || []))}</div>
    </div>
  `, async () => {
    const payload = {};
    const name = document.getElementById('aName')?.value.trim();
    const email = document.getElementById('aEmail')?.value.trim();
    const pwd = document.getElementById('aPwd')?.value;
    const role = document.getElementById('aRole')?.value;
    if (name) payload.display_name = name;
    if (email && email !== u.email) payload.email = email;
    if (pwd) payload.password = pwd;
    if (role) payload.role = role;
    payload.group_ids = getCheckedGroups();
    const btn = document.getElementById('adminModalConfirm');
    btn.disabled = true; btn.textContent = 'Đang lưu...';
    try {
      const res = await authFetch(`${API}/users/${userId}`, { method: 'PATCH', body: JSON.stringify(payload) });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi cập nhật'); }
      showToast('Đã cập nhật user', 'success');
      closeModal();
      loadUsersAdmin();
    } catch (e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = 'Xác nhận'; }
  });
};

// ── Toggle Active ─────────────────────────────────────────────────────────────

window.adminToggleActive = async function (userId, currentlyActive) {
  const action = currentlyActive ? 'khóa' : 'kích hoạt';
  if (!confirm(`Bạn có chắc muốn ${action} user này không?`)) return;
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
  showModal('Thêm group mới', `
    <div style="display:grid;gap:12px">
      <label>Tên group<br><input id="gName" type="text" class="admin-input" placeholder="Tên nhóm" style="width:100%"></label>
      <label>ID (tùy chọn — để tự động sinh)<br><input id="gId" type="text" class="admin-input" placeholder="vd: group_dev" style="width:100%"></label>
    </div>
  `, async () => {
    const name = document.getElementById('gName')?.value.trim();
    const id = document.getElementById('gId')?.value.trim() || undefined;
    if (!name) return showToast('Vui lòng nhập tên group', 'error');
    const btn = document.getElementById('adminModalConfirm');
    btn.disabled = true; btn.textContent = 'Đang tạo...';
    try {
      const res = await authFetch(`${API}/users/groups`, {
        method: 'POST',
        body: JSON.stringify({ name, ...(id ? { id } : {}) }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi tạo group'); }
      showToast('Đã tạo group thành công', 'success');
      closeModal();
      loadUsersAdmin();
    } catch (e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = 'Xác nhận'; }
  });
};

// ── Edit Group ────────────────────────────────────────────────────────────────

window.adminOpenEditGroup = function (groupId, groupName) {
  showModal(`Sửa group: ${escapeHtml(groupName)}`, `
    <div style="display:grid;gap:12px">
      <label>Tên mới<br><input id="gName" type="text" class="admin-input" value="${escapeHtml(groupName)}" style="width:100%"></label>
    </div>
  `, async () => {
    const name = document.getElementById('gName')?.value.trim();
    if (!name) return showToast('Tên không được để trống', 'error');
    const btn = document.getElementById('adminModalConfirm');
    btn.disabled = true; btn.textContent = 'Đang lưu...';
    try {
      const res = await authFetch(`${API}/users/groups/${groupId}`, {
        method: 'PATCH',
        body: JSON.stringify({ name }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi cập nhật'); }
      showToast('Đã cập nhật group', 'success');
      closeModal();
      loadUsersAdmin();
    } catch (e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = 'Xác nhận'; }
  });
};

// ── User Overrides ────────────────────────────────────────────────────────────

window.adminViewOverrides = async function (userId) {
  const u = (_adminData.users || []).find(x => x.id === userId);
  showModal(`🔐 Overrides: ${escapeHtml(u?.email || userId)}`, '<div class="admin-loading">Đang tải...</div>', () => closeModal());
  document.getElementById('adminModalConfirm').style.display = 'none';

  try {
    const res = await authFetch(`${API}/users/${userId}/overrides`);
    if (!res.ok) throw new Error('Không tải được overrides');
    const data = await res.json();
    const groupOverrides = data.group_overrides || [];
    const docOverrides   = data.document_overrides || [];

    const body = document.getElementById('adminModalBody');
    if (!body) return;

    body.innerHTML = `
      <div style="margin-bottom:20px">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
          <strong style="color:var(--text-primary)">Group Denies (${groupOverrides.length})</strong>
          <button class="secondary-btn mini" onclick="window.adminDenyGroup('${userId}')">+ Thêm deny</button>
        </div>
        ${groupOverrides.length === 0 ? '<p style="color:var(--text-muted);font-size:13px">Không có group override nào</p>' : `
          <div style="display:flex;flex-direction:column;gap:6px">
            ${groupOverrides.map(o => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:rgba(239,68,68,0.08);border-radius:6px;border:1px solid rgba(239,68,68,0.2)">
                <span style="font-size:13px;color:var(--text-primary)">🚫 ${escapeHtml(o.group_name || o.group_id)}</span>
                <button class="secondary-btn mini" onclick="window.adminRemoveGroupOverride('${userId}', '${o.group_id}')">✕ Gỡ</button>
              </div>
            `).join('')}
          </div>
        `}
      </div>
      <div>
        <strong style="color:var(--text-primary)">Document Denies (${docOverrides.length})</strong>
        ${docOverrides.length === 0 ? '<p style="color:var(--text-muted);font-size:13px;margin-top:6px">Không có document override nào</p>' : `
          <div style="display:flex;flex-direction:column;gap:6px;margin-top:10px">
            ${docOverrides.map(o => `
              <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;background:rgba(239,68,68,0.08);border-radius:6px;border:1px solid rgba(239,68,68,0.2)">
                <div>
                  <span style="font-size:13px;color:var(--text-primary)">🚫 ${escapeHtml(o.document_title || o.document_id)}</span>
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
    closeModal();
  }
};

window.adminDenyGroup = function (userId) {
  closeModal();
  const groups = _adminData.groups || [];
  showModal('🚫 Deny group cho user', `
    <div style="display:grid;gap:12px">
      <label>Chọn group<br>
        <select id="denyGroupId" class="admin-input" style="width:100%">
          ${groups.map(g => `<option value="${escapeHtml(g.id)}">${escapeHtml(g.name)}</option>`).join('')}
        </select>
      </label>
      <label>Lý do (tùy chọn)<br><input id="denyReason" type="text" class="admin-input" placeholder="Vì sao deny?" style="width:100%"></label>
    </div>
  `, async () => {
    const group_id = document.getElementById('denyGroupId')?.value;
    const reason   = document.getElementById('denyReason')?.value.trim() || undefined;
    if (!group_id) return showToast('Chọn group', 'error');
    const btn = document.getElementById('adminModalConfirm');
    btn.disabled = true; btn.textContent = 'Đang lưu...';
    try {
      const res = await authFetch(`${API}/users/${userId}/overrides/groups`, {
        method: 'POST',
        body: JSON.stringify({ group_id, reason }),
      });
      if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi'); }
      showToast('Đã deny group cho user', 'success');
      closeModal();
      window.adminViewOverrides(userId);
    } catch (e) { showToast(e.message, 'error'); btn.disabled = false; btn.textContent = 'Xác nhận'; }
  });
};

window.adminRemoveGroupOverride = async function (userId, groupId) {
  if (!confirm('Gỡ bỏ group deny này?')) return;
  try {
    const res = await authFetch(`${API}/users/${userId}/overrides/groups/${groupId}`, { method: 'DELETE' });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi'); }
    showToast('Đã gỡ override', 'success');
    window.adminViewOverrides(userId);
  } catch (e) { showToast(e.message, 'error'); }
};

window.adminRemoveDocOverride = async function (userId, documentId) {
  if (!confirm('Gỡ bỏ document deny này?')) return;
  try {
    const res = await authFetch(`${API}/users/${userId}/overrides/documents/${documentId}`, { method: 'DELETE' });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lỗi'); }
    showToast('Đã gỡ override', 'success');
    window.adminViewOverrides(userId);
  } catch (e) { showToast(e.message, 'error'); }
};
