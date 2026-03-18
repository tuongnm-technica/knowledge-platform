// Drafts Module - Bản nháp tài liệu
console.log('[Drafts] Loading module...');
import { authFetch, API } from '../api/client.js';

export async function loadDraftsPage(refresh = false) {
  try {
    const response = await authFetch(`${API}/docs/drafts`);
    if (!response.ok) throw new Error('Failed to load drafts');
    
    const data = await response.json();
    renderDraftsList(data.drafts || []);
  } catch (e) {
    console.error('Error loading drafts page:', e);
  }
}

function renderDraftsList(drafts) {
  const container = document.getElementById('draftsContainer');
  if (!container) return;
  
  container.innerHTML = '';
  if (!drafts || drafts.length === 0) {
    container.innerHTML = '<div class="drafts-empty">Chưa có bản nháp nào</div>';
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'drafts-list';
  
  drafts.forEach(draft => {
    const card = document.createElement('div');
    card.className = 'draft-card';
    const docType = String(draft.doc_type || 'srs').toLowerCase();
    card.innerHTML = `
      <div class="draft-header">
        <div class="draft-type">${escapeHtml(docType.toUpperCase())}</div>
        <div class="draft-title">${escapeHtml(draft.title || 'Untitled')}</div>
      </div>
      <div class="draft-meta">
        <p>${escapeHtml(draft.content || '').substring(0, 100)}...</p>
        <span>Created: ${formatDate(draft.created_at)}</span>
      </div>
      <div class="draft-actions">
        <button onclick="openDocDraftEditor('${draft.id}')">Open</button>
        <button onclick="deleteDraft('${draft.id}')">Delete</button>
      </div>
    `;
    grid.appendChild(card);
  });
  
  container.appendChild(grid);
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

function formatDate(dateStr) {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleDateString('vi-VN');
  } catch {
    return dateStr;
  }
}
