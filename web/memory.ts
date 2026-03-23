import { API, authFetch } from './client';
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
            const data = await res.json() as { memory: Record<string, any[]> };
            this.renderMemory(data.memory || {});
        } catch(err) {
            const error = err as Error;
            if (container) container.innerHTML = `<div class="search-empty">Chưa có dữ liệu API (/api/memory): ${escapeHtml(error.message)}</div>`;
        }
    }

    private renderMemory(grouped: Record<string, any[]>): void {
        const container = document.getElementById('memoryContent');
        if (!container) return;
        
        const types = Object.keys(grouped);
        if (types.length === 0) {
            container.innerHTML = '<div class="search-empty">Chưa có thông tin nào được ghi nhớ. AI sẽ tự động học hỏi khi sinh tài liệu (Drafts).</div>';
            return;
        }

        let html = '<div style="display:flex; flex-direction:column; gap:24px;">';
        
        for (const type of types) {
            const items = grouped[type];
            html += `
                <div class="memory-group">
                    <h3 style="margin-bottom: 12px; font-size: 14px; text-transform: uppercase; color: var(--text-dim); border-bottom: 1px solid var(--border); padding-bottom: 8px;">
                        ${escapeHtml(type)} (${items.length})
                    </h3>
                    <div style="display:grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap:12px;">
                        ${items.map(item => `
                            <div style="padding: 14px; border: 1px solid var(--border); border-radius: 12px; background: var(--bg2); transition: all 0.2s ease;">
                                <div style="font-weight: 700; margin-bottom: 6px; color: var(--accent); font-size: 13px;">${escapeHtml(item.key)}</div>
                                <div style="font-size: 13px; color: var(--text); line-height: 1.5;">${escapeHtml(item.content || item.value || '')}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        
        html += '</div>';
        container.innerHTML = html;
    }
}