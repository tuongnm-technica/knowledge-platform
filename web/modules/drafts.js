// Drafts Module - Bản nháp tài liệu (docs/drafts endpoint)
console.log('[Drafts] Loading module...');
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml, kpConfirm, kpOpenModal, kpPrompt } from '../utils/ui.js';

let _currentDraftId = null;
let _currentDraftData = null;

// ── Load list ─────────────────────────────────────────────────────────────────

export async function loadDraftsPage(refresh = false) {
  const container = document.getElementById('draftsList');
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
  const container = document.getElementById('draftsList');
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
    const statusColor = draft.status === 'approved' ? 'var(--success)'
                      : draft.status === 'rejected'  ? 'var(--danger)'
                      : draft.status === 'published' ? 'var(--accent)'
                      : 'var(--text-muted)';
    card.innerHTML = `
      <div class="draft-header">
        <div class="draft-type">${escapeHtml(docType)}</div>
        <div class="draft-title">${escapeHtml(draft.title || 'Untitled')}</div>
        <span style="font-size:11px;padding:2px 8px;border-radius:12px;background:color-mix(in srgb, ${statusColor} 15%, transparent);color:${statusColor}">
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
  const container = document.getElementById('draftsList');
  if (container) container.innerHTML = '<div class="drafts-loading">Đang tải bản nháp...</div>';

  try {
    const res = await authFetch(`${API}/docs/drafts/${draftId}`);
    if (!res.ok) throw new Error('Không tải được draft');
    const data = await res.json();
    _currentDraftData = data.draft;
    renderDraftEditor(_currentDraftData);
  } catch (e) {
    showToast(e.message, 'error');
    loadDraftsPage();
  }
};

function renderDraftEditor(draft) {
  const container = document.getElementById('draftsList');
  if (!container) return;

  container.innerHTML = `
    <div class="draft-editor">
      <div class="draft-editor-header" style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
        <button class="secondary-btn mini" onclick="window.closeDraftEditor()">← Quay lại</button>
        <span class="draft-type" style="font-size:13px">${escapeHtml((draft.doc_type || 'srs').toUpperCase())}</span>
        <input id="draftTitleInput" type="text" class="time-input kp-modal-input" value="${escapeHtml(draft.title || '')}"
               style="flex:1;font-size:15px;font-weight:600" placeholder="Tiêu đề...">
        ${draft.structured_data && Object.keys(draft.structured_data).length > 0 ? `<button class="secondary-btn mini" onclick="window.viewStructuredData()" title="Xem dữ liệu cấu trúc bóc tách từ LLM">📦 JSON</button>` : ''}
        <button class="secondary-btn" onclick="window.refineDraftSelection()" title="Bôi đen văn bản và bấm để AI viết lại">✨ AI Viết lại</button>
        <button class="primary-btn" onclick="window.saveDraft()">💾 Lưu</button>
      </div>

      <div style="margin-bottom:8px;display:flex;gap:8px;align-items:center">
        <label style="color:var(--text-muted);font-size:12px">Trạng thái:</label>
        <select id="draftStatusSelect" class="time-input kp-modal-input" style="font-size:12px;padding:4px 8px">
          <option value="draft" ${draft.status === 'draft' ? 'selected' : ''}>Draft</option>
          <option value="review" ${draft.status === 'review' ? 'selected' : ''}>Đang review</option>
          <option value="approved" ${draft.status === 'approved' ? 'selected' : ''}>Approved</option>
          <option value="published" ${draft.status === 'published' ? 'selected' : ''}>Published</option>
          <option value="rejected" ${draft.status === 'rejected' ? 'selected' : ''}>Rejected</option>
        </select>
        <span style="color:var(--text-dim);font-size:11px">Cập nhật: ${formatDate(draft.updated_at || draft.created_at)}</span>
      </div>

      <textarea id="draftContentEditor"
        style="width:100%;min-height:480px;background:var(--bg3);
               border:1px solid var(--border-strong);border-radius:var(--radius);padding:16px;
               color:var(--text);font-family:'JetBrains Mono','Fira Code',monospace;
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

window.refineDraftSelection = async function () {
  if (!_currentDraftId) return;
  const editor = document.getElementById('draftContentEditor');
  if (!editor) return;

  const start = editor.selectionStart;
  const end = editor.selectionEnd;
  const selectedText = editor.value.substring(start, end).trim();

  if (!selectedText || selectedText.length < 5) {
    showToast('Hãy bôi đen đoạn văn bản (ít nhất 5 ký tự) cần sửa trước', 'warning');
    return;
  }

  const instruction = await kpPrompt({
    title: '✨ Gợi ý cho AI',
    message: 'Bạn muốn AI sửa đoạn văn bản đang chọn như thế nào?<br><br><i>Ví dụ: Viết ngắn lại, Dịch qua tiếng Anh, Thêm rule xác thực OTP...</i>',
    okText: 'Viết lại',
    placeholder: 'Nhập yêu cầu tại đây...'
  });

  if (!instruction) return;

  showToast('AI đang phân tích và viết lại...', 'info');

  try {
    const res = await authFetch(`${API}/docs/drafts/${_currentDraftId}/refine`, {
      method: 'POST',
      body: JSON.stringify({ 
        selected_text: selectedText, 
        instruction: instruction 
      }),
    });
    
    if (!res.ok) {
        const e = await res.json();
        throw new Error(e.detail || 'Lỗi kết nối AI');
    }
    
    const data = await res.json();
    const refinedText = data.refined_text;

    // Replace text inline
    const before = editor.value.substring(0, start);
    const after = editor.value.substring(end);
    editor.value = before + refinedText + after;
    
    // Highlight newly replaced text
    editor.focus();
    editor.setSelectionRange(start, start + refinedText.length);

    showToast('Đã viết lại xong! Hãy kiểm tra và Lưu (💾)', 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
};

window.closeDraftEditor = function () {
  _currentDraftId = null;
  _currentDraftData = null;
  loadDraftsPage();
};

window.viewStructuredData = function() {
  if (!_currentDraftData || !_currentDraftData.structured_data) return;
  const jsonStr = JSON.stringify(_currentDraftData.structured_data, null, 2);
  kpOpenModal({
    title: 'Dữ liệu cấu trúc (JSON)',
    content: `<textarea readonly style="width:100%;height:400px;font-family:monospace;font-size:12px;padding:8px;background:var(--bg3);color:var(--text);border:1px solid var(--border);border-radius:var(--radius);resize:none;">${escapeHtml(jsonStr)}</textarea>`,
    actions: '<button class="secondary-btn" onclick="window.closeKpModal()">Đóng</button>'
  });
};

// ── Delete draft ──────────────────────────────────────────────────────────────

window.deleteDraft = async function (draftId) {
  const confirmed = await kpConfirm({
    title: '🗑 Xóa bản nháp',
    message: 'Xóa bản nháp này? Hành động này không thể hoàn tác.',
    okText: 'Xóa',
    cancelText: 'Huỷ',
    danger: true,
  });
  if (!confirmed) return;
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
