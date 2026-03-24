import { API, authFetch } from './client';
import { ChatSession } from './models';
import { escapeHtml, formatDateTime } from './ui';

export class HistoryModule {
    constructor() {
        document.addEventListener('kp-refresh-history', () => {
            console.log('HistoryModule: Refreshing history list...');
            this.loadHistoryPage('chatHistoryList');
        });
    }

    public async loadHistoryPage(targetId: string = 'chatHistoryList'): Promise<void> {
        const list = document.getElementById(targetId);
        if (list) list.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-muted); font-size: 13px;">Đang tải...</div>';
        
        try {
            const res = await authFetch(`${API}/history/sessions`);
            if (!res.ok) throw new Error('Không thể tải lịch sử');
            
            const data = await res.json() as ChatSession[] | { sessions: ChatSession[] };
            const sessions: ChatSession[] = Array.isArray(data) ? data : (data.sessions || []);
            this.renderHistoryList(sessions, targetId);
        } catch(err) {
            const error = err as Error;
            if (list) list.innerHTML = `<div style="padding: 20px; text-align: center; color: var(--danger); font-size: 13px;">${escapeHtml(error.message)}</div>`;
        }
    }

    private renderHistoryList(sessions: ChatSession[], targetId: string = 'chatHistoryList'): void {
        const list = document.getElementById(targetId);
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
            
            const timestamp = s.updated_at || s.created_at || new Date().toISOString();
            
            item.innerHTML = `
                <div class="chat-history-title" style="font-weight: 600; margin-bottom: 4px; font-size: 14px;">${escapeHtml(s.title || 'Hội thoại mới')}</div>
                <div class="chat-history-meta" style="font-size: 11px; color: var(--text-dim);">${formatDateTime(timestamp)}</div>
            `;
            
            item.addEventListener('click', () => {
                document.dispatchEvent(new CustomEvent('kp-switch-chat-session', { detail: s.id }));
                document.dispatchEvent(new CustomEvent('kp-navigate', { detail: 'chat' }));
            });
            list.appendChild(item);
        });
    }
}