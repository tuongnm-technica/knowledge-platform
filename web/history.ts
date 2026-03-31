import { API, authFetch } from './client';
import { ChatSession } from './models';
import { escapeHtml, formatDateTime, kpConfirm, kpPrompt, showToast } from './ui';

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
            item.setAttribute('data-id', s.id);
            item.style.position = 'relative';
            item.style.cursor = 'pointer';
            item.style.padding = '12px';
            item.style.borderBottom = '1px solid var(--border)';
            item.style.transition = 'background-color 0.2s';
            
            const timestamp = s.updated_at || s.created_at || new Date().toISOString();
            
            item.innerHTML = `
                <div class="chat-history-content" style="padding-right: 60px;">
                    <div class="chat-history-title" style="font-weight: 600; margin-bottom: 4px; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(s.title || 'Hội thoại mới')}</div>
                    <div class="chat-history-meta" style="font-size: 11px; color: var(--text-dim);">${formatDateTime(timestamp)}</div>
                </div>
                <div class="chat-history-actions" style="position: absolute; right: 8px; top: 50%; transform: translateY(-50%); display: none; gap: 8px; background: inherit; padding-left: 8px;">
                    <button class="action-btn rename-btn" title="Đổi tên" style="background: none; border: none; cursor: pointer; color: var(--text-muted); font-size: 14px; padding: 4px;">✏️</button>
                    <button class="action-btn delete-btn" title="Xóa" style="background: none; border: none; cursor: pointer; color: var(--danger); font-size: 14px; padding: 4px;">🗑️</button>
                </div>
            `;
            
            item.addEventListener('mouseenter', () => {
                const actions = item.querySelector('.chat-history-actions') as HTMLElement;
                if (actions) actions.style.display = 'flex';
                item.style.backgroundColor = 'var(--bg-hover)';
            });

            item.addEventListener('mouseleave', () => {
                const actions = item.querySelector('.chat-history-actions') as HTMLElement;
                if (actions) actions.style.display = 'none';
                item.style.backgroundColor = 'transparent';
            });

            // Click to switch session
            item.addEventListener('click', (e) => {
                const target = e.target as HTMLElement;
                if (target.closest('.action-btn')) return; // Ignore if clicking action buttons
                
                document.dispatchEvent(new CustomEvent('kp-switch-chat-session', { detail: s.id }));
                document.dispatchEvent(new CustomEvent('kp-navigate', { detail: 'chat' }));
            });

            // Rename logic
            const renameBtn = item.querySelector('.rename-btn');
            renameBtn?.addEventListener('click', async (e: Event) => {
                e.stopPropagation();
                const newTitle = await kpPrompt({
                    title: 'Đổi tên hội thoại',
                    message: 'Nhập tên mới cho phiên chat này:',
                    defaultValue: s.title || '',
                    placeholder: 'Ví dụ: Thiết kế hệ thống RAG'
                });

                if (newTitle && newTitle.trim() && newTitle !== s.title) {
                    try {
                        const res = await authFetch(`${API}/history/sessions/${s.id}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ title: newTitle.trim() })
                        });
                        if (res.ok) {
                            showToast('Đã đổi tên hội thoại thành công');
                            this.loadHistoryPage(targetId);
                        } else {
                            showToast('Không thể đổi tên hội thoại', 'error');
                        }
                    } catch (err) {
                        showToast('Lỗi khi kết nối máy chủ', 'error');
                    }
                }
            });
 
            // Delete logic
            const deleteBtn = item.querySelector('.delete-btn');
            deleteBtn?.addEventListener('click', async (e) => {
                e.stopPropagation();
                const confirmed = await kpConfirm({
                    title: 'Xóa hội thoại',
                    message: 'Bạn có chắc chắn muốn xóa vĩnh viễn hội thoại này không?',
                    okText: 'Xóa ngay',
                    danger: true
                });

                if (confirmed) {
                    try {
                        const res = await authFetch(`${API}/history/sessions/${s.id}`, {
                            method: 'DELETE'
                        });
                        if (res.ok) {
                            showToast('Đã xóa hội thoại');
                            this.loadHistoryPage(targetId);
                        } else {
                            showToast('Không thể xóa hội thoại', 'error');
                        }
                    } catch (err) {
                        showToast('Lỗi khi kết nối máy chủ', 'error');
                    }
                }
            });

            list.appendChild(item);
        });
    }
}