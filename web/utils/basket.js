import { API, authFetch } from '../api/client.js';
import { getBadgeClass } from '../utils/format.js';
import { showToast, escapeHtml, readApiError, kpOpenModal } from '../utils/ui.js';

const BASKET_STORAGE_KEY = 'kp_context_basket_v1';
const BASKET_TOKEN_LIMIT = 32000;
export let basketState = {
  items: [], // { document_id, included, title, source, url, token_estimate, content_len, updated_at }
};

export function _loadBasket() {
  try {
    const raw = localStorage.getItem(BASKET_STORAGE_KEY);
    const data = raw ? JSON.parse(raw) : {};
    const items = Array.isArray(data.items) ? data.items : [];
    basketState.items = items
      .map(it => ({
        document_id: String(it.document_id || '').trim(),
        included: it.included !== false,
        title: String(it.title || '').trim(),
        source: String(it.source || '').trim(),
        url: String(it.url || '').trim(),
        token_estimate: Number(it.token_estimate || 0) || 0,
        content_len: Number(it.content_len || 0) || 0,
        updated_at: it.updated_at || null,
      }))
      .filter(it => !!it.document_id);
  } catch {
    basketState.items = [];
  }
}

export function _saveBasket() {
  try {
    localStorage.setItem(BASKET_STORAGE_KEY, JSON.stringify({ items: basketState.items || [] }));
  } catch {}
}

export function _basketIncludedIds() {
  return (basketState.items || []).filter(i => i.included).map(i => i.document_id);
}

export function _basketTokenUsed() {
  return (basketState.items || []).filter(i => i.included).reduce((s, it) => s + (Number(it.token_estimate || 0) || 0), 0);
}

export function toggleBasketDrawer() {
  const drawer = document.getElementById('basketDrawer');
  const overlay = document.getElementById('basketOverlay');
  if (!drawer || !overlay) return;
  const isOpen = drawer.style.display !== 'none';
  if (isOpen) return closeBasketDrawer();
  return openBasketDrawer();
}

export function openBasketDrawer() {
  const drawer = document.getElementById('basketDrawer');
  const overlay = document.getElementById('basketOverlay');
  if (!drawer || !overlay) return;
  drawer.style.display = '';
  overlay.style.display = '';
  _loadBasket();
  renderBasket();
  refreshBasketDetails();
}

export function closeBasketDrawer() {
  const drawer = document.getElementById('basketDrawer');
  const overlay = document.getElementById('basketOverlay');
  if (drawer) drawer.style.display = 'none';
  if (overlay) overlay.style.display = 'none';
}

export function clearBasket() {
  basketState.items = [];
  _saveBasket();
  renderBasket();
  showToast('Đã xóa giỏ ngữ cảnh.', 'success');
}

export async function refreshBasketDetails() {
  const ids = (basketState.items || []).map(i => i.document_id);
  if (!ids.length) return renderBasket();
  try {
    const sub = document.getElementById('basketSub');
    const sub2 = document.getElementById('basketPageSub');
    if (sub) sub.textContent = `${(basketState.items || []).length} items · đang tải...`;
    if (sub2) sub2.textContent = `${(basketState.items || []).length} items · đang tải...`;
  } catch {}
  try {
    const r = await authFetch(`${API}/documents/batch`, {
      method: 'POST',
      body: JSON.stringify({ ids, include_content: false }),
    });
    if (!r.ok) throw new Error(await readApiError(r));
    const data = await r.json();
    const docs = (data && data.documents) ? data.documents : [];
    const byId = {};
    for (const d of docs) byId[String(d.id || '')] = d;
    basketState.items = (basketState.items || []).map(it => {
      const d = byId[it.document_id];
      if (!d) return it;
      return {
        ...it,
        title: String(d.title || it.title || ''),
        source: String(d.source || it.source || ''),
        url: String(d.url || it.url || ''),
        token_estimate: Number(d.token_estimate || it.token_estimate || 0) || 0,
        content_len: Number(d.content_len || it.content_len || 0) || 0,
        updated_at: d.updated_at || it.updated_at || null,
      };
    });
    _saveBasket();
    renderBasket();
  } catch (e) {
    renderBasket();
  }
}

