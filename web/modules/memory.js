// memory.js – Project Memory Manager
console.log('[Memory] Loading module...');
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml, kpConfirm } from '../utils/ui.js';

const TYPE_CONFIG = {
  actor:    { icon: '👤', label: 'Actors (Vai trò)',     color: 'var(--accent)' },
  glossary: { icon: '📖', label: 'Glossary (Thuật ngữ)', color: 'var(--success)' },
  rule:     { icon: '⚖️', label: 'Rules (Quy tắc)',      color: 'var(--warn)' },
};

export async function loadMemoryPage() {
  const el = document.getElementById('memoryContent');
  if (!el) return;
  el.innerHTML = '<div class="drafts-loading">Đang tải trí nhớ dự án...</div>';

  try {
    const res = await authFetch(`${API}/docs/memory`);
    if (!res.ok) throw new Error('Không tải được Project Memory');
    const data = await res.json();
    renderMemory(data.memory || {});
  } catch (e) {
    console.error('[Memory] load error', e);
    el.innerHTML = `<div class="drafts-empty">Lỗi: ${escapeHtml(e.message)}</div>`;
  }
}

function renderMemory(grouped) {
  const el = document.getElementById('memoryContent');
  if (!el) return;

  const types = Object.keys(grouped);
  if (types.length === 0) {
    el.innerHTML = `
      <div class="drafts-empty">
        <p>Chưa có trí nhớ dự án nào.</p>
        <p style="font-size:12px;color:var(--text-dim);margin-top:8px">
          Các <strong>Actors</strong>, <strong>Thuật ngữ</strong> và <strong>Quy tắc</strong>
          sẽ được AI tự động thu thập khi bạn sinh tài liệu (SRS, Use Cases...).
        </p>
      </div>`;
    return;
  }

  const order = ['actor', 'glossary', 'rule', ...types.filter(t => !['actor','glossary','rule'].includes(t))];
  const container = document.createElement('div');
  container.style.cssText = 'display:flex;flex-direction:column;gap:24px';

  for (const mtype of order) {
    const items = grouped[mtype];
    if (!items || items.length === 0) continue;

    const cfg = TYPE_CONFIG[mtype] || { icon: '🏷️', label: mtype.toUpperCase(), color: 'var(--text-muted)' };

    const section = document.createElement('div');
    section.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)">
        <span style="font-size:18px">${cfg.icon}</span>
        <h3 style="margin:0;font-size:14px;font-weight:700;color:${cfg.color}">${escapeHtml(cfg.label)}</h3>
        <span style="font-size:11px;padding:2px 8px;border-radius:12px;background:color-mix(in srgb,${cfg.color} 15%,transparent);color:${cfg.color}">${items.length}</span>
      </div>
      <div class="memory-grid" id="memory-grid-${mtype}"></div>
    `;

    const grid = section.querySelector('.memory-grid');
    grid.style.cssText = 'display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px';

    for (const item of items) {
      const card = document.createElement('div');
      card.id = `mem-card-${item.id}`;
      card.style.cssText = `
        background:var(--bg2);border:1px solid var(--border);border-radius:var(--radius);
        padding:12px 14px;display:flex;flex-direction:column;gap:6px;
        transition:border-color .15s;
      `;
      card.onmouseenter = () => card.style.borderColor = cfg.color;
      card.onmouseleave = () => card.style.borderColor = 'var(--border)';
      card.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px">
          <span style="font-size:13px;font-weight:700;color:var(--text);word-break:break-word">${escapeHtml(item.key)}</span>
          <button class="secondary-btn mini" style="flex-shrink:0;padding:3px 7px;font-size:11px;color:var(--danger);border-color:var(--danger)"
            onclick="window.deleteMemory('${escapeHtml(item.id)}','${escapeHtml(item.key)}')" title="Xoá mục này">
            🗑
          </button>
        </div>
        <p style="margin:0;font-size:12px;color:var(--text-muted);line-height:1.5;word-break:break-word">${escapeHtml(item.content || '')}</p>
        <span style="font-size:10px;color:var(--text-dim)">Cập nhật: ${formatMemDate(item.updated_at)}</span>
      `;
      grid.appendChild(card);
    }

    container.appendChild(section);
  }

  el.innerHTML = '';
  el.appendChild(container);
}

window.deleteMemory = async function (memoryId, key) {
  const confirmed = await kpConfirm({
    title: '🗑 Xoá trí nhớ',
    message: `Xoá thuật ngữ/vai trò "<strong>${escapeHtml(key)}</strong>"?<br><small>AI sẽ không còn nhớ mục này trong các tài liệu tiếp theo.</small>`,
    okText: 'Xoá',
    cancelText: 'Huỷ',
    danger: true,
  });
  if (!confirmed) return;

  try {
    const res = await authFetch(`${API}/docs/memory/${memoryId}`, { method: 'DELETE' });
    if (!res.ok) { const e = await res.json(); throw new Error(e.detail || 'Xoá thất bại'); }
    const card = document.getElementById(`mem-card-${memoryId}`);
    if (card) {
      card.style.transition = 'opacity .25s, transform .25s';
      card.style.opacity = '0';
      card.style.transform = 'scale(0.95)';
      setTimeout(() => card.remove(), 250);
    }
    showToast(`Đã xoá "${key}"`, 'success');
  } catch (e) {
    showToast(e.message, 'error');
  }
};

function formatMemDate(d) {
  if (!d) return '—';
  try { return new Date(d).toLocaleString('vi-VN', { day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' }); }
  catch { return d; }
}
