// tasks.js — Redirect to /docs/drafts (Phương án B: không có /api/tasks endpoint)
// tasks.js hiển thị drafts từ /api/docs/drafts thay vì /api/tasks không tồn tại
console.log('[Tasks] Loading module...');
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

export async function loadTasks() {
  const container = document.getElementById('tasksContainer');
  if (container) container.innerHTML = '<div class="tasks-loading">Đang tải...</div>';

  try {
    // /api/tasks không tồn tại → dùng /docs/drafts
    const response = await authFetch(`${API}/docs/drafts?limit=50`);
    if (!response.ok) throw new Error('Failed to load drafts');

    const data = await response.json();
    renderTasksList(data.drafts || []);
  } catch (e) {
    console.error('Error loading tasks:', e);
    if (container) container.innerHTML = '<div class="tasks-empty">Không tải được dữ liệu</div>';
  }
}

function renderTasksList(drafts) {
  const container = document.getElementById('tasksContainer');
  if (!container) return;

  container.innerHTML = '';
  if (!drafts || drafts.length === 0) {
    container.innerHTML = '<div class="tasks-empty">Chưa có bản nháp nào</div>';
    return;
  }

  const list = document.createElement('div');
  list.className = 'tasks-list';

  drafts.forEach(draft => {
    const card = document.createElement('div');
    card.className = 'task-card';
    const docType = String(draft.doc_type || 'srs').toUpperCase();
    const statusClass = draft.status === 'approved' ? 'task-status approved'
                      : draft.status === 'rejected'  ? 'task-status rejected'
                      : 'task-status pending';
    card.innerHTML = `
      <div class="${statusClass}">${escapeHtml(draft.status || 'draft')}</div>
      <div class="task-title">
        <span class="draft-type-badge">${escapeHtml(docType)}</span>
        ${escapeHtml(draft.title || 'Untitled')}
      </div>
      <div class="task-meta">
        <span class="task-time">Tạo lúc: ${formatTaskDate(draft.created_at)}</span>
      </div>
      <div class="task-actions">
        <button class="secondary-btn mini" onclick="window.openDocDraftEditor('${draft.id}')">📄 Mở</button>
        <button class="secondary-btn mini" onclick="window.deleteTaskDraft('${draft.id}')">🗑 Xóa</button>
      </div>
    `;
    list.appendChild(card);
  });

  container.appendChild(list);
}

window.deleteTaskDraft = async function (draftId) {
  if (!confirm('Xóa bản nháp này?')) return;
  try {
    const res = await authFetch(`${API}/docs/drafts/${draftId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Xóa thất bại');
    showToast('Đã xóa bản nháp', 'success');
    loadTasks();
  } catch (e) {
    showToast(e.message, 'error');
  }
};

// Badge count: đếm drafts có status !== 'approved' và 'rejected'
export async function loadTasksCount() {
  try {
    const response = await authFetch(`${API}/docs/drafts?limit=100`);
    if (!response.ok) return;
    const data = await response.json();
    const pending = (data.drafts || []).filter(d => !d.status || d.status === 'draft').length;
    const badge = document.querySelector('[data-badge="tasks"]');
    if (badge) {
      badge.textContent = pending;
      badge.style.display = pending > 0 ? 'inline-block' : 'none';
    }
  } catch (e) {
    console.error('Error loading tasks count:', e);
  }
}

function formatTaskDate(dateStr) {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
  } catch {
    return dateStr;
  }
}
