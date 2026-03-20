import { API, authFetch } from './client';
import { PromptSkill } from './models';
import { escapeHtml } from './ui';

export class PromptsModule {
    public async loadPromptsPage(): Promise<void> {
        const container = document.getElementById('page-prompts');
        if (container) container.innerHTML = '<div style="padding:40px; text-align:center;">Đang tải danh sách Skill Prompts...</div>';

        try {
            const res = await authFetch(`${API}/prompts`);
            if (!res.ok) throw new Error('Không thể tải prompts');
            const data = await res.json() as PromptSkill[] | { agents: PromptSkill[] };
            const prompts: PromptSkill[] = Array.isArray(data) ? data : (data.agents || []);
            this.renderPrompts(prompts);
        } catch(err) {
            const error = err as Error;
            if (container) container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--danger)">Lỗi tải Skills API: ${escapeHtml(error.message)}</div>`;
        }
    }

    private renderPrompts(prompts: PromptSkill[]): void {
        const container = document.getElementById('page-prompts');
        if (!container) return;
        
        let html = `
        <div class="connectors-content">
            <div class="page-intro">
                <div>
                    <div class="intro-kicker">AI Skills</div>
                    <div class="intro-title">Skill Prompts Library</div>
                    <div class="intro-sub">Quản lý các mẫu AI Agents dùng cho việc phân tích và tạo tài liệu (chọn trong Giỏ ngữ cảnh).</div>
                </div>
            </div>
            <div class="connectors-grid" style="padding: 0 20px;">
        `;

        if (!prompts || prompts.length === 0) {
            html += '<div class="search-empty" style="grid-column:1/-1;">Chưa cấu hình skill prompt nào trên backend.</div>';
        } else {
            prompts.forEach(p => {
                const type = p.doc_type || p.type || 'System';
                const label = p.label || p.name || 'Untitled Agent';
                const desc = p.description || 'Hỗ trợ viết tự động tài liệu SDLC';
                html += `<div class="connector-card"><div style="font-weight:bold; font-size:16px; margin-bottom:8px;">${escapeHtml(label)}</div><div style="font-size:13px; color:var(--text-dim); margin-bottom:16px;">${escapeHtml(desc)}</div><div style="font-size:11px; padding:4px 8px; background:var(--bg3); border-radius:4px; display:inline-block;">Skill: ${escapeHtml(type)}</div></div>`;
            });
        }
        container.innerHTML = html + '</div></div>';
    }
}