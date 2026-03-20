import { API, authFetch } from './client';
import { MemoryItem } from './models';
import { escapeHtml } from './ui';

export class MemoryModule {
    constructor() {
        this.initEvents();
    }
    
    private initEvents() {
        document.getElementById('refreshMemoryBtn')?.addEventListener('click', () => this.loadMemoryPage());
    }

    public async loadMemoryPage(): Promise<void> {
        const container = document.getElementById('memoryContent');
        if (container) container.innerHTML = '<div class="loading-state">Đang tải Project Memory...</div>';

        try {
            const res = await authFetch(`${API}/memory`);
            if (!res.ok) throw new Error('Không thể tải memory');
            const data = await res.json() as MemoryItem[] | { items: MemoryItem[] };
            const items: MemoryItem[] = Array.isArray(data) ? data : (data.items || []);
            this.renderMemory(items);
        } catch(err) {
            const error = err as Error;
            if (container) container.innerHTML = `<div class="search-empty">Chưa có dữ liệu API (/api/memory): ${escapeHtml(error.message)}</div>`;
        }
    }

    private renderMemory(items: MemoryItem[]): void {
        const container = document.getElementById('memoryContent');
        if (!container) return;
        if (!items || items.length === 0) {
            container.innerHTML = '<div class="search-empty">Chưa có thông tin nào được ghi nhớ. AI sẽ tự động học hỏi khi sinh tài liệu (Drafts).</div>';
            return;
        }
        let html = '<div style="display:flex; flex-direction:column; gap:16px;">';
        items.forEach(item => {
            html += `
                <div style="padding: 16px; border: 1px solid var(--border); border-radius: 8px; background: var(--bg2);">
                    <div style="font-weight: bold; margin-bottom: 8px; color: var(--accent); text-transform: uppercase;">${escapeHtml(item.type)}: ${escapeHtml(item.key)}</div>
                    <div style="font-size: 14px; color: var(--text);">${escapeHtml(item.value)}</div>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    }
}