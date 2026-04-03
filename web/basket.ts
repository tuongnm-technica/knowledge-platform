import { API, authFetch } from './client';
import { BasketItem, PromptSkill } from './models';
import { kpOpenModal, showToast, escapeHtml, updateBadge } from './ui';

export class BasketModule {
    private items: BasketItem[] = [];
    private maxTokens = 32000;
    private currentTokens = 0;
    private isDrawerOpen = false;

    constructor() {
        this.loadBasket();
        this.bindEvents();
    }

    private bindEvents() {
        document.addEventListener('kp-add-to-basket', (e: Event) => {
            const detail = (e as CustomEvent).detail;
            this.addItem(detail.id, detail.title);
            if (detail.options?.openDrawer) this.isDrawerOpen = true;
            this.render();
        });

        document.addEventListener('kp-open-basket', () => {
            this.isDrawerOpen = true;
            this.render();
        });
    }

    public bindGlobalTriggers() {
        const fab = document.getElementById('basketFab');
        const overlay = document.getElementById('basketOverlay');
        const close = document.getElementById('basketClose');

        if (fab) fab.addEventListener('click', () => { this.isDrawerOpen = !this.isDrawerOpen; this.render(); });
        if (overlay) overlay.addEventListener('click', () => { this.isDrawerOpen = false; this.render(); });
        if (close) close.addEventListener('click', () => { this.isDrawerOpen = false; this.render(); });

        document.getElementById('basket-run-skill')?.addEventListener('click', () => this.basketRunSkill());
        document.getElementById('basket-clear-all')?.addEventListener('click', () => this.clearAll());
    }

    public async loadBasket() {
        const saved = localStorage.getItem('kp_basket');
        if (saved) {
            try {
                this.items = JSON.parse(saved);
                this.currentTokens = this.calculateTokens();
            } catch (err) {
                this.items = [];
            }
        }
        this.render();
    }

    private saveBasket() {
        localStorage.setItem('kp_basket', JSON.stringify(this.items));
        this.currentTokens = this.calculateTokens();
        this.render();
        updateBadge('basket', this.items.length); // Update sidebar badge
    }

    public addItem(id: string, title: string) {
        if (this.items.some(i => i.id === id)) {
            showToast((window as any).$t('basket.err_already_in', { title }), 'info');
            return;
        }
        this.items.push({ id, title, source: 'Knowledge Base' });
        showToast((window as any).$t('basket.add_success', { title }), 'success');
        this.saveBasket();
    }

    public removeItem(id: string) {
        this.items = this.items.filter(i => i.id !== id);
        this.saveBasket();
    }

    public clearAll() {
        this.items = [];
        this.saveBasket();
        showToast((window as any).$t('basket.clear_success'), 'info');
    }

    private calculateTokens(): number {
        // Mock token calculation (chars / 4)
        return Math.floor(this.items.reduce((sum, i) => sum + (i.title.length * 20), 0));
    }

    public toggleDrawer() {
        this.isDrawerOpen = !this.isDrawerOpen;
        this.render();
    }

