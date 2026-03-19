import { API, authFetch } from './client';
import { BasketItem } from './models';
import { kpOpenModal, showToast } from './ui';

export function BasketAlpine() {
    return {
        items: [] as BasketItem[],
        maxTokens: 32000,
        currentTokens: 0,
        isDrawerOpen: false,

        init() {
            this.loadBasket();
            document.addEventListener('kp-add-to-basket', (e: any) => {
                this.addToBasket(e.detail.id, e.detail.title, e.detail.options);
            });
        },

        loadBasket() {
            const stored = localStorage.getItem('kp_basket');
            if (stored) {
                try { this.items = JSON.parse(stored); } catch (e) { this.items = []; }
            }
            this.updateBadges();
        },

        saveBasket() {
            localStorage.setItem('kp_basket', JSON.stringify(this.items));
            this.updateBadges();
        },

        updateBadges() {
            this.currentTokens = this.items.length * 1500;
            (window as any).Alpine.store('badges').basket = this.items.length;
        },

        addToBasket(id: string, title: string, options?: { openDrawer?: boolean }) {
            if (!this.items.find((item: BasketItem) => item.id === id)) {
                this.items.push({ id, title });
                this.saveBasket();
                showToast('Đã thêm vào giỏ ngữ cảnh', 'success');
            } else {
                showToast('Tài liệu đã có trong giỏ', 'info');
            }
            if (options?.openDrawer) this.isDrawerOpen = true;
        },

        removeFromBasket(id: string) {
            this.items = this.items.filter((item: BasketItem) => item.id !== id);
            this.saveBasket();
        },

        clearBasket() {
            if (!confirm('Bạn có chắc muốn xóa toàn bộ giỏ ngữ cảnh?')) return;
            this.items = [];
            this.saveBasket();
        },

        refreshBasketDetails() {
            this.updateBadges();
            showToast('Đã cập nhật thông tin giỏ', 'success');
        },

        toggleDrawer() { this.isDrawerOpen = !this.isDrawerOpen; },
        closeDrawer() { this.isDrawerOpen = false; },

        basketRunSkill() {
            if (this.items.length === 0) {
                showToast('Giỏ ngữ cảnh đang trống', 'warning');
                return;
            }
        
        let skillOptionsHtml = '<option value="srs">📄 GPT-4: SRS (Mặc định)</option>';
        
        const body = document.createElement('div');
        body.innerHTML = `
        <div style="margin-bottom: 16px;">
            <label style="display:block; margin-bottom:8px; font-weight:600; font-size:13px;">Chế độ chạy</label>
            <div style="display:flex; gap:16px; margin-bottom: 16px; font-size:13px;">
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
                <input type="radio" name="runMode" value="single" checked onchange="document.getElementById('singleAgentSelect').style.display='block'; document.getElementById('pipelineSelect').style.display='none';"> 
                Tùy chọn 1 Agent
            </label>
            <label style="display:flex; align-items:center; gap:6px; cursor:pointer;">
                <input type="radio" name="runMode" value="pipeline" onchange="document.getElementById('singleAgentSelect').style.display='none'; document.getElementById('pipelineSelect').style.display='block';"> 
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
        </div>
        `;

        kpOpenModal({
            title: '✨ Chạy AI Skill',
            content: body,
            okText: '🚀 Bắt đầu tạo',
            onOk: async () => {
                const runMode = (document.querySelector('input[name="runMode"]:checked') as HTMLInputElement).value;
                const goal = (document.getElementById('skillInstructionInput') as HTMLInputElement).value.trim();
                const docIds = this.items.map(i => i.id);

                this.closeBasketDrawer();
                this.showToast('Đang khởi tạo Agent... Vui lòng đợi.', 'info');
                
                if (runMode === 'single') {
                    const docType = (document.getElementById('skillTypeSelect') as HTMLSelectElement).value;
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
                    } catch (e: any) { return { error: e.message }; }
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

    // --- Drawer Controls ---
    public toggleBasketDrawer(): void {
        const drawer = document.getElementById('basketDrawer');
        if (drawer && drawer.style.display === 'flex') {
            this.closeBasketDrawer();
        } else {
            this.openBasketDrawer();
        }
    }

    public openBasketDrawer(): void {
        const drawer = document.getElementById('basketDrawer');
        const overlay = document.getElementById('basketOverlay');
        if (drawer) drawer.style.display = 'flex';
        if (overlay) overlay.style.display = 'block';
        this.renderBasket();
    }

    public closeBasketDrawer(): void {
        const drawer = document.getElementById('basketDrawer');
        const overlay = document.getElementById('basketOverlay');
        if (drawer) drawer.style.display = 'none';
        if (overlay) overlay.style.display = 'none';
    }

    // --- Helpers ---
    private showToast(message: string, type: string): void {
        if (typeof (window as any).showToast === 'function') {
            (window as any).showToast(message, type);
        } else {
            alert(`[${type}] ${message}`);
        }
    }

    private escapeHtml(unsafe: string): string {
        return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
}