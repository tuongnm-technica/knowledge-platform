// admin.js
import { authFetch, API } from '../api/client.js';
import { escapeHtml } from '../utils/ui.js';

export async function loadUsersAdmin() {
  console.log('[Admin] loadUsersAdmin');
  const uCont = document.getElementById('usersTableContainer');
  const gCont = document.getElementById('groupsTableContainer');
  
  try {
    const res = await authFetch(`${API}/users`);
    if (!res.ok) throw new Error('Users API failed');
    const data = await res.json();
    
    if (uCont) renderUsersTable(uCont, data.users || []);
    if (gCont) renderGroupsTable(gCont, data.groups || []);
  } catch (e) {
    console.error('[Admin] fail:', e);
  }
}

function renderUsersTable(container, users) {
  if (!users.length) {
    container.innerHTML = '<div class="connectors-empty">No users.</div>';
    return;
  }
  container.innerHTML = `
    <table class="admin-table">
      <thead><tr><th>User</th><th>Email</th><th>Role</th><th>Actions</th></tr></thead>
      <tbody>
        ${users.map(u => `
          <tr>
            <td>${escapeHtml(u.display_name || 'N/A')}</td>
            <td>${escapeHtml(u.email)}</td>
            <td>${u.is_admin ? 'Admin' : 'Standard'}</td>
            <td><button class="secondary-btn mini">Edit</button></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

function renderGroupsTable(container, groups) {
  if (!groups.length) {
    container.innerHTML = '<div class="connectors-empty">No groups.</div>';
    return;
  }
  container.innerHTML = `
    <table class="admin-table">
      <thead><tr><th>Group Name</th><th>Members</th><th>Actions</th></tr></thead>
      <tbody>
        ${groups.map(g => `
          <tr>
            <td><strong>${escapeHtml(g.name)}</strong></td>
            <td>${g.members_count || 0} users</td>
            <td><button class="secondary-btn mini">Manage</button></td>
          </tr>
        `).join('')}
      </tbody>
    </table>
  `;
}

export function openCreateUser() { showToast('Coming soon'); }
export function openCreateGroup() { showToast('Coming soon'); }
