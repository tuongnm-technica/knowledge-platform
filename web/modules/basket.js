// basket.js
import { showToast, escapeHtml, kpConfirm } from '../utils/ui.js';

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
            <div style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(i.title || i.id)}</div>
            <button class="basket-item-remove" onclick="window.removeFromBasket('${i.id}')" title="Xoa">✕</button>
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
    if (basketItems.length === 0) return showToast('Gio trong');
    showToast('Chay skill dang duoc phat trien (integrated with app.js callback)');
}

loadBasket();
window.addEventListener('DOMContentLoaded', updateBasketBadges);
