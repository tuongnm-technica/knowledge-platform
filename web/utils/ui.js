export async function readApiError(response) {
  const payload = await response.json().catch(() => ({}));
  return payload.detail || payload.message || `Request failed (${response.status})`;
}

export function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

export function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatNumber(value) {
  return Number(value || 0).toLocaleString('vi-VN');
}

export function showToast(msg, type = 'success') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

let KP_MODAL_STATE = null;

export function _kpEnsureModalElements() {
  let overlay = document.getElementById('kpModalOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'kpModalOverlay';
    overlay.className = 'kp-modal-overlay';
    overlay.style.display = 'none';
    overlay.innerHTML = `
      <div class="kp-modal" role="dialog" aria-modal="true" aria-labelledby="kpModalTitle">
        <div class="kp-modal-header">
          <div class="kp-modal-header-copy">
            <div id="kpModalTitle" class="kp-modal-title"></div>
            <div id="kpModalSubtitle" class="kp-modal-sub"></div>
          </div>
          <button id="kpModalCloseBtn" class="kp-modal-close" type="button" aria-label="Close">&times;</button>
        </div>
        <div id="kpModalBody" class="kp-modal-body"></div>
        <div id="kpModalError" class="kp-modal-error" style="display:none"></div>
        <div class="kp-modal-actions">
          <button id="kpModalCancelBtn" class="secondary-btn" type="button">Cancel</button>
          <button id="kpModalOkBtn" class="primary-btn" type="button">OK</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
  }

  const titleEl = document.getElementById('kpModalTitle');
  const subtitleEl = document.getElementById('kpModalSubtitle');
  const bodyEl = document.getElementById('kpModalBody');
  const errorEl = document.getElementById('kpModalError');
  const okBtn = document.getElementById('kpModalOkBtn');
  const cancelBtn = document.getElementById('kpModalCancelBtn');
  const closeBtn = document.getElementById('kpModalCloseBtn');

  return { overlay, titleEl, subtitleEl, bodyEl, errorEl, okBtn, cancelBtn, closeBtn };
}

export function _kpCloseModal(result) {
  const els = _kpEnsureModalElements();
  els.overlay.style.display = 'none';
  els.bodyEl.innerHTML = '';
  els.errorEl.style.display = 'none';
  els.errorEl.textContent = '';
  document.body.classList.remove('kp-modal-open');

  const state = KP_MODAL_STATE;
  KP_MODAL_STATE = null;
  if (state && typeof state.cleanup === 'function') state.cleanup();
  if (state && state.previouslyFocused && typeof state.previouslyFocused.focus === 'function') {
    try { state.previouslyFocused.focus(); } catch (_) {}
  }
  if (state && typeof state.resolve === 'function') state.resolve(result);
}

export function _kpSetModalError(message) {
  const els = _kpEnsureModalElements();
  els.errorEl.textContent = String(message || 'Invalid input.');
  els.errorEl.style.display = '';
}

export function kpOpenModal({ title, subtitle, content, okText = 'OK', cancelText = 'Cancel', okClass = 'primary-btn', onOk } = {}) {
  const els = _kpEnsureModalElements();
  if (KP_MODAL_STATE) _kpCloseModal(null);

  els.titleEl.textContent = String(title || '');
  els.subtitleEl.textContent = String(subtitle || '');
  els.subtitleEl.style.display = subtitle ? '' : 'none';
  els.bodyEl.innerHTML = '';
  els.errorEl.style.display = 'none';
  els.errorEl.textContent = '';
  els.okBtn.textContent = okText;
  els.cancelBtn.textContent = cancelText;
  els.cancelBtn.style.display = cancelText ? '' : 'none';
  els.okBtn.className = okClass;

  const previouslyFocused = document.activeElement;

  if (content) {
    if (typeof content === 'string') {
      els.bodyEl.innerHTML = content;
    } else {
      els.bodyEl.appendChild(content);
    }
  }

  const handleCancel = () => _kpCloseModal(null);
  const handleOk = async () => {
    if (!KP_MODAL_STATE) return;
    try {
      const out = onOk ? await onOk() : true;
      if (out && typeof out === 'object' && out.error) {
        _kpSetModalError(out.error);
        return;
      }
      if (out === false) return;
      _kpCloseModal(out);
    } catch (e) {
      _kpSetModalError(e && e.message ? e.message : 'Action failed.');
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
    }
  };

  const onOverlayClick = (e) => {
    if (e.target === els.overlay) handleCancel();
  };

  els.cancelBtn.addEventListener('click', handleCancel);
  els.closeBtn.addEventListener('click', handleCancel);
  els.okBtn.addEventListener('click', handleOk);
  els.overlay.addEventListener('click', onOverlayClick);
  document.addEventListener('keydown', onKeyDown);

  KP_MODAL_STATE = {
    resolve: null,
    previouslyFocused,
    cleanup: () => {
      els.cancelBtn.removeEventListener('click', handleCancel);
      els.closeBtn.removeEventListener('click', handleCancel);
      els.okBtn.removeEventListener('click', handleOk);
      els.overlay.removeEventListener('click', onOverlayClick);
      document.removeEventListener('keydown', onKeyDown);
    },
  };

  els.overlay.style.display = 'flex';
  document.body.classList.add('kp-modal-open');

  setTimeout(() => {
    const first = els.bodyEl.querySelector('input, select, textarea, button');
    if (first && typeof first.focus === 'function') first.focus();
  }, 0);

  return new Promise(resolve => {
    if (!KP_MODAL_STATE) return resolve(null);
    KP_MODAL_STATE.resolve = resolve;
  });
}

export function kpConfirm({ title, message, okText = 'OK', cancelText = 'Cancel', danger = false } = {}) {
  const body = document.createElement('div');
  body.className = 'kp-modal-confirm';
  const p = document.createElement('div');
  p.className = 'kp-modal-confirm-text';
  p.textContent = String(message || '');
  body.appendChild(p);
  return kpOpenModal({
    title,
    subtitle: '',
    content: body,
    okText,
    cancelText,
    okClass: danger ? 'danger-btn' : 'primary-btn',
    onOk: () => true,
  }).then(res => !!res);
}

export function _kpBuildModalField({ id, label, type = 'text', value = '', placeholder = '', help = '', required = false, options = null } = {}) {
  const wrap = document.createElement('div');
  wrap.className = 'kp-modal-field';

  const lab = document.createElement('label');
  lab.className = 'kp-modal-label';
  lab.setAttribute('for', id);
  lab.textContent = label;
  wrap.appendChild(lab);

  let input = null;
  if (type === 'select') {
    input = document.createElement('select');
    (options || []).forEach(opt => {
      const o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.label;
      input.appendChild(o);
    });
    input.value = String(value || '');
  } else if (type === 'textarea') {
    input = document.createElement('textarea');
    input.value = String(value || '');
    input.rows = 4;
  } else {
    input = document.createElement('input');
    input.type = type;
    input.value = String(value || '');
  }

  input.id = id;
  input.name = id;
  input.className = 'time-input kp-modal-input';
  if (placeholder) input.placeholder = placeholder;
  if (required) input.required = true;

  wrap.appendChild(input);

  if (help) {
    const h = document.createElement('div');
    h.className = 'kp-modal-help';
    h.textContent = help;
    wrap.appendChild(h);
  }

  return { wrap, input };
}