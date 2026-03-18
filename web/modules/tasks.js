console.log('[Tasks] Loading module...');
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

export async function loadTasks() {
  const container = document.getElementById('tasksContainer');
  if (container) container.innerHTML = '<div class="tasks-loading">Đang tải...</div>';

  try {
    const response = await authFetch(`${API}/tasks?limit=50`);
    if (!response.ok) throw new Error('Failed to load tasks');

    const data = await response.json();
    renderTasksList(data.tasks || []);
  } catch (e) {
    console.error('Error loading tasks:', e);
    if (container) container.innerHTML = '<div class="tasks-empty">Không tải được dữ liệu</div>';
  }
}

function renderTasksList(tasks) {
  const container = document.getElementById('tasksContainer');
  if (!container) return;

  container.innerHTML = '';
  if (!tasks || tasks.length === 0) {
    container.innerHTML = '<div class="tasks-empty">Chưa có task nào</div>';
    return;
  }

  const list = document.createElement('div');
  list.className = 'tasks-list';

  tasks.forEach(task => {
    const card = document.createElement('div');
    card.className = 'task-card';
    // Dùng source thay vì doc_type cho Task
    const source = String(task.source || 'system').toUpperCase();
    const statusClass = task.status === 'approved' ? 'task-status approved'
                      : task.status === 'rejected'  ? 'task-status rejected'
                      : 'task-status pending';
    card.innerHTML = `
      <div class="${statusClass}">${escapeHtml(task.status || 'pending')}</div>
      <div class="task-title">
        <span class="draft-type-badge">${escapeHtml(source)}</span>
        ${escapeHtml(task.title || 'Untitled')}
      </div>
      <div class="task-meta">
        <span class="task-time">Tạo lúc: ${formatTaskDate(task.created_at)}</span>
      </div>
      <div class="task-actions">
        <button class="secondary-btn mini" onclick="window.approveTask('${task.id}')">✅ Duyệt</button>
        <button class="secondary-btn mini" onclick="window.deleteTask('${task.id}')">🗑 Xóa</button>
      </div>
    `;
    list.appendChild(card);
  });

  container.appendChild(list);
}

window.deleteTask = async function (taskId) {
  if (!confirm('Xóa task này?')) return;
  try {
    const res = await authFetch(`${API}/tasks/${taskId}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Xóa thất bại');
    showToast('Đã xóa task', 'success');
    loadTasks();
    loadTasksCount();
  } catch (e) {
    showToast(e.message, 'error');
  }
};

window.approveTask = async function(taskId) {
  try {
    const res = await authFetch(`${API}/tasks/${taskId}/status`, { 
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'approved' })
    });
    if (!res.ok) throw new Error('Duyệt thất bại');
    showToast('Đã duyệt thành Task', 'success');
    loadTasks();
    loadTasksCount();
  } catch (e) {
    showToast(e.message, 'error');
  }
};

export async function loadTasksCount() {
  try {
    // Gọi API count chuyên dụng thay vì load 100 record về đếm
    const response = await authFetch(`${API}/tasks/count`);
    if (!response.ok) return;
    const data = await response.json();
    const pending = data.total_pending || 0;
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
