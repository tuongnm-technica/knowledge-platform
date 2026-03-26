export async function readApiError(response: Response): Promise<string> {
    const payload = await response.json().catch(() => ({}));
    return payload.detail || payload.message || `Request failed (${response.status})`;
}

export function escapeHtml(value: string | null | undefined): string {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

export function formatDateTime(value: string | number | Date | null | undefined): string {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('vi-VN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

export function formatNumber(value: number | string | null | undefined): string {
    return Number(value || 0).toLocaleString('vi-VN');
}

export function showToast(msg: string, type: 'success' | 'error' | 'warning' | 'info' = 'success'): void {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast ${type} glass-panel`;
    
    const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : (type === 'warning' ? '⚠️' : 'ℹ️'));
    toast.innerHTML = `<span class="toast-icon">${icon}</span> <span class="toast-msg">${msg}</span>`;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px) scale(0.95)';
        setTimeout(() => toast.remove(), 400);
    }, 4000);
}

// --- Modal System ---

interface ModalState {
    resolve: ((value: any) => void) | null;
    previouslyFocused: Element | null;
    cleanup: () => void;
}

let KP_MODAL_STATE: ModalState | null = null;

interface ModalElements {
    overlay: HTMLElement;
    titleEl: HTMLElement;
    subtitleEl: HTMLElement;
    bodyEl: HTMLElement;
    errorEl: HTMLElement;
    okBtn: HTMLButtonElement;
    cancelBtn: HTMLButtonElement;
    closeBtn: HTMLButtonElement;
}

export function _kpEnsureModalElements(): ModalElements {
    let overlay = document.getElementById('kpModalOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'kpModalOverlay';
        overlay.className = 'kp-modal-overlay';
        overlay.style.display = 'none';
        overlay.innerHTML = `
            <div class="kp-modal glass-panel" role="dialog" aria-modal="true" aria-labelledby="kpModalTitle">
                <div class="kp-modal-header">
                    <div class="kp-modal-header-copy">
                        <div id="kpModalTitle" class="kp-modal-title"></div>
                        <div id="kpModalSubtitle" class="kp-modal-sub"></div>
                    </div>
                    <button id="kpModalCloseBtn" class="kp-modal-close" type="button" aria-label="Close">
                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                    </button>
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

    return {
        overlay,
        titleEl: document.getElementById('kpModalTitle') as HTMLElement,
        subtitleEl: document.getElementById('kpModalSubtitle') as HTMLElement,
        bodyEl: document.getElementById('kpModalBody') as HTMLElement,
        errorEl: document.getElementById('kpModalError') as HTMLElement,
        okBtn: document.getElementById('kpModalOkBtn') as HTMLButtonElement,
        cancelBtn: document.getElementById('kpModalCancelBtn') as HTMLButtonElement,
        closeBtn: document.getElementById('kpModalCloseBtn') as HTMLButtonElement,
    };
}

export function _kpCloseModal<T>(result: T | null): void {
    const els = _kpEnsureModalElements();
    els.overlay.style.display = 'none';
    els.bodyEl.innerHTML = '';
    els.errorEl.style.display = 'none';
    els.errorEl.textContent = '';
    els.okBtn.disabled = false;
    els.cancelBtn.disabled = false;
    document.body.classList.remove('kp-modal-open');

    const state = KP_MODAL_STATE;
    KP_MODAL_STATE = null;
    if (state && typeof state.cleanup === 'function') state.cleanup();
    if (state && state.previouslyFocused && typeof (state.previouslyFocused as HTMLElement).focus === 'function') {
        try { (state.previouslyFocused as HTMLElement).focus(); } catch (_) {}
    }
    if (state && typeof state.resolve === 'function' && state.resolve) state.resolve(result);
}

export function _kpSetModalError(message: string): void {
    const els = _kpEnsureModalElements();
    els.errorEl.textContent = String(message || 'Invalid input.');
    els.errorEl.style.display = '';
}

export interface OpenModalOptions<T = any> {
    title?: string;
    subtitle?: string;
    content?: string | HTMLElement;
    okText?: string;
    cancelText?: string | null;
    okClass?: string;
    modalClass?: string;
    contentStyles?: Partial<CSSStyleDeclaration>;
    onOk?: () => Promise<T | { error: string } | boolean> | T | { error: string } | boolean;
}

export function kpOpenModal<T = any>({ title, subtitle, content, okText = 'OK', cancelText = 'Cancel', okClass = 'primary-btn', modalClass = '', contentStyles, onOk }: OpenModalOptions<T> = {}): Promise<T | null> {
    const els = _kpEnsureModalElements();
    if (KP_MODAL_STATE) _kpCloseModal(null);

    els.titleEl.textContent = String(title || '');
    els.subtitleEl.textContent = String(subtitle || '');
    els.subtitleEl.style.display = subtitle ? '' : 'none';
    els.bodyEl.innerHTML = '';
    els.errorEl.style.display = 'none';
    els.errorEl.textContent = '';
    els.okBtn.textContent = okText;
    els.okBtn.disabled = false;
    els.cancelBtn.textContent = cancelText || '';
    els.cancelBtn.disabled = false;
    els.cancelBtn.style.display = cancelText ? '' : 'none';
    els.okBtn.className = okClass;
    
    const modalEl = els.overlay.querySelector('.kp-modal') as HTMLElement;
    if (modalEl) {
        modalEl.className = `kp-modal glass-panel ${modalClass || ''}`;
        // Apply custom content styles if provided
        if (contentStyles) {
            Object.assign(modalEl.style, contentStyles);
        } else {
            // Reset styles if not provided (for modal reuse)
            modalEl.style.maxWidth = '';
            modalEl.style.width = '';
        }
    }

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
        const oldText = els.okBtn.textContent;
        try {
            els.okBtn.disabled = true;
            els.okBtn.textContent = 'Đang xử lý...';
            els.cancelBtn.disabled = true;

            const out = onOk ? await onOk() : true;
            if (out && typeof out === 'object' && 'error' in (out as object)) {
                _kpSetModalError((out as { error: string }).error);
                els.okBtn.disabled = false;
                els.okBtn.textContent = oldText;
                els.cancelBtn.disabled = false;
                return;
            }
            if (out === false) {
                els.okBtn.disabled = false;
                els.okBtn.textContent = oldText;
                els.cancelBtn.disabled = false;
                return;
            }
            _kpCloseModal(out as T);
        } catch (err) {
            const error = err as Error;
            _kpSetModalError(error.message || 'Action failed.');
            els.okBtn.disabled = false;
            els.okBtn.textContent = oldText;
            els.cancelBtn.disabled = false;
        }
    };

    const onKeyDown = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
            e.preventDefault();
            handleCancel();
        }
    };

    const onOverlayClick = (e: MouseEvent) => {
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
        const first = els.bodyEl.querySelector('input, select, textarea, button') as HTMLElement | null;
        if (first && typeof first.focus === 'function') first.focus();
    }, 0);

    return new Promise(resolve => {
        if (!KP_MODAL_STATE) return resolve(null);
        KP_MODAL_STATE.resolve = resolve;
    });
}

