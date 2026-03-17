// Chat Module - Chức năng chat
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

let _callbacks = {};

export function setChatCallbacks(callbacks) {
  _callbacks = callbacks || {};
}

export async function doSearch() {
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) return;
  
  const query = searchInput.value.trim();
  if (!query) {
    showToast('Vui lòng nhập câu hỏi', 'info');
    return;
  }

  showToast('Đang tìm kiếm...', 'info');
  const searchBtn = document.getElementById('searchBtn');
  if (searchBtn) searchBtn.disabled = true;

  try {
    const response = await authFetch(`${API}/search`, {
      method: 'POST',
      body: JSON.stringify({ query, limit: 10 })
    });
    
    if (!response.ok) throw new Error('Tìm kiếm thất bại');
    const data = await response.json();
    renderSearchResults(data);
    showToast(`Tìm thấy ${(data || []).length} kết quả`, 'success');
  } catch (e) {
    showToast(`Lỗi: ${e.message}`, 'error');
  } finally {
    if (searchBtn) searchBtn.disabled = false;
  }
}

function renderSearchResults(results) {
  const container = document.getElementById('searchResults');
  if (!container) return;
  
  container.innerHTML = '';
  if (!results || results.length === 0) {
    container.innerHTML = '<div class="search-empty">Không tìm thấy kết quả</div>';
    return;
  }

  results.forEach(result => {
    const item = document.createElement('div');
    item.className = 'search-result';
    item.innerHTML = `
      <div class="search-result-title">${escapeHtml(result.title || 'Untitled')}</div>
      <div class="search-result-snippet">${escapeHtml(result.content || '').substring(0, 200)}</div>
      <div class="search-result-meta">
        <span>${result.source || 'Unknown'}</span>
        <span>${(result.score * 100).toFixed(0)}%</span>
      </div>
    `;
    container.appendChild(item);
  });
}

export function renderHistory() {
  // TODO: Load and display chat history from API
  console.log('renderHistory called');
}
