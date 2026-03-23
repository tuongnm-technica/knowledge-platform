import { API, authFetch } from './client';
import { PromptSkill } from './models';
import { escapeHtml, showToast, kpOpenModal, _kpBuildModalField, kpConfirm } from './ui';
import { renderMarkdown } from './format';

export class PromptsModule {
    public async init(): Promise<void> {
        await this.loadPromptsPage();
    }

    public async loadPromptsPage(): Promise<void> {
        const container = document.getElementById('page-prompts');
        if (container) container.innerHTML = '<div style="padding:40px; text-align:center;">Đang tải danh sách Skill Prompts...</div>';

        try {
            const res = await authFetch(`${API}/prompts`);
            if (!res.ok) throw new Error('Không thể tải prompts');
            const data = await res.json() as { prompts: PromptSkill[] };
            const prompts: PromptSkill[] = data.prompts || [];
            this.renderPrompts(prompts);
        } catch(err) {
            const error = err as Error;
            if (container) container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--danger)">Lỗi tải Skills API: ${escapeHtml(error.message)}</div>`;
        }
    }

    private renderPrompts(prompts: PromptSkill[]): void {
        const container = document.getElementById('page-prompts');
        if (!container) return;
        
        container.innerHTML = `
        <div class="connectors-content">
            <div class="page-intro">
                <div>
                    <div class="intro-kicker">AI Skills</div>
                    <div class="intro-title">Skill Prompts Library</div>
                    <div class="intro-sub">Quản lý các mẫu AI Agents dùng cho việc phân tích và tạo tài liệu (chọn trong Giỏ ngữ cảnh).</div>
                </div>
            </div>
            <div id="skillsGroupsContainer" style="padding: 0 20px;"></div>
        </div>`;

        const groupsContainer = document.getElementById('skillsGroupsContainer');
        if (!groupsContainer) return;

        if (!prompts || prompts.length === 0) {
            groupsContainer.innerHTML = '<div class="search-empty">Chưa cấu hình skill prompt nào trên backend.</div>';
            return;
        }

        // 1. Group prompts
        const groups: { [key: string]: PromptSkill[] } = {};
        prompts.forEach(p => {
            const g = (p as any).group || 'Other';
            if (!groups[g]) groups[g] = [];
            groups[g].push(p);
        });

        // 2. Sort group names (GPT-1, GPT-2, ...)
        const sortedGroupNames = Object.keys(groups).sort((a, b) => {
            if (a.includes('GPT-') && b.includes('GPT-')) {
                const numA = parseInt(a.split('GPT-')[1]);
                const numB = parseInt(b.split('GPT-')[1]);
                return numA - numB;
            }
            return a.localeCompare(b);
        });

        // 3. Render each group
        sortedGroupNames.forEach(gname => {
            const groupSection = document.createElement('div');
            groupSection.style.marginBottom = '40px';
            groupSection.innerHTML = `
                <div class="section-header" style="margin-bottom:16px; border-bottom: 2px solid var(--border); padding-bottom:8px">
                    <div class="section-title" style="font-size:16px; color:var(--accent)">${escapeHtml(gname)}</div>
                </div>
                <div class="connectors-grid connectors-grid-rich"></div>
            `;
            
            const grid = groupSection.querySelector('.connectors-grid')!;
            const groupPrompts = groups[gname].sort((a, b) => (a.label || "").localeCompare(b.label || ""));

            groupPrompts.forEach(p => {
                const type = p.doc_type || p.type || 'System';
                const label = p.label || p.name || 'Untitled Agent';
                const desc = p.description || 'Hỗ trợ viết tự động tài liệu SDLC';
                
                const card = document.createElement('div');
                card.className = 'connector-card-rich';
                card.style.cursor = 'pointer';
                card.innerHTML = `
                    <div style="padding:20px">
                        <div style="font-weight:bold; font-size:15px; margin-bottom:8px; line-height:1.4">${escapeHtml(label)}</div>
                        <div class="markdown-body" style="font-size:12.5px; color:var(--text-dim); margin-bottom:16px; min-height:40px; line-height:1.5">${renderMarkdown(desc)}</div>
                        <div style="display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border); padding-top:12px">
                            <div style="font-size:10px; font-weight:700; color:var(--text-muted); background:var(--bg3); padding:3px 8px; border-radius:4px; text-transform:uppercase">${escapeHtml(type)}</div>
                            <div class="connector-actions-row" style="margin-top:0; border:none; padding:0; gap:8px">
                                <button class="secondary-btn mini" data-action="edit" data-type="${escapeHtml(type)}" title="Chỉnh sửa instructions">✏️</button>
                                <button class="secondary-btn mini" data-action="reset" data-type="${escapeHtml(type)}" title="Khôi phục mặc định">🔄</button>
                            </div>
                        </div>
                    </div>
                `;
                
                card.addEventListener('click', (e) => {
                    const btn = (e.target as HTMLElement).closest('button');
                    const action = btn?.getAttribute('data-action');
                    if (action === 'reset') {
                        this.resetPrompt(type);
                    } else if (action === 'edit') {
                        this.openEditModal(type);
                    } else {
                        // Click on card body edits by default
                        this.openEditModal(type);
                    }
                });
                
                grid.appendChild(card);
            });
            
            groupsContainer.appendChild(groupSection);
        });
    }

    private async openEditModal(docType: string): Promise<void> {
        showToast('Đang tải thông tin prompt...', 'info');
        try {
            const res = await authFetch(`${API}/prompts/${docType}`);
            if (!res.ok) throw new Error('Không tải được chi tiết prompt');
            const data = await res.json() as PromptSkill & { default_prompt?: string };

            const body = document.createElement('div');
            body.style.display = 'flex';
            body.style.flexDirection = 'row';
            body.style.gap = '20px';
            body.style.alignItems = 'stretch';
            body.style.minHeight = '500px';

            const leftPanel = document.createElement('div');
            leftPanel.style.flex = '1'; // Balanced 50-50 ratio
            leftPanel.style.display = 'flex';
            leftPanel.style.flexDirection = 'column';
            leftPanel.style.gap = '8px';

            const rightPanel = document.createElement('div');
            rightPanel.style.flex = '1'; // Balanced 50-50 ratio
            rightPanel.style.display = 'flex';
            rightPanel.style.flexDirection = 'column';
            rightPanel.style.gap = '8px';

            const { wrap: areaWrap, input: areaInput } = _kpBuildModalField({
                id: 'promptContent', label: 'System Instructions (Editor)', type: 'textarea', 
                value: data.system_prompt || data.template || '', 
                placeholder: 'Enter the AI instructions here...'
            });
            const ta = areaInput as HTMLTextAreaElement;
            ta.style.height = '520px';
            ta.style.fontFamily = "'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace";
            ta.style.fontSize = '12.5px';
            ta.style.lineHeight = '1.7';
            ta.style.padding = '16px';
            ta.style.border = '1px solid var(--border)';
            ta.style.borderRadius = '10px';
            ta.style.background = 'var(--bg2)';
            ta.style.color = 'var(--text)';
            ta.style.outline = 'none';
            ta.style.resize = 'none';
            ta.style.boxShadow = 'inset 0 2px 4px rgba(0,0,0,0.1)';

            const previewLabel = document.createElement('label');
            previewLabel.className = 'kp-modal-label';
            previewLabel.textContent = 'Live Preview (Rendered)';
            
            const previewBox = document.createElement('div');
            previewBox.className = 'markdown-body premium-scrollbar';
            previewBox.style.padding = '16px';
            previewBox.style.background = 'var(--bg3)';
            previewBox.style.border = '1px solid var(--border)';
            previewBox.style.borderRadius = '10px';
            previewBox.style.flex = '1';
            previewBox.style.fontSize = '13px';
            previewBox.style.overflowY = 'auto';
            previewBox.style.boxSizing = 'border-box';
            previewBox.style.height = '540px'; 
            previewBox.innerHTML = renderMarkdown(ta.value);

            ta.addEventListener('input', () => {
                previewBox.innerHTML = renderMarkdown(ta.value);
            });
            
            leftPanel.appendChild(areaWrap);
            rightPanel.appendChild(previewLabel);
            rightPanel.appendChild(previewBox);
            
            body.appendChild(leftPanel);
            body.appendChild(rightPanel);

            await kpOpenModal({
                title: `✏️ Chỉnh sửa Skill: ${data.label || docType}`,
                subtitle: 'Thay đổi các hướng dẫn (instructions) mà AI sử dụng khi thực hiện skill này.',
                content: body,
                modalClass: 'kp-modal-lg',
                contentStyles: { maxWidth: '1200px', width: '95vw' }, // Ultra-wide modal for IDE feel
                okText: 'Cập nhật Prompt',
                onOk: async () => {
                    const content = ta.value.trim();
                    if (!content) return { error: 'Nội dung prompt không được để trống' };

                    try {
                        const upd = await authFetch(`${API}/prompts/${docType}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ system_prompt: content })
                        });
                        if (!upd.ok) throw new Error('Cập nhật thất bại');
                        showToast('Đã cập nhật prompt thành công', 'success');
                        return true;
                    } catch (e) {
                        return { error: (e as Error).message };
                    }
                }
            });
        } catch (e) {
            showToast((e as Error).message, 'error');
        }
    }

    private async resetPrompt(docType: string): Promise<void> {
        const confirmed = await kpConfirm({
            title: 'Khôi phục mặc định',
            message: `Bạn có chắc muốn khôi phục prompt mang tên "${docType}" về giá trị mặc định của hệ thống?`,
            okText: 'Khôi phục ngay'
        });
        if (!confirmed) return;

        try {
            const res = await authFetch(`${API}/prompts/${docType}/reset`, { method: 'POST' });
            if (!res.ok) throw new Error('Reset thất bại');
            showToast('Đã khôi phục prompt mặc định', 'success');
            this.loadPromptsPage();
        } catch (e) {
            showToast((e as Error).message, 'error');
        }
    }
}