export async function basketAddDocument(documentId, { openDrawer = true, silent = false } = {}) {
  const id = String(documentId || '').trim();
  if (!id) return;
  _loadBasket();
  if ((basketState.items || []).some(i => i.document_id === id)) {
    if (!silent) showToast('Item đã có trong giỏ.', 'info');
    if (openDrawer) openBasketDrawer();
    return;
  }

  basketState.items = [
    ...(basketState.items || []),
    { document_id: id, included: true, title: '', source: '', url: '', token_estimate: 0, content_len: 0, updated_at: null },
  ];
  _saveBasket();
  renderBasket();
  if (openDrawer) openBasketDrawer();
  await refreshBasketDetails();
  if (!silent) showToast('Đã ghim vào giỏ.', 'success');
}

export async function basketAddDocuments(docIds, { openDrawer = true } = {}) {
  const ids = Array.isArray(docIds) ? docIds : [];
  _loadBasket();
  const existing = new Set((basketState.items || []).map(i => i.document_id));
  const unique = [];
  const seen = new Set();
  for (const v of ids) {
    const s = String(v || '').trim();
    if (!s || seen.has(s) || existing.has(s)) continue;
    seen.add(s);
    unique.push(s);
  }
  for (const id of unique) {
    basketAddDocument(id, { openDrawer: false, silent: true });
  }
  if (openDrawer) openBasketDrawer();
  if (unique.length) showToast(`Đã ghim ${unique.length} item vào giỏ.`, 'success');
}

export function basketRemoveDocument(documentId) {
  const id = String(documentId || '').trim();
  if (!id) return;
  _loadBasket();
  basketState.items = (basketState.items || []).filter(i => i.document_id !== id);
  _saveBasket();
  renderBasket();
}

export function basketSetIncluded(documentId, included) {
  const id = String(documentId || '').trim();
  if (!id) return;
  _loadBasket();
  basketState.items = (basketState.items || []).map(i => (i.document_id === id ? { ...i, included: !!included } : i));
  _saveBasket();
  renderBasket();
}

export async function basketPreviewDocument(documentId) {
  const id = String(documentId || '').trim();
  if (!id) return;
  try {
    const r = await authFetch(`${API}/documents/${encodeURIComponent(id)}`);
    if (!r.ok) throw new Error(await readApiError(r));
    const data = await r.json();
    const doc = data && data.document ? data.document : null;
    if (!doc) throw new Error('No document.');

    const body = document.createElement('div');
    body.className = 'kp-modal-form-wrap';
    const wrap = document.createElement('div');
    wrap.className = 'kp-modal-form';

    const meta = document.createElement('div');
    meta.className = 'kp-modal-help';
    meta.textContent = `${String(doc.source || '')} · ~${Number(doc.token_estimate || 0)} tokens`;

    const content = document.createElement('textarea');
    content.className = 'time-input kp-modal-input';
    content.value = String(doc.content || '');
    content.style.minHeight = '360px';

    wrap.appendChild(meta);
    wrap.appendChild(content);
    body.appendChild(wrap);

    await kpOpenModal({
      title: String(doc.title || 'Preview'),
      subtitle: String(doc.url || ''),
      content: body,
      okText: 'Đóng',
      cancelText: '',
      onOk: () => true,
    });
  } catch (e) {
    showToast(e.message || 'Không thể preview tài liệu.', 'error');
  }
}

