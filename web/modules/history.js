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
    
    // Chuyển dữ liệu sang màn hình Chat chính
    window.currentSessionId = sessionId;
    
    const chatMessages = document.getElementById('chatMessages');
    const emptyState = document.getElementById('emptyState');
    const newChatBtn = document.getElementById('newChatBtn');
    
    if (chatMessages) {
      // Xóa các tin nhắn cũ
      Array.from(chatMessages.querySelectorAll('.chat-message')).forEach(msg => msg.remove());
      if (emptyState) emptyState.style.display = 'none';
      if (newChatBtn) newChatBtn.style.display = 'inline-block';
      
      // Render lại từng tin nhắn từ DB lên giao diện Chat AI
      data.messages.forEach(m => {
        const roleClass = m.role === 'assistant' ? 'ai' : 'user';
        const wrap = document.createElement('div');
        wrap.className = `chat-message chat-message-${roleClass}`;
        const bubble = document.createElement('div');
        bubble.className = `chat-bubble chat-bubble-${roleClass}`;
        
        if (roleClass === 'ai' && typeof marked !== 'undefined') {
          bubble.innerHTML = marked.parse(m.content || '');
        } else {
          bubble.textContent = m.content || '';
        }
        wrap.appendChild(bubble);
        chatMessages.appendChild(wrap);
      });
      
      // Cuộn xuống cuối cùng
      setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }, 50);
    }
    
    // Tự động chuyển tab sang trang Chat
    if (window.navigate) {
      window.navigate('chat');
    }
    
    // Tải lại list history ở background để làm mới trạng thái
    loadHistoryPage();
    
  } catch (e) {
    showToast(e.message, 'error');
    loadHistoryPage();
  }
}