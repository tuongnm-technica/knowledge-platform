import { API, authFetch } from './client';
import { ChatSession } from './models';
import { escapeHtml, formatDateTime, showToast } from './ui';
import { ChatModule } from './chat'; // Tùy chọn: nếu muốn tương tác trực tiếp

export class HistoryModule {
    public async loadHistoryPage(): Promise<void> {
        const list = document.getElementById('chatHistoryList');
        if (list) list.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">Đang tải...</div>';
        
        try {
            const res = await authFetch(`${API}/chat/history`);
            if (!res.ok) throw new Error('Không thể tải lịch sử');
            
            const data = await res.json();
            const sessions: ChatSession[] = Array.isArray(data) ? data : (data.sessions || []);
            this.renderHistoryList(sessions);
        } catch(e: any) {
            if (list) list.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--danger); font-size: 13px;">${escapeHtml(e.message)}</div>`;
        }
    }

    private renderHistoryList(sessions: ChatSession[]): void {
        const list = document.getElementById('chatHistoryList');
        if (!list) return;
        list.innerHTML = '';

        if (!sessions || sessions.length === 0) {
            list.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">Chưa có hội thoại nào</div>';
            return;
        }

        sessions.forEach(s => {
            const item = document.createElement('div');
            item.className = 'chat-history-item';
            item.style.cursor = 'pointer';
            item.style.padding = '12px';
            item.style.borderBottom = '1px solid var(--border)';
            
            item.innerHTML = `
                <div class="chat-history-title" style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">${escapeHtml(s.title || 'Hội thoại mới')}</div>
                <div class="chat-history-meta" style="font-size: 11px; color: var(--text-dim);">${formatDateTime(s.updated_at || s.created_at)}</div>
            `;
            
            item.addEventListener('click', () => {
                document.dispatchEvent(new CustomEvent('kp-switch-chat-session', { detail: s.id }));
                document.dispatchEvent(new CustomEvent('kp-navigate', { detail: 'chat' }));
            });
            list.appendChild(item);
        });
    }
}