    public async basketRunSkill() {
        if (this.items.length === 0) {
            showToast((window as any).$t('basket.err_empty_run'), 'warning');
            return;
        }

        // Fetch Prompts
        let prompts = [];
        try {
            const res = await authFetch(`${API}/prompts`);
            if (res.ok) {
                const data = await res.json();
                prompts = data.prompts || [];
                // Sort by group
                prompts.sort((a: PromptSkill, b: PromptSkill) => (a.group || '').localeCompare(b.group || ''));
            }
        } catch (err) {
            showToast((window as any).$t('basket.err_load_skills'), 'error');
        }

        const body = document.createElement('div');
        body.className = 'basket-run-form';
        body.innerHTML = `
            <div style="margin-bottom:12px;">
                <label class="kp-modal-label">${(window as any).$t('basket.label_select_skill')}</label>
                <select id="runSkillSelect" class="form-select kp-modal-input" style="width:100%">
                    <option value="">${(window as any).$t('basket.opt_select_skill')}</option>
                    ${prompts.map((p: PromptSkill) => `
                        <option value="${p.doc_type}">[${escapeHtml(p.group || (window as any).$t('basket.fallback_group'))}] ${escapeHtml(p.label || p.doc_type || (window as any).$t('basket.fallback_skill'))}</option>
                    `).join('')}
                </select>
            </div>
            <div style="padding:12px; background:var(--bg3); border-radius:8px; border:1px solid var(--border); font-size:12px;">
                <strong>${(window as any).$t('basket.label_context')}</strong> ${(window as any).$t('basket.label_context_docs', { count: this.items.length, tokens: this.currentTokens })}
            </div>
            <div style="margin-top:12px;">
                <label class="kp-modal-label">${(window as any).$t('basket.label_goal')}</label>
                <textarea id="runGoalInput" class="form-control kp-modal-input" style="width:100%; min-height:80px;" placeholder="${(window as any).$t('basket.placeholder_goal')}"></textarea>
            </div>
            <div style="margin-top:16px;">
                <label style="display:flex; align-items:center; gap:8px; cursor:pointer">
                    <input type="checkbox" id="runPipelineCheck">
                    <span>${(window as any).$t('basket.label_run_pipeline')}</span>
                </label>
            </div>
        `;

        kpOpenModal({
            title: '🚀 ' + (window as any).$t('basket.run_modal_title'),
            content: body,
            okText: (window as any).$t('basket.run_modal_ok'),
            onOk: async () => {
                const skillId = (body.querySelector('#runSkillSelect') as HTMLSelectElement).value;
                const goal = (body.querySelector('#runGoalInput') as HTMLTextAreaElement).value;
                const isPipeline = (body.querySelector('#runPipelineCheck') as HTMLInputElement).checked;

                if (!skillId) return { error: (window as any).$t('basket.err_no_skill') };

                // Find the selected skill object
                const selectedSkill = prompts.find((p: any) => p.doc_type === skillId);
                if (!selectedSkill) return { error: (window as any).$t('basket.err_invalid_skill') };

                const itemIds = this.items.map(i => i.id);
                const title = `Draft từ ${selectedSkill.label || selectedSkill.doc_type} (${this.items.length} tài liệu)`;

                try {
                    const res = await authFetch(`${API}/docs/drafts/from-documents`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            doc_type: selectedSkill.doc_type || 'srs',
                            doc_ids: itemIds,
                            goal: goal,
                            title: title,
                            run_pipeline: isPipeline // Keep this for future/legacy support
                        }),
                    });

                    if (!res.ok) {
                        const errData = await res.json();
                        throw new Error(errData.detail || (window as any).$t('basket.err_run_failed'));
                    }

                    // Redirect to drafts tab immediately
                    const draftsTab = document.querySelector('.nav-item[data-tab="drafts"]') as HTMLElement;
                    if (draftsTab) {
                        draftsTab.click();
                    }

                    showToast((window as any).$t('basket.run_init_info'), 'info');
                    return true; // Close modal
                } catch (err) {
                    return { error: (err as Error).message };
                }
            }
        });
    }

    public render() {
        const drawer = document.getElementById('basketDrawer');
        const overlay = document.getElementById('basketOverlay');
        const list = document.getElementById('basketItems');
        const count = document.getElementById('basketCount');
        const fabCount = document.getElementById('basketFabCount');
        const tokenVal = document.getElementById('tokenVal');
        const tokenBar = document.getElementById('tokenBar');

        if (drawer) {
            drawer.classList.toggle('active', this.isDrawerOpen);
            drawer.style.display = this.isDrawerOpen ? 'flex' : 'none';
        }
        if (overlay) overlay.style.display = this.isDrawerOpen ? 'block' : 'none';

        if (count) count.textContent = String(this.items.length);
        if (fabCount) fabCount.textContent = String(this.items.length);

        if (tokenVal) tokenVal.textContent = String(this.currentTokens);
        if (tokenBar) {
            const pct = Math.min(100, (this.currentTokens / this.maxTokens) * 100);
            tokenBar.style.width = `${pct}%`;
            tokenBar.style.background = pct > 90 ? 'var(--danger)' : (pct > 70 ? 'var(--warn)' : 'var(--accent)');
        }

        if (list) {
            if (this.items.length === 0) {
                list.innerHTML = `
                    <div class="basket-empty">
                        <div style="font-size:32px; margin-bottom:12px;">📥</div>
                        <div>${(window as any).$t('basket.empty_hint')}</div>
                        <div style="font-size:12px; color:var(--text-dim); margin-top:4px;">${(window as any).$t('basket.empty_sub')}</div>
                    </div>
                `;
            } else {
                list.innerHTML = this.items.map(item => `
                    <div class="basket-item premium-card">
                        <div class="item-info">
                            <div class="item-title">${escapeHtml(item.title)}</div>
                            <div class="item-meta">${escapeHtml(item.source)}</div>
                        </div>
                        <button class="remove-btn" data-id="${item.id}">✕</button>
                    </div>
                `).join('');

                list.querySelectorAll('.remove-btn').forEach(btn => {
                    btn.addEventListener('click', () => this.removeItem(btn.getAttribute('data-id')!));
                });
            }
        }
    }
}