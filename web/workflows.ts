import { API, authFetch } from './client';
import { AIWorkflow } from './models';
import { escapeHtml, showToast, kpConfirm, kpOpenModal, _kpBuildModalField } from './ui';
import { renderMarkdown } from './format';

export class WorkflowsModule {
    public async loadWorkflowsPage(): Promise<void> {
        const container = document.getElementById('page-workflows');
        if (container) container.innerHTML = '<div style="padding:40px; text-align:center;">Đang tải danh sách AI Workflows...</div>';

        try {
            const res = await authFetch(`${API}/workflows`);
            if (!res.ok) throw new Error('Không thể tải workflows');
            const data = await res.json();
            this.renderWorkflows((data.workflows || []) as AIWorkflow[]);
        } catch(err) {
            const error = err as Error;
            if (container) container.innerHTML = `<div style="padding:40px; text-align:center; color:var(--danger)">Lỗi tải API: ${escapeHtml(error.message)}</div>`;
        }
    }

    private renderWorkflows(workflows: AIWorkflow[]): void {
        const container = document.getElementById('page-workflows');
        if (!container) return;
        
        container.innerHTML = `
        <div class="connectors-content">
            <div class="page-intro">
                <div>
                    <div class="intro-kicker">AI Workflows</div>
                    <div class="intro-title">Agentic Chains</div>
                    <div class="intro-sub">Quản lý các chuỗi tác vụ AI phức tạp, thực thi qua nhiều bước nối tiếp nhau.</div>
                </div>
                <!-- <div style="font-size:12px; color:var(--text-dim); border: 1px solid var(--border); padding: 8px; border-radius: 8px;">
                    💡 Tips: Tạo workflows qua Database script cho phiên bản hiện tại
                </div> -->
                <button class="primary-btn" id="btnCreateDemoWf">Tạo Workflow Mẫu</button>
            </div>
            <div class="connectors-grid" id="workflowsGrid" style="padding: 0 20px;"></div>
        </div>`;

        const grid = document.getElementById('workflowsGrid');
        if (!grid) return;

        if (!workflows || workflows.length === 0) {
            grid.innerHTML = '<div class="search-empty" style="grid-column:1/-1;">Chưa cấu hình Workflow nào.</div>';
            return;
        }

        workflows.forEach(w => {
            const card = document.createElement('div');
            card.className = 'connector-card-rich';
            card.innerHTML = `
                <div style="padding:20px; display:flex; flex-direction:column; height: 100%;">
                    <div style="font-weight:bold; font-size:16px; margin-bottom:8px;">${escapeHtml(w.name)}</div>
                    <div class="markdown-body" style="font-size:13px; color:var(--text-dim); margin-bottom:16px; flex-grow:1;">${renderMarkdown(w.description || 'No description')}</div>
                    
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <span style="background:var(--bg3); padding:4px 8px; border-radius:4px; font-size:11px; color:var(--text)">Triggers: ${escapeHtml(w.trigger_type)}</span>
                        
                        <div class="connector-actions-row" style="margin-top:0; border:none; padding:0; background:transparent">
                            <button class="primary-btn mini" data-action="run" data-id="${w.id}">▶ Chạy</button>
                            <button class="secondary-btn mini" style="color:var(--danger); border-color:transparent" data-action="delete" data-id="${w.id}">🗑</button>
                        </div>
                    </div>
                </div>
            `;
            
            card.addEventListener('click', (e) => {
                const btn = (e.target as HTMLElement).closest('button');
                const action = btn?.getAttribute('data-action');
                if (action === 'run') {
                    this.runWorkflow(w);
                } else if (action === 'delete') {
                    this.deleteWorkflow(w);
                }
            });
            
            grid.appendChild(card);
        });

        document.getElementById('btnCreateDemoWf')?.addEventListener('click', async () => {
            try {
                showToast('Đang tạo workflow mẫu...', 'info');
                const res = await authFetch(`${API}/workflows/demo`, { method: 'POST' });
                if (!res.ok) throw new Error('Không thể tạo workflow mẫu');
                showToast('Đã tạo thành công!', 'success');
                this.loadWorkflowsPage();
            } catch (e) {
                showToast((e as Error).message, 'error');
            }
        });
    }

    private async deleteWorkflow(w: AIWorkflow): Promise<void> {
        const ok = await kpConfirm({
            title: 'Xóa Workflow',
            message: `Bạn có chắc muốn xóa vĩnh viễn Workflow "${w.name}"? Tác vụ này không thể phục hồi.`,
            danger: true
        });
        if (!ok) return;

        try {
            showToast('Đang xóa...', 'info');
            const res = await authFetch(`${API}/workflows/${w.id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Xóa thất bại');
            showToast('Đã xóa workflow', 'success');
            this.loadWorkflowsPage();
        } catch(e) {
            showToast((e as Error).message, 'error');
        }
    }

    private async runWorkflow(w: AIWorkflow): Promise<void> {
        const bodyWrapper = document.createElement('div');
        bodyWrapper.innerHTML = `
            <div style="margin-bottom:16px; font-size:13px; color:var(--text); opacity: 0.9">
                Dữ liệu văn bản này sẽ được gán vào biến <b>{{START}}</b> của Workflow.
            </div>
        `;
        const { wrap, input } = _kpBuildModalField({
            id: 'wfInput',
            label: 'Dữ liệu đầu vào ban đầu (Initial Context/Prompt)',
            type: 'textarea',
            placeholder: 'Nhập nội dung văn bản, yêu cầu hoặc URL...',
            required: true
        });
        const ta = input as HTMLTextAreaElement;
        ta.style.height = '120px';
        bodyWrapper.appendChild(wrap);

        await kpOpenModal({
            title: `▶ Trigger Workflow: ${w.name}`,
            content: bodyWrapper,
            okText: 'Execute Action',
            onOk: async () => {
                const val = ta.value.trim();
                if (!val) return { error: 'Vui lòng nhập bối cảnh khởi chạy.' };
                
                try {
                    const res = await authFetch(`${API}/workflows/${w.id}/run`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({ initial_context: val })
                    });
                    if (!res.ok) throw new Error(await res.text());
                    
                    showToast('Đã đẩy lệnh vào hàng đợi! Hệ thống sẽ chuyển qua giao diện theo dõi.', 'success');
                    // Gửi signal để nhảy qua tab Chat
                    setTimeout(() => {
                        document.dispatchEvent(new CustomEvent('kp-navigate', { detail: 'chat' }));
                    }, 500);
                    return true;
                } catch(e) {
                    return { error: (e as Error).message };
                }
            }
        });
    }
}
