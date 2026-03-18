/**
 * Prompts Management Module
 * List / search / view / edit skill prompts
 */
import { showToast, escapeHtml, kpConfirm } from '../utils/ui.js';
import { authFetch } from '../api/client.js';

const PROMPTS_API = '/api/prompts';

let _prompts = [];           // [{doc_type, label, description, system_prompt, updated_at, updated_by}]
let _selected = null;        // currently selected doc_type
let _editMode = false;
let _originalPrompt = '';    // snapshot before edit for dirty detection
let _defaultPrompt = '';     // hardcoded default from server

// ── Fetch helpers ──────────────────────────────────────────────────────────

async function fetchList() {
  const res = await authFetch(PROMPTS_API);
  if (!res.ok) throw new Error('Không thể tải danh sách prompt');
  const data = await res.json();
  return data.prompts || [];
}

async function fetchOne(docType) {
  const res = await authFetch(`${PROMPTS_API}/${docType}`);
  if (!res.ok) throw new Error(`Không thể tải prompt: ${docType}`);
  return res.json();
}

async function savePrompt(docType, systemPrompt) {
  const res = await authFetch(`${PROMPTS_API}/${docType}`, {
    method: 'PUT',
    body: JSON.stringify({ system_prompt: systemPrompt }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Lưu thất bại');
  }
  return res.json();
}

async function resetPrompt(docType) {
  const res = await authFetch(`${PROMPTS_API}/${docType}/reset`, { method: 'POST' });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Reset thất bại');
  }
  return res.json();
}


// ── Render ─────────────────────────────────────────────────────────────────

function renderList(filter = '') {
  const list = document.getElementById('promptListItems');
  if (!list) return;

  const q = filter.toLowerCase().trim();
  const filtered = q
    ? _prompts.filter(p =>
        p.label.toLowerCase().includes(q) ||
        p.description.toLowerCase().includes(q) ||
        p.doc_type.toLowerCase().includes(q)
      )
    : _prompts;

  list.innerHTML = filtered.length === 0
    ? `<div class="prompt-list-empty">Không tìm thấy kết quả</div>`
    : filtered.map(p => `
      <div class="prompt-list-item ${_selected === p.doc_type ? 'active' : ''}"
           data-doctype="${p.doc_type}" id="pl-${p.doc_type}">
        <div class="prompt-item-label">${escapeHtml(p.label)}</div>
        <div class="prompt-item-desc">${escapeHtml(p.description)}</div>
        <div class="prompt-item-meta">
          <span class="prompt-item-type">${escapeHtml(p.doc_type)}</span>
          ${p.updated_by !== 'system' ? `<span class="prompt-item-modified">✏️ đã sửa</span>` : ''}
        </div>
      </div>
    `).join('');

  list.querySelectorAll('.prompt-list-item').forEach(el => {
    el.addEventListener('click', () => selectPrompt(el.dataset.doctype));
  });
}

async function selectPrompt(docType) {
  if (_editMode && _selected === docType) return;

  // Confirm leave edit if dirty
  if (_editMode && isPromptDirty()) {
    const yes = await kpConfirm({
      title: 'Thay đổi chưa lưu',
      message: 'Bạn có thay đổi chưa lưu. Thoát không?',
      okText: 'Thoát',
      cancelText: 'Ở lại',
      danger: true,
    });
    if (!yes) return;
  }

  _selected = docType;
  _editMode = false;
  renderList(document.getElementById('promptSearchInput')?.value || '');
  renderDetail(null); // loading state

  try {
    const data = await fetchOne(docType);
    _originalPrompt = data.system_prompt || '';
    _defaultPrompt = data.default_prompt || '';
    renderDetail(data);
  } catch (e) {
    showToast(e.message, 'error');
  }
}

function renderDetail(data) {
  const panel = document.getElementById('promptDetailPanel');
  if (!panel) return;

  if (!_selected) {
    panel.innerHTML = `
      <div class="prompt-detail-empty">
        <span>👈</span>
        <p>Chọn một agent từ danh sách để xem và chỉnh sửa prompt</p>
      </div>
    `;
    return;
  }

  if (!data) {
    panel.innerHTML = `<div class="prompt-detail-loading">Đang tải...</div>`;
    return;
  }

  const isModified = data.updated_by !== 'system';
  const updatedAt = data.updated_at
    ? new Date(data.updated_at).toLocaleString('vi-VN')
    : '';

  panel.innerHTML = `
    <div class="prompt-detail-header">
      <div class="prompt-detail-meta">
        <div class="prompt-detail-label">${escapeHtml(data.label || data.doc_type)}</div>
        <div class="prompt-detail-desc">${escapeHtml(data.description || '')}</div>
        ${updatedAt ? `<div class="prompt-detail-time">Cập nhật: ${updatedAt} ${isModified ? '· bởi ' + escapeHtml(data.updated_by) : '(mặc định)'}</div>` : ''}
      </div>
      <div class="prompt-detail-actions" id="promptDetailActions">
        ${renderDetailActions(isModified)}
      </div>
    </div>
    <div class="prompt-editor-wrap" id="promptEditorWrap">
      <div class="prompt-editor-toolbar">
        <span class="prompt-char-count" id="promptCharCount">${data.system_prompt?.length ?? 0} ký tự</span>
        ${_editMode ? '<span class="prompt-edit-hint">✏️ Đang chỉnh sửa</span>' : ''}
      </div>
      <textarea
        id="promptTextarea"
        class="prompt-textarea ${_editMode ? 'editable' : 'readonly'}"
        ${_editMode ? '' : 'readonly'}
        spellcheck="false"
      >${escapeHtml(data.system_prompt || '')}</textarea>
    </div>
  `;

  const textarea = document.getElementById('promptTextarea');
  if (textarea) {
    textarea.addEventListener('input', () => {
      const cc = document.getElementById('promptCharCount');
      if (cc) cc.textContent = `${textarea.value.length} ký tự`;
    });
  }

  bindDetailActions(data, isModified);
}

function renderDetailActions(isModified) {
  if (_editMode) {
    return `
      <button class="prompt-btn prompt-btn-save" id="promptSaveBtn">💾 Lưu</button>
      <button class="prompt-btn prompt-btn-cancel" id="promptCancelBtn">✕ Huỷ</button>
    `;
  }
  return `
    <button class="prompt-btn prompt-btn-edit" id="promptEditBtn">✏️ Sửa</button>
    ${isModified ? `<button class="prompt-btn prompt-btn-reset" id="promptResetBtn">🔄 Đặt lại mặc định</button>` : ''}
  `;
}

function bindDetailActions(data, isModified) {
  document.getElementById('promptEditBtn')?.addEventListener('click', () => {
    _editMode = true;
    renderDetail(data);
    setTimeout(() => document.getElementById('promptTextarea')?.focus(), 50);
  });

  document.getElementById('promptCancelBtn')?.addEventListener('click', () => {
    _editMode = false;
    renderDetail(data);
  });

  document.getElementById('promptSaveBtn')?.addEventListener('click', async () => {
    const textarea = document.getElementById('promptTextarea');
    const newPrompt = (textarea?.value || '').trim();
    if (!newPrompt) { showToast('Prompt không được để trống', 'error'); return; }

    const btn = document.getElementById('promptSaveBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Đang lưu...'; }

    try {
      await savePrompt(_selected, newPrompt);
      showToast('Đã lưu prompt thành công', 'success');
      _originalPrompt = newPrompt;
      _editMode = false;
      // Refresh list to update "đã sửa" badge
      _prompts = await fetchList();
      renderList(document.getElementById('promptSearchInput')?.value || '');
      const refreshed = await fetchOne(_selected);
      renderDetail(refreshed);
    } catch (e) {
      showToast(e.message, 'error');
      if (btn) { btn.disabled = false; btn.textContent = '💾 Lưu'; }
    }
  });

  document.getElementById('promptResetBtn')?.addEventListener('click', async () => {
    const shouldReset = await kpConfirm({
      title: '🔄 Đặt lại prompt',
      message: `Đặt lại prompt "${data.label}" về mặc định? Thay đổi tuỳ chỉnh sẽ bị mất.`,
      okText: 'Đặt lại',
      cancelText: 'Huỷ',
      danger: true,
    });
    if (!shouldReset) return;
    try {
      await resetPrompt(_selected);
      showToast('Đã đặt lại về mặc định', 'success');
      _editMode = false;
      _prompts = await fetchList();
      renderList(document.getElementById('promptSearchInput')?.value || '');
      const refreshed = await fetchOne(_selected);
      _originalPrompt = refreshed.system_prompt || '';
      renderDetail(refreshed);
    } catch (e) {
      showToast(e.message, 'error');
    }
  });
}

function isPromptDirty() {
  const ta = document.getElementById('promptTextarea');
  return ta && ta.value.trim() !== _originalPrompt.trim();
}

// ── Page initializer ───────────────────────────────────────────────────────

export async function loadPromptsPage() {
  _selected = null;
  _editMode = false;

  const container = document.getElementById('page-prompts');
  if (!container) return;

  container.innerHTML = `
    <div class="prompts-page">
      <div class="prompts-sidebar">
        <div class="prompts-sidebar-header">
          <h2 class="prompts-sidebar-title">🗂️ Skill Prompts</h2>
          <p class="prompts-sidebar-subtitle">Xem và tuỳ chỉnh hướng dẫn cho từng agent BA</p>
        </div>
        <div class="prompts-search-wrap">
          <input type="search" id="promptSearchInput" class="prompts-search-input"
            placeholder="🔍 Tìm theo tên agent..." autocomplete="off" />
        </div>
        <div class="prompt-list-items" id="promptListItems">
          <div class="prompt-detail-loading">Đang tải...</div>
        </div>
      </div>
      <div class="prompts-detail" id="promptDetailPanel">
        <div class="prompt-detail-empty">
          <span>👈</span>
          <p>Chọn một agent từ danh sách để xem và chỉnh sửa prompt</p>
        </div>
      </div>
    </div>
  `;

  document.getElementById('promptSearchInput')?.addEventListener('input', e => {
    renderList(e.target.value);
  });

  try {
    _prompts = await fetchList();
    renderList();
  } catch (e) {
    showToast(e.message, 'error');
  }
}