export function kpConfirm({ title, message, okText = 'OK', cancelText = 'Cancel', danger = false }: ConfirmOptions = {}): Promise<boolean> {
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

export function kpPrompt({ title, message, placeholder = '', defaultValue = '', okText = 'OK', cancelText = 'Cancel' }: PromptOptions = {}): Promise<string | null> {
    const body = document.createElement('div');
    body.className = 'kp-modal-confirm';
    if (message) {
        const p = document.createElement('div');
        p.className = 'kp-modal-confirm-text';
        p.textContent = String(message);
        body.appendChild(p);
    }
    const input = document.createElement('input');
    input.type = 'text';
    input.className = 'time-input kp-modal-input kp-prompt-input';
    input.placeholder = placeholder;
    input.value = defaultValue;
    body.appendChild(input);

    return kpOpenModal({
        title,
        subtitle: '',
        content: body,
        okText,
        cancelText,
        okClass: 'primary-btn',
        onOk: () => {
            const val = input.value.trim();
            if (!val) return { error: 'Vui lòng nhập giá trị' };
            return val;
        },
    });
}

export function _kpBuildModalField({ id, label, type = 'text', value = '', placeholder = '', help = '', required = false, options = null }: BuildFieldOptions): { wrap: HTMLElement, input: HTMLElement } {
    const wrap = document.createElement('div');
    wrap.className = 'kp-modal-field';

    const lab = document.createElement('label');
    lab.className = 'kp-modal-label';
    lab.setAttribute('for', id);
    lab.textContent = label;
    wrap.appendChild(lab);

    let input: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;
    
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
    
    if (type === 'select') {
        input.className = 'form-select kp-modal-input';
    } else if (type === 'textarea') {
        input.className = 'form-textarea kp-modal-input';
    } else {
        input.className = type === 'time' ? 'time-input kp-modal-input' : 'form-input kp-modal-input';
    }

    if (placeholder && input.tagName !== 'SELECT') {
        (input as HTMLInputElement | HTMLTextAreaElement).placeholder = placeholder;
    }
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

/**
 * Cập nhật Badge (số lượng) trên Sidebar hoặc Header
 * @param key 'tasks' | 'drafts' | 'basket'
 * @param count số lượng
 */
export function updateBadge(key: string, count: number): void {
    const el = document.getElementById(`nav-${key}-badge`);
    if (!el) return;
    
    if (count > 0) {
        el.textContent = String(count);
        el.style.display = 'inline-flex';
    } else {
        el.style.display = 'none';
    }

    // Đồng bộ với Alpine store nếu nó còn tồn tại (compat layer)
    const win = window as any;
    if (win.Alpine?.store('badges')) {
        win.Alpine.store('badges')[key] = count;
    }
}

export interface BuildFieldOptions {
    id: string;
    label: string;
    type?: 'text' | 'select' | 'textarea' | 'time' | 'password' | 'email' | 'number' | string;
    value?: string | number;
    placeholder?: string;
    help?: string;
    required?: boolean;
    options?: FieldOption[] | null;
}

export interface FieldOption {
    value: string;
    label: string;
}

export interface PromptOptions {
    title?: string;
    message?: string;
    placeholder?: string;
    defaultValue?: string;
    okText?: string;
    cancelText?: string;
}

export interface ConfirmOptions {
    title?: string;
    message?: string;
    okText?: string;
    cancelText?: string;
    danger?: boolean;
}