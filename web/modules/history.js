// history.js — Quản lý lịch sử Chat
console.log('[History] Loading module...');
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

export async function loadHistoryPage() {
  const container = document.getElementById('historyContainer');
  if (!container) return;
  
  container.innerHTML = '<div class="drafts-loading">Đang tải lịch sử...</div>';

  try {
    const response = await authFetch(`${API}/history/sessions`);
    if (!response.ok) throw new Error('Failed to load history');
    const data = await response.json();
    renderHistoryList(data.sessions || []);
  } catch (e) {
    console.error('Error loading history:', e);
    container.innerHTML = `<div class="drafts-empty">Lỗi: ${escapeHtml(e.message)}</div>`;
  }
}

function renderHistoryList(sessions) {
  const container = document.getElementById('historyContainer');
  if (!container) return;

  if (!sessions || sessions.length === 0) {
    container.innerHTML = '<div class="drafts-empty">Bạn chưa có phiên chat nào. Hãy hỏi AI để bắt đầu!</div>';
    return;
  }

  let html = `<div class="history-grid" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;">`;
  
  sessions.forEach(session => {
    const date = new Date(session.updated_at).toLocaleString('vi-VN', { 
      day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit' 
    });
    html += `
      <div class="history-card" onclick="window.viewChatSession('${session.id}')" 
           style="background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:16px;cursor:pointer;transition:all 0.2s;">
        <h4 style="margin:0 0 8px;font-size:14px;color:var(--text);">${escapeHtml(session.title || 'Chat không tên')}</h4>
        <div style="font-size:11px;color:var(--text-muted)">🕒 ${date}</div>
      </div>
    `;
  });
  
  html += `</div>`;
  container.innerHTML = html;
}

window.viewChatSession = async function(sessionId) {
  const container = document.getElementById('historyContainer');
  if (!container) return;
  
  container.innerHTML = '<div class="drafts-loading">Đang tải chi tiết...</div>';
  
  try {
    const response = await authFetch(`${API}/history/sessions/${sessionId}`);
    if (!response.ok) throw new Error('Không thể tải phiên chat');
    const data = await response.json();
    
    let html = `
      <div style="margin-bottom: 20px;">
        <button class="secondary-btn mini" onclick="window.loadHistoryPage()">← Quay lại danh sách</button>
        <h3 style="margin:16px 0 8px;color:var(--text)">${escapeHtml(data.session.title)}</h3>
      </div>
      <div class="chat-thread" style="background:var(--bg2);border:1px solid var(--border);border-radius:16px;padding:20px;display:flex;flex-direction:column;gap:20px;">
    `;
    
    data.messages.forEach(m => {
      const isUser = m.role === 'user';
      const align = isUser ? 'flex-end' : 'flex-start';
      const bg = isUser ? 'var(--accent)' : 'var(--bg3)';
      const color = isUser ? '#fff' : 'var(--text)';
      
      let contentHtml = `<div style="white-space:pre-wrap;">${escapeHtml(m.content)}</div>`;
      
      html += `
        <div style="display:flex; flex-direction:column; align-items:${align};">
          <div style="max-width:85%;background:${bg};color:${color};padding:12px 16px;border-radius:12px;font-size:14px;line-height:1.6;">
            ${contentHtml}
          </div>
        </div>
      `;
    });
    
    html += `</div>`;
    container.innerHTML = html;
    
  } catch (e) {
    showToast(e.message, 'error');
    loadHistoryPage();
  }
}