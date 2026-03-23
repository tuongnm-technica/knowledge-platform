import { API, authFetch } from './client';
import { BasketItem } from './models';
import { kpOpenModal, showToast, escapeHtml, kpConfirm } from './ui';

export class BasketModule {
    private items: BasketItem[] = [];
    private maxTokens = 32000;
    private currentTokens = 0;
    private isDrawerOpen = false;

    constructor() {
        this.loadInitialData();
        
        document.addEventListener('kp-add-to-basket', (e: Event) => {
            const detail = (e as CustomEvent).detail;
            this.addToBasket(detail.id, detail.title, detail.options);
        });
        
        document.addEventListener('kp-refresh-basket', () => {
            this.loadBasket();
        });
    }

    private loadInitialData() {
        this.loadBasket();
    }

    private loadBasket() {
        const stored = localStorage.getItem('kp_basket');
        if (stored) {
            try { 
                this.items = JSON.parse(stored) as BasketItem[]; 
            } catch (e) { 
                this.items = []; 
            }
        }
        this.updateStateAndUI();
    }

    private saveBasket() {
        localStorage.setItem('kp_basket', JSON.stringify(this.items));
        this.updateStateAndUI();
    }

    private updateStateAndUI() {
        this.currentTokens = this.items.length * 1500;
        
        // Update global badge store (still using Alpine store for badges for now to avoid breaking header)
        const alpine = (window as any).Alpine;
        if (alpine?.store('badges')) {
            alpine.store('badges').basket = this.items.length;
        }

        this.render();
    }

    public addToBasket(id: string, title: string, options?: { openDrawer?: boolean }) {
        if (!this.items.find((item: BasketItem) => item.id === id)) {
            this.items.push({ id, title });
            this.saveBasket();
            showToast('Đã thêm vào giỏ ngữ cảnh', 'success');
        } else {
            showToast('Tài liệu đã có trong giỏ', 'info');
        }
        if (options?.openDrawer) {
            this.isDrawerOpen = true;
            this.render();
        }
    }

    public removeFromBasket(id: string) {
        this.items = this.items.filter((item: BasketItem) => item.id !== id);
        this.saveBasket();
    }

    public async clearBasket() {
        if (!await kpConfirm({ 
            title: 'Xóa giỏ ngữ cảnh', 
            message: 'Bạn có chắc muốn xóa toàn bộ giỏ ngữ cảnh? Hành động này không thể hoàn tác.', 
            danger: true 
        })) return;
        this.items = [];
        this.saveBasket();
    }

    public refreshBasketDetails() {
        this.updateStateAndUI();
        showToast('Đã cập nhật thông tin giỏ', 'success');
    }

    public toggleDrawer() { 
        this.isDrawerOpen = !this.isDrawerOpen; 
        this.render();
    }

    public closeDrawer() { 
        this.isDrawerOpen = false; 
        this.render();
    }