export function renderBasketInto({ listId, subId, tokenTextId, progressFillId, tokenHintId } = {}) {
  const list = document.getElementById(String(listId || ''));
  if (!list) return;

  const sub = document.getElementById(String(subId || ''));
  const tokenText = document.getElementById(String(tokenTextId || ''));
  const fill = document.getElementById(String(progressFillId || ''));
  const hint = document.getElementById(String(tokenHintId || ''));

  _loadBasket();
  const items = basketState.items || [];
  const used = _basketTokenUsed();
  const pct = Math.max(0, Math.min(100, (used / BASKET_TOKEN_LIMIT) * 100));
  const selectedCount = _basketIncludedIds().length;

  if (sub) sub.textContent = `${items.length} items · ${selectedCount} selected`;
  if (tokenText) tokenText.textContent = `${used.toLocaleString('vi-VN')} / ${BASKET_TOKEN_LIMIT.toLocaleString('vi-VN')} tokens`;
  if (fill) {
    fill.style.width = pct.toFixed(1) + '%';
    if (pct >= 90) fill.style.background = 'linear-gradient(90deg, var(--danger), var(--warn))';
    else if (pct >= 75) fill.style.background = 'linear-gradient(90deg, var(--warn), var(--accent2))';
    else fill.style.background = 'linear-gradient(90deg, var(--accent3), var(--accent))';
  }
  if (hint) {
    if (pct >= 90) {
      hint.style.display = '';
      hint.style.color = 'var(--danger)';
      hint.textContent = 'Giỏ đang quá đầy, AI có thể mất tập trung. Vui lòng bỏ bớt tài liệu phụ.';
    } else if (pct >= 75) {
      hint.style.display = '';
      hint.style.color = 'var(--warn)';
      hint.textContent = 'Giỏ khá đầy. Nên giữ lại các tài liệu “đinh” để tăng chất lượng đầu ra.';
    } else {
      hint.style.display = 'none';
      hint.textContent = '';
    }
  }

  if (!items.length) {
    list.innerHTML = `<div class="basket-empty">Chưa có item nào. Hãy bấm 📌 để ghim ngữ cảnh.</div>`;
    return;
  }

  list.innerHTML = items.map(it => {
    const badge = getBadgeClass(it.source);
    const title = escapeHtml(it.title || 'Untitled');
    const src = escapeHtml(it.source || 'doc');
    const tok = Number(it.token_estimate || 0) || 0;
    return `
      <div class="basket-item">
        <input class="basket-item-check" type="checkbox" ${it.included ? 'checked' : ''} onchange="basketSetIncluded('${escapeHtml(it.document_id)}', this.checked)">
        <div class="basket-item-body">
          <div class="basket-item-title" title="${title}">${title}</div>
          <div class="basket-item-meta">
            <span class="result-source-badge ${badge}">${src}</span>
            <span>~${tok.toLocaleString('vi-VN')} tok</span>
          </div>
        </div>
        <div class="basket-item-actions">
          <button onclick="basketPreviewDocument('${escapeHtml(it.document_id)}')" title="Preview">👁</button>
          <button onclick="basketRemoveDocument('${escapeHtml(it.document_id)}')" title="Remove">✕</button>
        </div>
      </div>
    `;
  }).join('');
}

export function renderBasket() {
  renderBasketInto({
    listId: 'basketList',
    subId: 'basketSub',
    tokenTextId: 'basketTokenText',
    progressFillId: 'basketProgressFill',
    tokenHintId: 'basketTokenHint',
  });
  renderBasketInto({
    listId: 'basketPageList',
    subId: 'basketPageSub',
    tokenTextId: 'basketPageTokenText',
    progressFillId: 'basketPageProgressFill',
    tokenHintId: 'basketPageTokenHint',
  });
  updateBasketBadges();
}

export function updateBasketBadges() {
  _loadBasket();
  const count = (basketState.items || []).length;
  const badge = document.getElementById('basketBadge');
  if (badge) {
    badge.textContent = String(count);
    badge.style.display = count ? '' : 'none';
  }
  const fab = document.getElementById('basketFab');
  if (fab) {
    fab.title = count ? `Giỏ ngữ cảnh (${count})` : 'Giỏ ngữ cảnh';
  }
}

export function loadBasketPage() {
  renderBasket();
  refreshBasketDetails();
}

export async function basketRunSkill(runSkillCallback) {
  _loadBasket();
  const ids = _basketIncludedIds();
  if (!ids.length) {
    showToast('Giỏ đang trống hoặc chưa chọn item nào.', 'info');
    return;
  }
  if (runSkillCallback) return runSkillCallback(ids);
}