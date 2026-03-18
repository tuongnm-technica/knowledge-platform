// Drafts Module - Bản nháp tài liệu (docs/drafts endpoint)
console.log('[Drafts] Loading module...');
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml, kpPrompt } from '../utils/ui.js';

let _currentDraftId = null;

// ── Load list ─────────────────────────────────────────────────────────────────

export async function loadDraftsPage(refresh = false) {
  const container = document.getElementById('draftsContainer');
  if (container && !refresh) container.innerHTML = '<div class="drafts-loading">Đang tải...</div>';

  try {
    const response = await authFetch(`${API}/docs/drafts?limit=50`);
    if (!response.ok) throw new Error('Failed to load drafts');
    const data = await response.json();
    renderDraftsList(data.drafts || []);
  } catch (e) {
    console.error('Error loading drafts page:', e);
    showToast('Không tải được danh sách drafts', 'error');
  }
}

// ── Render list ───────────────────────────────────────────────────────────────

function renderDraftsList(drafts) {
  const container = document.getElementById('draftsContainer');
  if (!container) return;

  container.innerHTML = '';
  if (!drafts || drafts.length === 0) {
    container.innerHTML = '<div class="drafts-empty">Chưa có bản nháp nào. Tạo draft từ Chat để bắt đầu.</div>';
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'drafts-list';

  drafts.forEach(draft => {
    const card = document.createElement('div');
    card.className = 'draft-card';
    const docType = String(draft.doc_type || 'srs').toUpperCase();
    const statusColor = draft.status === 'approved' ? '#22c55e'
                      : draft.status === 'rejected'  ? '#ef4444'
                      : draft.status === 'published' ? '#3b82f6'
                      : '#94a3b8';
    card.innerHTML = `
      <div class="draft-header">
        <div class="draft-type">${escapeHtml(docType)}</div>
        <div class="draft-title">${escapeHtml(draft.title || 'Untitled')}</div>
        <span style="font-size:11px;padding:2px 8px;border-radius:12px;background:${statusColor}22;color:${statusColor}">
          ${escapeHtml(draft.status || 'draft')}
        </span>
      </div>
      <div class="draft-meta">
        <p>${escapeHtml((draft.content || '').substring(0, 120))}${draft.content?.length > 120 ? '...' : ''}</p>
        <span>Tạo lúc: ${formatDate(draft.created_at)}</span>
      </div>
      <div class="draft-actions">
        <button class="secondary-btn mini" onclick="window.openDocDraftEditor('${draft.id}')">📄 Mở</button>
        <button class="secondary-btn mini" onclick="window.deleteDraft('${draft.id}')">🗑 Xóa</button>
      </div>
    `;
    grid.appendChild(card);
  });

  container.appendChild(grid);
}

// ── Open / Edit draft ─────────────────────────────────────────────────────────

window.openDocDraftEditor = async function (draftId) {
  _currentDraftId = draftId;
  const container = document.getElementById('draftsContainer');
  if (container) container.innerHTML = '<div class="drafts-loading">Đang tải bản nháp...</div>';

  try {
    const res = await authFetch(`${API}/docs/drafts/${draftId}`);
    if (!res.ok) throw new Error('Không tải được draft');
    const data = await res.json();
    renderDraftEditor(data.draft);
  } catch (e) {
    showToast(e.message, 'error');
    loadDraftsPage();
  }
};

function renderDraftEditor(draft) {
  const container = document.getElementById('draftsContainer');
  if (!container) return;

  container.innerHTML = `
    <div class="draft-editor">
      <div class="draft-editor-header" style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <button class="secondary-btn mini" onclick="window.closeDraftEditor()">← Quay lại</button>
        <span class="draft-type" style="font-size:13px">${escapeHtml((draft.doc_type || 'srs').toUpperCase())}</span>
        <input id="draftTitleInput" type="text" class="admin-input" value="${escapeHtml(draft.title || '')}"
               style="flex:1;font-size:15px;font-weight:600" placeholder="Tiêu đề...">
        <button class="secondary-btn ai-rewrite-btn" onclick="window.refineSelectedText()" title="Bôi đen văn bản bên dưới và nhờ AI viết lại">✨ AI Rewrite</button>
        <button class="primary-btn" onclick="window.saveDraft()">💾 Lưu</button>
      </div>

      <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center">
        <label style="color:var(--text-secondary);font-size:12px">Trạng thái:</label>
        <select id="draftStatusSelect" class="admin-input" style="font-size:12px;padding:4px 8px">
          <option value="draft" ${draft.status === 'draft' ? 'selected' : ''}>Draft</option>
          <option value="review" ${draft.status === 'review' ? 'selected' : ''}>Đang review</option>
          <option value="approved" ${draft.status === 'approved' ? 'selected' : ''}>Approved</option>
          <option value="published" ${draft.status === 'published' ? 'selected' : ''}>Published</option>
          <option value="rejected" ${draft.status === 'rejected' ? 'selected' : ''}>Rejected</option>
        </select>
        <span style="color:var(--text-muted);font-size:11px">Cập nhật: ${formatDate(draft.updated_at || draft.created_at)}</span>
      </div>

      <textarea id="draftContentEditor"
        style="width:100%;min-height:480px;background:var(--surface-alt,rgba(255,255,255,0.03));
               border:1px solid rgba(255,255,255,0.1);border-radius:8px;padding:16px;
               color:var(--text-primary,#fff);font-family:'JetBrains Mono','Fira Code',monospace;
               font-size:13px;line-height:1.7;resize:vertical;box-sizing:border-box"
        spellcheck="false">${escapeHtml(draft.content || '')}</textarea>
    </div>
  `;
}

window.saveDraft = async function () {
  if (!_currentDraftId) return;
  const title   = document.getElementById('draftTitleInput')?.value.trim();
  const content = document.getElementById('draftContentEditor')?.value;
  const status  = document.getElementById('draftStatusSelect')?.value;

  try {
    const res = await authFetch(`${API}/docs/drafts/${_currentDraftId}`, {
      method: 'PUT',
      body: JSON.stringify({ title, content, status }),
    });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Lưu thất bại'); }
    showToast('Đã lưu bản nháp', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
};

window.refineSelectedText = async function () {
  if (!_currentDraftId) return;
  const editor = document.getElementById('draftContentEditor');
  if (!editor) return;

  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  const selectedText = editor.value.substring(start, end);

  if (!selectedText || selectedText.trim().length === 0) {
    showToast('Vui lòng bôi đen một đoạn văn bản cần viết lại.', 'warning');
    return;
  }

  const instruction = await kpPrompt({
    title: '✨ AI Rewrite',
    message: 'Bạn muốn AI viết lại đoạn văn bản này như thế nào?',
    placeholder: 'VD: Dịch sang tiếng Anh, viết ngắn gọn hơn, chuyên nghiệp hơn...'
  });

  if (!instruction) return;

  const originalCursor = editor.style.cursor;
  editor.style.cursor = 'wait';
  editor.disabled = true;
  showToast('AI đang phân tích và viết lại...', 'info');

  try {
    const res = await authFetch(`${API}/docs/drafts/${_currentDraftId}/refine`, {
      method: 'POST',
      body: JSON.stringify({ selected_text: selectedText, instruction }),
    });
    
    if (!res.ok) { 
      const e = await res.json(); 
      throw new Error(e.detail || 'Lỗi khi gọi AI Rewrite'); 
    }
    
    const data = await res.json();
    const newText = data.refined_text || '';

    // Thay thế đoạn text cũ bằng text mới từ AI
    editor.value = editor.value.substring(0, start) + newText + editor.value.substring(end);
    
    // Bôi đen lại chính đoạn text mới để user dễ nhìn
    editor.selectionStart = start;
    editor.selectionEnd = start + newText.length;
    editor.focus();

    showToast('Đã viết lại thành công! Bạn có thể tiếp tục chỉnh sửa hoặc nhấn Lưu.', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  } finally {
    editor.style.cursor = originalCursor;
    editor.disabled = false;
  }
};

window.closeDraftEditor = function () {
  _currentDraftId = null;
  loadDraftsPage();
};

// ── Delete draft ──────────────────────────────────────────────────────────────

window.deleteDraft = async function (draftId) {
  if (!confirm('Xóa bản nháp này? Hành động này không thể hoàn tác.')) return;
  try {
    const res = await authFetch(`${API}/docs/drafts/${draftId}`, { method: 'DELETE' });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Xóa thất bại'); }
    showToast('Đã xóa bản nháp', 'success');
    loadDraftsPage(true);
  } catch (e) {
    showToast(e.message, 'error');
  }
};

// ── Helpers ───────────────────────────────────────────────────────────────────

function formatDate(dateStr) {
  if (!dateStr) return 'N/A';
  try {
    return new Date(dateStr).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
}