    public async basketRunSkill() {
        if (this.items.length === 0) {
            showToast('Giỏ ngữ cảnh đang trống', 'warning');
            return;
        }
    
        let prompts: any[] = [];
        try {
            const res = await authFetch(`${API}/prompts`);
            if (res.ok) {
                const data = await res.json();
                prompts = data.prompts || [];
            }
        } catch (e) {
            console.error('Failed to load prompts:', e);
        }

        // Sort prompts by GPT-X for consistency
        const sortedPrompts = prompts.sort((a, b) => {
            const grpA = a.group || "";
            const grpB = b.group || "";
            if (grpA.includes('GPT-') && grpB.includes('GPT-')) {
                const numA = parseInt(grpA.split('GPT-')[1]);
                const numB = parseInt(grpB.split('GPT-')[1]);
                if (numA !== numB) return numA - numB;
            }
            return (a.label || "").localeCompare(b.label || "");
        });

        const skillOptionsHtml = sortedPrompts.map(p => 
            `<option value="${escapeHtml(p.doc_type || p.type)}">${escapeHtml(p.label || p.name)}</option>`
        ).join('') || '<option value="srs">📄 SRS (Mặc định)</option>';
        
        const body = document.createElement('div');
        body.innerHTML = `
        <div style="margin-bottom: 16px;">
            <label style="display:block; margin-bottom:8px; font-weight:600; font-size:13px;">Chế độ chạy</label>
            <div style="display:flex; gap:16px; margin-bottom: 16px; font-size:13px;">
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
                <input type="radio" name="runMode" value="single" checked id="radioRunSingle"> 
                Tùy chọn 1 Agent
            </label>
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
                <input type="radio" name="runMode" value="pipeline" id="radioRunPipeline"> 
                Chạy Full Luồng (SDLC)
            </label>
            </div>
            
            <div id="singleAgentSelect">
                <label style="display:block; margin-bottom:4px; font-weight:600; font-size:13px;">Chọn loại tài liệu (Skill)</label>
                <select id="skillTypeSelect" class="time-input" style="width:100%; box-sizing: border-box; padding: 10px;">
                    ${skillOptionsHtml}
                </select>
            </div>
            
            <div id="pipelineSelect" style="display:none; padding:14px; background:var(--bg3); border:1px solid var(--border); border-radius:12px; font-size:12.5px; color:var(--text-muted);">
                <strong>🚀 Pipeline sẽ chạy tuần tự 4 Agents:</strong><br>
                1. GPT-1: Requirements Intake<br>
                2. GPT-3: Solution Design<br>
                3. GPT-4: SRS<br>
                4. GPT-5: User Stories
            </div>
        </div>
        <div>
            <label style="display:block; margin-bottom:4px; font-weight:600; font-size:13px;">Yêu cầu thêm (Prompt cho AI)</label>
            <textarea id="skillInstructionInput" class="time-input" style="width:100%; min-height:80px;" placeholder="Ví dụ: Tập trung vào luồng thanh toán VNPay..."></textarea>
        </div>`;

        // Add event listeners for radio buttons in modal
        body.querySelector('#radioRunSingle')?.addEventListener('change', () => {
            (body.querySelector('#singleAgentSelect') as HTMLElement).style.display = 'block';
            (body.querySelector('#pipelineSelect') as HTMLElement).style.display = 'none';
        });
        body.querySelector('#radioRunPipeline')?.addEventListener('change', () => {
            (body.querySelector('#singleAgentSelect') as HTMLElement).style.display = 'none';
            (body.querySelector('#pipelineSelect') as HTMLElement).style.display = 'block';
        });

        kpOpenModal({
            title: '✨ Chạy AI Skill',
            content: body,
            okText: '🚀 Bắt đầu tạo',
            onOk: async () => {
                const runModeEl = body.querySelector('input[name="runMode"]:checked') as HTMLInputElement;
                const runMode = runModeEl ? runModeEl.value : 'single';
                const instructionEl = body.querySelector('#skillInstructionInput') as HTMLTextAreaElement;
                const goal = instructionEl ? instructionEl.value.trim() : '';
                const docIds = this.items.map(i => i.id);

                this.closeDrawer();
                showToast('Đang khởi tạo Agent... Vui lòng đợi.', 'info');
                
                if (runMode === 'single') {
                    const skillSelect = body.querySelector('#skillTypeSelect') as HTMLSelectElement;
                    const docType = skillSelect ? skillSelect.value : 'srs';
                    try {
                        const res = await authFetch(`${API}/docs/drafts/from-documents`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ doc_type: docType, doc_ids: docIds, goal: goal })
                        });
                        if (!res.ok) throw new Error('Lỗi khi chạy skill');
                        showToast('Tạo bản nháp thành công!', 'success');
                        document.dispatchEvent(new CustomEvent('kp-navigate', { detail: 'drafts' }));
                        return true;
                    } catch (err) { 
                        const error = err as Error;
                        return { error: error.message }; 
                    }
                } else {
                    document.dispatchEvent(new CustomEvent('kp-navigate', { detail: 'drafts' }));
                    const pipeline = ['requirements_intake', 'solution_design', 'srs', 'user_stories'];
                    
                    (async () => {
                        for (let i = 0; i < pipeline.length; i++) {
                            const dt = pipeline[i];
                            showToast(`⚙️ Đang chạy Agent ${i+1}/4: ${dt.toUpperCase()}...`, 'info');
                            await authFetch(`${API}/docs/drafts/from-documents`, {
                                method: 'POST', headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ doc_type: dt, doc_ids: docIds, goal: goal })
                            });
                            document.dispatchEvent(new CustomEvent('kp-refresh-drafts')); // Real-time Update UI
                        }
                        showToast('🎉 Đã hoàn tất SDLC Pipeline!', 'success');
                    })();
                    return true;
                }
            }
        });
    }

    private render() {
        const drawer = document.querySelector('.basket-drawer');
        const overlay = document.querySelector('.basket-overlay');
        const fab = document.querySelector('.basket-fab');
        
        if (!drawer || !overlay || !fab) return;

        // Sync visibility
        if (this.isDrawerOpen) {
            drawer.classList.add('active');
            overlay.classList.add('active');
            drawer.setAttribute('style', 'display: flex');
            overlay.setAttribute('style', 'display: block');
        } else {
            drawer.classList.remove('active');
            overlay.classList.remove('active');
            drawer.setAttribute('style', 'display: none');
            overlay.setAttribute('style', 'display: none');
        }

        // 1. Update Header
        const sub = drawer.querySelector('.basket-sub');
        if (sub) sub.textContent = `${this.items.length} items`;

        // 2. Update Tokens
        const tokenVal = drawer.querySelector('.basket-token-value') as HTMLElement;
        if (tokenVal) {
            tokenVal.textContent = `${this.currentTokens} / ${this.maxTokens}`;
            tokenVal.style.color = this.currentTokens > this.maxTokens ? 'var(--danger)' : '';
        }
        const progressFill = drawer.querySelector('.basket-progress-fill') as HTMLElement;
        if (progressFill) {
            const pct = Math.min(100, (this.currentTokens / this.maxTokens) * 100);
            progressFill.style.width = `${pct}%`;
            progressFill.style.backgroundColor = this.currentTokens > this.maxTokens 
                ? 'var(--danger)' 
                : (pct > 80 ? 'var(--warning)' : 'var(--primary)');
        }

        // 3. Update List
        const list = drawer.querySelector('.basket-list') as HTMLElement;
        if (list) {
            if (this.items.length === 0) {
                list.innerHTML = '<div class="basket-empty">Chưa có item nào. Hãy bấm 📌 để ghim ngữ cảnh.</div>';
            } else {
                list.innerHTML = this.items.map(item => `
                    <div class="basket-item">
                        <div class="basket-item-icon">📄</div>
                        <div class="basket-item-info">
                            <div class="basket-item-title">${escapeHtml(item.title || item.id)}</div>
                            <div class="basket-item-meta" style="font-size:11px;color:var(--text-dim);">${escapeHtml(item.id)}</div>
                        </div>
                        <button class="secondary-btn mini remove-item-btn" data-id="${escapeHtml(item.id)}" style="color:var(--danger); border-color:var(--danger)" title="Xóa">✕</button>
                    </div>
                `).join('');

                // Bind remove buttons
                list.querySelectorAll('.remove-item-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
                        if (id) this.removeFromBasket(id);
                    });
                });
            }
        }
    }

    public bindGlobalTriggers() {
        // This should be called once by main.ts
        document.querySelector('.basket-fab')?.addEventListener('click', () => this.toggleDrawer());
        document.querySelector('.basket-overlay')?.addEventListener('click', () => this.closeDrawer());
        document.querySelector('.basket-header-actions button:nth-child(1)')?.addEventListener('click', () => this.clearBasket());
        document.querySelector('.basket-header-actions button:nth-child(2)')?.addEventListener('click', () => this.closeDrawer());
        document.querySelector('.basket-actions button:nth-child(1)')?.addEventListener('click', () => this.refreshBasketDetails());
        document.querySelector('.basket-actions button:nth-child(2)')?.addEventListener('click', () => this.basketRunSkill());
    }
}