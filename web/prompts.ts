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
        if (container) container.innerHTML = `<div style="padding:40px; text-align:center;">${(window as any).$t('prompts.loading')}</div>`;

        try {
            const res = await authFetch(`${API}/prompts`);
            if (!res.ok) throw new Error((window as any).$t('prompts.err_load_list'));
            const data = await res.json() as { prompts: PromptSkill[] };
            const prompts: PromptSkill[] = data.prompts || [];
            this.renderPrompts(prompts);
        } catch(err) {
            const error = err as Error;
            if (container) container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--danger)">${(window as any).$t('prompts.err_load_api')} ${escapeHtml(error.message)}</div>`;
        }
    }

    private renderPrompts(prompts: PromptSkill[]): void {
        const container = document.getElementById('page-prompts');
        if (!container) return;
        
        container.innerHTML = `
        <div class="connectors-content">
            <div class="page-intro">
                <div>
                    <div class="intro-kicker">${(window as any).$t('prompts.intro_kicker')}</div>
                    <div class="intro-title">${(window as any).$t('prompts.intro_title')}</div>
                    <div class="intro-sub">${(window as any).$t('prompts.intro_sub')}</div>
                </div>
            </div>
            <div id="skillsGroupsContainer" style="padding: 0 20px;"></div>
        </div>`;

        const groupsContainer = document.getElementById('skillsGroupsContainer');
        if (!groupsContainer) return;

        if (!prompts || prompts.length === 0) {
            groupsContainer.innerHTML = `<div class="search-empty">${(window as any).$t('prompts.empty_hint')}</div>`;
            return;
        }

        // 1. Group prompts
        const groups: { [key: string]: PromptSkill[] } = {};
        prompts.forEach(p => {
            const g = (p as any).group || (window as any).$t('prompts.fallback_group');
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
                const label = p.label || p.name || (window as any).$t('prompts.fallback_label');
                const desc = p.description || (window as any).$t('prompts.fallback_desc');
                
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
                                <button class="secondary-btn mini" data-action="edit" data-type="${escapeHtml(type)}" title="${(window as any).$t('prompts.tooltip_edit')}">✏️</button>
                                <button class="secondary-btn mini" data-action="reset" data-type="${escapeHtml(type)}" title="${(window as any).$t('prompts.tooltip_reset')}">🔄</button>
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
        showToast((window as any).$t('prompts.toast_loading_detail'), 'info');
        try {
            const res = await authFetch(`${API}/prompts/${docType}`);
            if (!res.ok) throw new Error((window as any).$t('prompts.err_load_detail'));
            const data = await res.json() as PromptSkill & { default_prompt?: string };

            const body = document.createElement('div');
            body.className = 'prompt-edit-modal-body';

            const leftPanel = document.createElement('div');
            leftPanel.className = 'prompt-edit-modal-panel';

            const rightPanel = document.createElement('div');
            rightPanel.className = 'prompt-edit-modal-panel';

            const { wrap: areaWrap, input: areaInput } = _kpBuildModalField({
                id: 'promptContent', label: (window as any).$t('prompts.label_instructions'), type: 'textarea', 
                value: data.system_prompt || data.template || '', 
                placeholder: (window as any).$t('prompts.placeholder_instructions')
            });
            areaWrap.classList.add('prompt-edit-modal-editor-wrap');
            const ta = areaInput as HTMLTextAreaElement;
            ta.classList.add('prompt-edit-modal-textarea', 'premium-scrollbar');
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
            previewLabel.textContent = (window as any).$t('prompts.label_preview');
            
            const previewBox = document.createElement('div');
            previewBox.className = 'markdown-body premium-scrollbar prompt-edit-modal-preview';
            previewBox.style.padding = '16px';
            previewBox.style.background = 'var(--bg3)';
            previewBox.style.border = '1px solid var(--border)';
            previewBox.style.borderRadius = '10px';
            previewBox.style.fontSize = '13px';
            previewBox.style.boxSizing = 'border-box';
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
                title: (window as any).$t('prompts.modal_edit_title', { label: data.label || docType }),
                subtitle: (window as any).$t('prompts.modal_edit_sub'),
                content: body,
                modalClass: 'kp-modal-lg',
                contentStyles: { maxWidth: '1200px', width: '95vw' }, // Ultra-wide modal for IDE feel
                okText: (window as any).$t('prompts.btn_update'),
                onOk: async () => {
                    const content = ta.value.trim();
                    if (!content) return { error: (window as any).$t('prompts.err_empty_content') };

                    try {
                        const upd = await authFetch(`${API}/prompts/${docType}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ system_prompt: content })
                        });
                        if (!upd.ok) throw new Error((window as any).$t('prompts.err_update_failed'));
                        showToast((window as any).$t('prompts.update_success'), 'success');
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
            title: (window as any).$t('prompts.confirm_reset_title'),
            message: (window as any).$t('prompts.confirm_reset_msg', { type: docType }),
            okText: (window as any).$t('prompts.btn_reset_confirm')
        });
        if (!confirmed) return;

        try {
            const res = await authFetch(`${API}/prompts/${docType}/reset`, { method: 'POST' });
            if (!res.ok) throw new Error((window as any).$t('prompts.err_reset_failed'));
            showToast((window as any).$t('prompts.reset_success'), 'success');
            this.loadPromptsPage();
        } catch (e) {
            showToast((e as Error).message, 'error');
        }
    }
}
