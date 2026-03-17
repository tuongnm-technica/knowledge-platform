// Tasks Module - Công việc AI
import { authFetch, API } from '../api/client.js';

export async function loadTasks() {
  try {
    const response = await authFetch(`${API}/tasks`);
    if (!response.ok) throw new Error('Failed to load tasks');
    
    const data = await response.json();
    renderTasksList(data.drafts || []);
  } catch (e) {
    console.error('Error loading tasks:', e);
  }
}

function renderTasksList(tasks) {
  const container = document.getElementById('tasksContainer');
  if (!container) return;
  
  container.innerHTML = '';
  if (!tasks || tasks.length === 0) {
    container.innerHTML = '<div class="tasks-empty">Không có công việc nào</div>';
    return;
  }

  tasks.forEach(task => {
    const card = document.createElement('div');
    card.className = 'task-card';
    const statusClass = `task-status ${task.status || 'pending'}`;
    card.innerHTML = `
      <div class="${statusClass}">${task.status || 'pending'}</div>
      <div class="task-title">${escapeHtml(task.title || 'Untitled')}</div>
      <div class="task-meta">
        <p>${escapeHtml(task.description || '')}</p>
        <span class="task-time">Created: ${formatTaskDate(task.created_at)}</span>
      </div>
      <div class="task-actions">
        <button onclick="confirmTask('${task.id}')">Confirm</button>
        <button onclick="rejectTask('${task.id}')">Reject</button>
      </div>
    `;
    container.appendChild(card);
  });
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

function formatTaskDate(dateStr) {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('vi-VN');
  } catch {
    return dateStr;
  }
}

export async function loadTasksCount() {
  try {
    const response = await authFetch(`${API}/tasks/count`);
    if (!response.ok) throw new Error('Failed to load tasks count');
    
    const data = await response.json();
    const badge = document.querySelector('[data-badge="tasks"]');
    if (badge && data.count > 0) {
      badge.textContent = data.count;
      badge.style.display = 'inline-block';
    }
  } catch (e) {
    console.error('Error loading tasks count:', e);
  }
}
