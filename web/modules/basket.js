// basket.js
import { showToast, escapeHtml, kpConfirm, kpOpenModal } from '../utils/ui.js';
import { authFetch, API } from '../api/client.js';

let basketItems = [];

function loadBasket() {
  try {
    const s = localStorage.getItem('kpBasket');
    basketItems = s ? JSON.parse(s) : [];
  } catch (e) { basketItems = []; }
}

export function addToBasket(id, title = '') {
  if (!id) return;
  loadBasket();
  if (!basketItems.find(i => i.id === id)) {
    basketItems.push({ id, title });
    localStorage.setItem('kpBasket', JSON.stringify(basketItems));
    updateBasketBadges();
    showToast('Them vao gio thanh cong');
  }
}

export function removeFromBasket(id) {
  loadBasket();
  basketItems = basketItems.filter(i => i.id !== id);
  localStorage.setItem('kpBasket', JSON.stringify(basketItems));
  updateBasketBadges();
  renderBasket();
}

export function updateBasketBadges() {
  loadBasket();
  const b = document.getElementById('basketBadge');
  if (b) {
    b.textContent = basketItems.length;
    b.style.display = basketItems.length > 0 ? 'flex' : 'none';
  }
}

export function toggleBasketDrawer() {
  const d = document.getElementById('basketDrawer');
  const o = document.getElementById('basketOverlay');
  if (!d) return;
  const isHidden = (d.style.display === 'none' || !d.style.display);
  if (isHidden) {
    d.style.display = 'flex';
    if (o) o.style.display = 'block';
    renderBasket();
  } else {
    d.style.display = 'none';
    if (o) o.style.display = 'none';
  }
}

export function closeBasketDrawer() {
    const d = document.getElementById('basketDrawer');
    const o = document.getElementById('basketOverlay');
    if (d) d.style.display = 'none';
    if (o) o.style.display = 'none';
}

export function renderBasket() {
  loadBasket();
  [document.getElementById('basketList'), document.getElementById('basketPageList')].forEach(list => {
    if (list) {
      if (basketItems.length === 0) {
        list.innerHTML = '<div class="basket-empty">Gio trong. Hay bam ghim tai lieu.</div>';
      } else {
        list.innerHTML = basketItems.map(i => `
          <div class="basket-item">
            <div class="basket-item-info">
              <div class="basket-item-title" title="${escapeHtml(i.title || i.id)}">${escapeHtml(i.title || i.id)}</div>
            </div>
            <button class="secondary-btn mini" style="padding:4px 8px; font-size:12px; height:auto; min-width:unset" onclick="window.removeFromBasket('${i.id}')" title="Xóa khỏi giỏ">✕</button>
          </div>
        `).join('');
      }
    }
  });

  // Update Brain capacity
  const capText = ['basketTokenText', 'basketPageTokenText'];
  const capFill = ['basketProgressFill', 'basketPageProgressFill'];
  const used = basketItems.length * 2100;
  const total = 32000;
  const pct = Math.min(100, Math.round((used/total)*100));

  capText.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.textContent = `${used.toLocaleString()} / ${total.toLocaleString()}`;
  });
  capFill.forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.width = pct + '%';
  });

  updateBasketBadges();
}

export function loadBasketPage() { renderBasket(); }

export async function clearBasket() {
    const confirmed = await kpConfirm({
      title: '🗑 Xóa giỏ ngữ cảnh',
      message: 'Xóa toàn bộ giỏ ngữ cảnh?',
      okText: 'Xóa tất cả',
      cancelText: 'Huỷ',
      danger: true,
    });
    if (!confirmed) return;
    basketItems = [];
    localStorage.setItem('kpBasket', '[]');
    updateBasketBadges();
    renderBasket();
}

export function refreshBasketDetails() { renderBasket(); }

export async function basketRunSkill() {
    if (basketItems.length === 0) return showToast('Giỏ tài liệu trống. Hãy ghim tài liệu trước.', 'warning');

    const body = document.createElement('div');
    body.innerHTML = `
      <div style="margin-bottom: 12px;">
        <label style="display:block; margin-bottom:4px; font-weight:600; font-size:13px;">Chọn loại tài liệu (Skill)</label>
        <select id="skillTypeSelect" class="time-input" style="width:100%; box-sizing: border-box;">
          <option value="srs">📄 GPT-4: SRS (Software Requirements)</option>
          <option value="brd">📋 GPT-4: BRD (Business Requirements)</option>
          <option value="use_cases">📐 GPT-4: Use Cases</option>
          <option value="user_stories">🎯 GPT-5: User Stories</option>
          <option value="fe_spec">🖥️ GPT-6: FE Technical Spec</option>
          <option value="qa_test_spec">🧪 GPT-7: QA Test Spec</option>
          <option value="api_spec">🔌 GPT-3: API Spec</option>
        </select>
      </div>
      <div>
        <label style="display:block; margin-bottom:4px; font-weight:600; font-size:13px;">Yêu cầu thêm (Prompt cho AI)</label>
        <textarea id="skillInstructionInput" class="time-input" style="width:100%; min-height:80px; resize:vertical; box-sizing: border-box;" placeholder="Ví dụ: Tập trung vào luồng thanh toán VNPay..."></textarea>
      </div>
    `;

    kpOpenModal({
        title: '✨ Chạy AI Skill',
        content: body,
        okText: '🚀 Bắt đầu tạo',
        onOk: async () => {
            const docType = document.getElementById('skillTypeSelect').value;
            const goal = document.getElementById('skillInstructionInput').value.trim();
            const docIds = basketItems.map(i => i.id);

            showToast('Đang khởi tạo Agent... Vui lòng đợi.', 'info');
            try {
                const res = await authFetch(`${API}/docs/drafts/from-documents`, {
                    method: 'POST',
                    // Đồng bộ payload với file docs.py (doc_ids và goal)
                    body: JSON.stringify({ doc_type: docType, doc_ids: docIds, goal: goal })
                });
                if (!res.ok) { 
                    const err = await res.json().catch(()=>({})); 
                    throw new Error(err.detail || 'Lỗi khi chạy skill'); 
                }
                const data = await res.json();
                showToast('Tạo bản nháp thành công!', 'success');
                
                closeBasketDrawer();
                if (window.navigate) window.navigate('drafts');
                if (window.openDocDraftEditor && data.draft && data.draft.id) {
                    setTimeout(() => window.openDocDraftEditor(data.draft.id), 500);
                }
                return true;
            } catch (e) { 
                showToast(e.message, 'error');
                return false;
            }
        }
    });
}

loadBasket();
window.addEventListener('DOMContentLoaded', updateBasketBadges);
