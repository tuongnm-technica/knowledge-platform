// history.js — Quản lý lịch sử Chat
console.log('[History] Loading module...');
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';
import { formatAnswer, appendBubble } from './chat.js';

window.loadHistoryPage = loadHistoryPage;
let _allSessions = [];

export async function loadHistoryPage() {
  const container = document.getElementById('chatHistoryList');
  if (!container) return;
  
  container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">Đang tải...</div>';

  try {
    const response = await authFetch(`${API}/history/sessions`);
    if (!response.ok) throw new Error('Failed to load history');
    const data = await response.json();
    _allSessions = data.sessions || [];
    
    // Gắn event listener cho ô tìm kiếm (nếu chưa gắn)
    const searchInput = document.getElementById('chatHistorySearchInput');
    if (searchInput && !searchInput.dataset.bound) {
      searchInput.addEventListener('input', filterHistory);
      searchInput.dataset.bound = 'true';
    }
    
    filterHistory();
  } catch (e) {
    console.error('Error loading history:', e);
    container.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--danger); font-size: 13px;">Lỗi tải lịch sử</div>`;
  }
}

function filterHistory() {
  const query = (document.getElementById('chatHistorySearchInput')?.value || '').toLowerCase().trim();
  const filtered = query ? _allSessions.filter(s => (s.title || '').toLowerCase().includes(query)) : _allSessions;
  renderHistoryList(filtered);
}

function renderHistoryList(sessions) {
  const container = document.getElementById('chatHistoryList');
  if (!container) return;

  if (!sessions || sessions.length === 0) {
    const hasData = _allSessions && _allSessions.length > 0;
    container.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--text-dim); font-size: 13px;">${hasData ? 'Không tìm thấy kết quả.' : 'Chưa có lịch sử.'}</div>`;
    return;
  }

  let html = '';
  
  sessions.forEach(session => {
    const dateObj = new Date(session.updated_at);
    const isToday = new Date().toDateString() === dateObj.toDateString();
    const dateStr = isToday ? dateObj.toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit'}) : dateObj.toLocaleDateString('vi-VN', {day:'2-digit', month:'2-digit', year: 'numeric'});
    
    const isActive = window.currentSessionId === session.id;
    const activeStyles = isActive ? 'background: var(--bg3); border-color: var(--border-active); box-shadow: inset 0 0 0 1px rgba(37,99,235,0.1);' : 'border-color: transparent;';

    html += `
      <div onclick="window.viewChatSession('${session.id}')" 
           style="padding: 12px 14px; border-radius: 12px; cursor: pointer; transition: all 0.2s; border: 1px solid transparent; ${activeStyles}"
           onmouseover="if(!${isActive}) this.style.background='var(--bg2)'" onmouseout="if(!${isActive}) this.style.background='transparent'">
        <div style="font-size: 13.5px; font-weight: 500; color: ${isActive ? 'var(--accent)' : 'var(--text)'}; line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; margin-bottom: 6px;">${escapeHtml(session.title || 'Chat không tên')}</div>
        <div style="font-size: 11px; color: var(--text-dim);">${dateStr}</div>
      </div>
    `;
  });
  
  container.innerHTML = html;
}

window.viewChatSession = async function(sessionId) {
  try {
    const response = await authFetch(`${API}/history/sessions/${sessionId}`);
    if (!response.ok) throw new Error('Không thể tải phiên chat');
    const data = await response.json();
    
    // Chuyển dữ liệu sang màn hình Chat chính
    window.currentSessionId = sessionId;
    
    const chatMessages = document.getElementById('chatMessages');
    const emptyState = document.getElementById('emptyState');
    
    if (chatMessages) {
      // Xóa các tin nhắn cũ
      Array.from(chatMessages.querySelectorAll('.chat-message')).forEach(msg => msg.remove());
      if (emptyState) emptyState.style.display = 'none';
      
      // Render lại từng tin nhắn từ DB lên giao diện Chat AI
      data.messages.forEach(m => {
        const roleClass = m.role === 'assistant' ? 'ai' : 'user';
        
        if (roleClass === 'ai') {
          const msgData = { answer: m.content, sources: m.sources || [] };
          const answerHtml = formatAnswer(msgData);
          appendBubble('ai', answerHtml, msgData);
        } else {
          const userBubble = document.createElement('div');
          userBubble.textContent = m.content;
          appendBubble('user', userBubble);
        }
      });
      
      // Cuộn xuống cuối cùng
      setTimeout(() => {
        chatMessages.scrollTop = chatMessages.scrollHeight;
      }, 50);
    }
    
    // Tải lại list history ở background để làm mới trạng thái
    loadHistoryPage();
    
  } catch (e) {
    showToast(e.message, 'error');
    loadHistoryPage();
  }
}

// Khởi động: tải danh sách lịch sử khi file JS được load
setTimeout(() => {
  if (window.loadHistoryPage) window.loadHistoryPage();
}, 300);