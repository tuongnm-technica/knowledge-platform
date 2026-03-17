// Admin Module - Quản trị
import { authFetch, API } from '../api/client.js';

export function normalizeUserRole(role, isAdmin) {
  if (isAdmin) return 'admin';
  return role || 'standard';
}

export function getUserRoleLabel(roleCode) {
  const labels = {
    admin: '👤 Admin',
    manager: '👥 Manager',
    standard: '👤 User',
    'system_admin': '🔐 System Admin',
    'knowledge_architect': '🏗️ Knowledge Architect',
    'pm_po': '📋 PM/PO',
    'ba_sa': '📊 BA/SA',
    'dev_qa': '🧪 Dev/QA'
  };
  return labels[roleCode] || roleCode;
}

export async function loadUsersAdmin() {
  try {
    const response = await authFetch(`${API}/users`);
    if (!response.ok) throw new Error('Failed to load users');
    
    const data = await response.json();
    renderUsersTable(data.users || []);
  } catch (e) {
    console.error('Error loading users:', e);
  }
}

function renderUsersTable(users) {
  const container = document.getElementById('usersTableContainer');
  if (!container) return;
  
  container.innerHTML = '';
  if (!users || users.length === 0) {
    container.innerHTML = '<div>No users found</div>';
    return;
  }

  const table = document.createElement('table');
  table.className = 'users-table';
  table.innerHTML = `
    <thead>
      <tr>
        <th>Email</th>
        <th>Display Name</th>
        <th>Role</th>
        <th>Active</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      ${users.map(u => `
        <tr>
          <td>${escapeHtml(u.email)}</td>
          <td>${escapeHtml(u.display_name)}</td>
          <td><span class="user-role-badge ${u.is_admin ? 'admin' : 'standard'}">${getUserRoleLabel(u.role)}</span></td>
          <td>${u.is_active ? '✓' : '✗'}</td>
          <td><button onclick="editUser('${u.user_id}')">Edit</button></td>
        </tr>
      `).join('')}
    </tbody>
  `;
  container.appendChild(table);
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}
