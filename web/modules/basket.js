// Basket Module - Giỏ ngữ cảnh
import { showToast } from '../utils/ui.js';

let basketItems = [];

// Load basket from localStorage
function loadBasketFromStorage() {
  try {
    const stored = localStorage.getItem('kpBasket');
    basketItems = stored ? JSON.parse(stored) : [];
  } catch {
    basketItems = [];
  }
}

// Save basket to localStorage
function saveBasketToStorage() {
  localStorage.setItem('kpBasket', JSON.stringify(basketItems));
}

export function addToBasket(docId, docTitle = '') {
  const id = String(docId || '').trim();
  if (!id) return;
  
  if (!basketItems.find(item => item.id === id)) {
    basketItems.push({ id, title: docTitle });
    saveBasketToStorage();
    updateBasketBadges();
    showToast(`Đã thêm: ${docTitle || id}`, 'success');
  }
}

export function removeFromBasket(docId) {
  const id = String(docId || '').trim();
  basketItems = basketItems.filter(item => item.id !== id);
  saveBasketToStorage();
  updateBasketBadges();
  renderBasket();
}

export function clearBasket() {
  basketItems = [];
  saveBasketToStorage();
  updateBasketBadges();
  renderBasket();
}

export function getBasketItems() {
  return basketItems.map(item => item.id);
}

export function renderBasket() {
  loadBasketFromStorage();
  const container = document.getElementById('basketContainer');
  if (!container) return;
  
  container.innerHTML = '';
  if (basketItems.length === 0) {
    container.innerHTML = '<div class="basket-empty">Giỏ trống</div>';
    return;
  }

  const ul = document.createElement('ul');
  ul.className = 'basket-items';
  basketItems.forEach(item => {
    const li = document.createElement('li');
    li.className = 'basket-item';
    li.innerHTML = `
      <span class="basket-item-title">${escapeHtml(item.title || item.id)}</span>
      <button class="basket-item-remove" onclick="removeFromBasket('${item.id}')">✕</button>
    `;
    ul.appendChild(li);
  });
  
  const actions = document.createElement('div');
  actions.style.marginTop = '12px';
  actions.innerHTML = `
    <button class="primary-btn" onclick="basketRunSkill()" style="marginRight: 8px;">🚀 Chạy Skill</button>
    <button onclick="clearBasket()">Xóa tất cả</button>
  `;
  container.appendChild(ul);
  container.appendChild(actions);
}

export function updateBasketBadges() {
  loadBasketFromStorage();
  const badge = document.querySelector('[data-badge="basket"]');
  if (badge) {
    const count = basketItems.length;
    if (count > 0) {
      badge.textContent = count;
      badge.style.display = 'inline-block';
    } else {
      badge.style.display = 'none';
    }
  }
}

export function loadBasketPage() {
  renderBasket();
}

// ─── Skill Selector ────────────────────────────────────────────────────────

let _skillAgents = null; // cache

async function fetchSkillAgents() {
  if (_skillAgents) return _skillAgents;
  try {
    const token = localStorage.getItem('token') || sessionStorage.getItem('token') || '';
    const res = await fetch('/api/docs/skills', {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error('API error');
    const data = await res.json();
    _skillAgents = data.agents || [];
    return _skillAgents;
  } catch {
    return null;
  }
}

function openSkillModal(agents, onSelect) {
  // Remove existing modal if any
  document.getElementById('skillSelectorModal')?.remove();

  const modal = document.createElement('div');
  modal.id = 'skillSelectorModal';
  modal.className = 'skill-modal-overlay';
  modal.innerHTML = `
    <div class="skill-modal">
      <div class="skill-modal-header">
        <h3 class="skill-modal-title">🚀 Chọn Skill để chạy</h3>
        <button class="skill-modal-close" id="skillModalClose">✕</button>
      </div>
      <p class="skill-modal-subtitle">Chọn agent BA phù hợp với tài liệu bạn muốn tạo từ ${basketItems.length} tài liệu trong giỏ.</p>
      <div class="skill-agent-list" id="skillAgentList">
        ${agents.map(a => `
          <label class="skill-agent-item" data-doctype="${escapeHtml(a.doc_type)}">
            <input type="radio" name="skillAgent" value="${escapeHtml(a.doc_type)}" />
            <span class="skill-agent-content">
              <span class="skill-agent-label">${escapeHtml(a.label)}</span>
              <span class="skill-agent-desc">${escapeHtml(a.description)}</span>
            </span>
          </label>
        `).join('')}
      </div>
      <div class="skill-modal-goal">
        <label for="skillGoalInput" class="skill-goal-label">Mục tiêu / Context (tuỳ chọn)</label>
        <textarea id="skillGoalInput" class="skill-goal-textarea" rows="2"
          placeholder="VD: Phân tích yêu cầu module thanh toán, target user B2C, team 5 devs..."></textarea>
      </div>
      <div class="skill-modal-actions">
        <button class="primary-btn" id="skillRunBtn">🚀 Chạy</button>
        <button class="skill-cancel-btn" id="skillCancelBtn">Huỷ</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);

  // Default select first agent
  const firstRadio = modal.querySelector('input[type="radio"]');
  if (firstRadio) firstRadio.checked = true;

  modal.querySelector('#skillModalClose').onclick = () => modal.remove();
  modal.querySelector('#skillCancelBtn').onclick = () => modal.remove();
  modal.addEventListener('click', e => { if (e.target === modal) modal.remove(); });

  modal.querySelector('#skillRunBtn').onclick = () => {
    const selected = modal.querySelector('input[name="skillAgent"]:checked');
    if (!selected) { showToast('Vui lòng chọn một agent', 'info'); return; }
    const goal = (modal.querySelector('#skillGoalInput')?.value || '').trim();
    modal.remove();
    onSelect(selected.value, goal);
  };
}

export async function basketRunSkill(generateDocFromDocuments) {
  loadBasketFromStorage();
  if (basketItems.length === 0) {
    showToast('Giỏ trống, vui lòng thêm tài liệu', 'info');
    return;
  }

  const agents = await fetchSkillAgents();

  if (!agents || agents.length === 0) {
    // Fallback: no agents metadata, run with default srs
    if (typeof generateDocFromDocuments === 'function') {
      await generateDocFromDocuments(basketItems.map(item => item.id));
    }
    return;
  }

  openSkillModal(agents, async (docType, goal) => {
    if (typeof generateDocFromDocuments === 'function') {
      await generateDocFromDocuments(basketItems.map(item => item.id), docType, goal);
    }
  });
}

function escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

// Initialize basket from storage on load
loadBasketFromStorage();
