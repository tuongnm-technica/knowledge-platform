/**
 * web/workflows.ts
 * AI Workflows Module — Full rebuild with:
 * - Workflow list page with rich cards
 * - Workflow Builder Modal (create + edit, dynamic node management)
 * - Inline Execution Tracker (live polling, per-node progress)
 * - Run History tab
 * - Template Gallery
 */
import { API, authFetch } from './client';
import { AIWorkflow, AIWorkflowNode } from './models';
import { escapeHtml, showToast, kpConfirm, kpOpenModal } from './ui';
import { renderMarkdown } from './format';

// ── Types ──────────────────────────────────────────────────────────────────────

interface WorkflowRun {
    id: string;
    workflow_id: string;
    job_id: string | null;
    triggered_by: string;
    trigger_type: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    initial_context: string;
    node_outputs: Record<string, string>;
    final_output: string | null;
    error: string | null;
    started_at: string | null;
    finished_at: string | null;
    created_at: string;
}

// ── Template Presets ────────────────────────────────────────────────────────────

const WORKFLOW_TEMPLATES = [
    {
        icon: '🔍',
        name: 'Research & Report',
        description: 'Tìm kiếm trong Knowledge Base, tóm tắt và định dạng thành báo cáo.',
        trigger_type: 'manual',
        nodes: [
            {
                step_order: 1, name: 'RAG Search', node_type: 'rag',
                system_prompt: 'Bạn là trợ lý nghiên cứu. Dựa trên thông tin từ Knowledge Base và yêu cầu:\n\n{{START}}\n\nHãy tổng hợp và phân tích các thông tin tìm được.',
            },
            {
                step_order: 2, name: 'Format Report', node_type: 'llm',
                system_prompt: 'Dựa trên phân tích sau:\n\n{{node_1_output}}\n\nHãy viết một báo cáo hoàn chỉnh theo format: ## Tóm tắt, ## Phát hiện chính, ## Kết luận.',
            }
        ]
    },
    {
        icon: '📋',
        name: 'Meeting to Tasks',
        description: 'Từ biên bản họp → trích xuất action items → tạo Task Drafts.',
        trigger_type: 'manual',
        nodes: [
            {
                step_order: 1, name: 'Extract Action Items', node_type: 'rag',
                system_prompt: 'Tìm kiếm biên bản họp liên quan đến: {{START}}\n\nTrích xuất tất cả action items, người phụ trách, và deadline dưới dạng danh sách có cấu trúc.',
            },
            {
                step_order: 2, name: 'Format Tasks', node_type: 'llm',
                system_prompt: 'Dựa trên action items:\n\n{{node_1_output}}\n\nHãy format thành danh sách Jira tasks với: Title, Description, Assignee, Priority (High/Medium/Low).',
            }
        ]
    },
    {
        icon: '📄',
        name: 'SDLC Pipeline',
        description: 'Từ yêu cầu nghiệp vụ → tự động tạo tài liệu BA, SA, QA.',
        trigger_type: 'manual',
        nodes: [
            {
                step_order: 1, name: 'Business Analysis', node_type: 'rag',
                system_prompt: 'Bạn là Business Analyst. Phân tích yêu cầu:\n\n{{START}}\n\nViết tài liệu phân tích nghiệp vụ: Use Cases, User Stories, Acceptance Criteria.',
            },
            {
                step_order: 2, name: 'Solution Design', node_type: 'llm',
                system_prompt: 'Dựa trên BA:\n\n{{node_1_output}}\n\nViết Solution Design: Architecture, API contracts, Database schema, Deployment notes.',
            },
            {
                step_order: 3, name: 'QA Test Plan', node_type: 'llm',
                system_prompt: 'Dựa trên BA và SA:\n\n{{node_1_output}}\n\nTạo Test Plan: Test cases, Scenarios, Expected results cho từng Use Case.',
            }
        ]
    },
    {
        icon: '📊',
        name: 'Daily Summary',
        description: 'Tóm tắt hoạt động hàng ngày từ các nguồn dữ liệu.',
        trigger_type: 'scheduled',
        schedule_cron: '0 8 * * 1-5',
        nodes: [
            {
                step_order: 1, name: 'Fetch & Analyze', node_type: 'rag',
                system_prompt: 'Tìm kiếm các hoạt động, cuộc họp, và cập nhật trong: {{START}}\n\nTổng hợp những điểm quan trọng nhất.',
            },
            {
                step_order: 2, name: 'Write Summary', node_type: 'llm',
                system_prompt: 'Từ thông tin:\n\n{{node_1_output}}\n\nViết bản tóm tắt ngắn gọn theo format: ✅ Hoàn thành, 🔄 Đang tiến hành, ⚠️ Cần chú ý.',
            }
        ]
    },
];

// ── Main Module ────────────────────────────────────────────────────────────────

export class WorkflowsModule {
    private activePollingInterval: ReturnType<typeof setInterval> | null = null;

    public async init(): Promise<void> {
        await this.loadWorkflowsPage();
    }

    public async loadWorkflowsPage(): Promise<void> {
        const container = document.getElementById('page-workflows');
        if (container) container.innerHTML = '<div class="wf-loading"><div class="wf-spinner"></div><span>Đang tải AI Workflows...</span></div>';

        try {
            const res = await authFetch(`${API}/workflows`);
            if (!res.ok) throw new Error('Không thể tải workflows');
            const data = await res.json();
            this.renderWorkflowsPage((data.workflows || []) as AIWorkflow[]);
        } catch (err) {
            const error = err as Error;
            const container = document.getElementById('page-workflows');
            if (container) container.innerHTML = `<div class="wf-empty-state"><div class="wf-empty-icon">⚠️</div><div class="wf-empty-title">Lỗi tải dữ liệu</div><div class="wf-empty-sub">${escapeHtml(error.message)}</div></div>`;
        }
    }

    // ── Render Page ──────────────────────────────────────────────────────────

    private renderWorkflowsPage(workflows: AIWorkflow[]): void {
        const container = document.getElementById('page-workflows');
        if (!container) return;

        container.innerHTML = `
        <div class="wf-page">
            <!-- Header -->
            <div class="wf-header">
                <div class="wf-header-left">
                    <div class="wf-header-kicker">🤖 Agentic Automation</div>
                    <h1 class="wf-header-title">AI Workflows</h1>
                    <p class="wf-header-sub">Xây dựng và chạy các chuỗi AI tự động hoá, nối tiếp nhiều bước xử lý thông minh.</p>
                </div>
                <div class="wf-header-actions">
                    <button class="wf-btn wf-btn-secondary" id="btnShowTemplates">📚 Template Gallery</button>
                    <button class="wf-btn wf-btn-primary" id="btnCreateWorkflow">＋ Tạo Workflow</button>
                </div>
            </div>

            <!-- Stats Bar -->
            <div class="wf-stats-bar">
                <div class="wf-stat">
                    <span class="wf-stat-val">${workflows.length}</span>
                    <span class="wf-stat-label">Workflows</span>
                </div>
                <div class="wf-stat">
                    <span class="wf-stat-val">${workflows.filter(w => w.trigger_type === 'scheduled').length}</span>
                    <span class="wf-stat-label">Scheduled</span>
                </div>
                <div class="wf-stat">
                    <span class="wf-stat-val">${workflows.filter(w => w.trigger_type === 'webhook').length}</span>
                    <span class="wf-stat-label">Webhooks</span>
                </div>
                <div class="wf-stat">
                    <span class="wf-stat-val">${workflows.filter(w => w.trigger_type === 'manual').length}</span>
                    <span class="wf-stat-label">Manual</span>
                </div>
            </div>

            <!-- Workflow Grid -->
            <div class="wf-grid" id="wfGrid"></div>
        </div>`;

        // Attach button handlers
        document.getElementById('btnCreateWorkflow')?.addEventListener('click', () => this.openWorkflowBuilder(null));
        document.getElementById('btnShowTemplates')?.addEventListener('click', () => this.openTemplateGallery());

        const grid = document.getElementById('wfGrid');
        if (!grid) return;

        if (!workflows || workflows.length === 0) {
            grid.innerHTML = `
            <div class="wf-empty-state">
                <div class="wf-empty-icon">🚀</div>
                <div class="wf-empty-title">Chưa có Workflow nào</div>
                <div class="wf-empty-sub">Tạo workflow đầu tiên hoặc chọn từ Template Gallery để bắt đầu tự động hoá.</div>
                <div style="display:flex;gap:12px;justify-content:center;margin-top:20px;">
                    <button class="wf-btn wf-btn-secondary" id="btnEmptyTemplates">📚 Template Gallery</button>
                    <button class="wf-btn wf-btn-primary" id="btnEmptyCreate">＋ Tạo ngay</button>
                </div>
            </div>`;
            document.getElementById('btnEmptyCreate')?.addEventListener('click', () => this.openWorkflowBuilder(null));
            document.getElementById('btnEmptyTemplates')?.addEventListener('click', () => this.openTemplateGallery());
            return;
        }

        workflows.forEach(w => this.renderWorkflowCard(w, grid));
    }

    private renderWorkflowCard(w: AIWorkflow, container: HTMLElement): void {
        const card = document.createElement('div');
        card.className = 'wf-card';
        card.setAttribute('data-id', w.id);

        const triggerBadge = this.getTriggerBadge(w.trigger_type);
        const timeFmt = w.updated_at ? new Date(w.updated_at).toLocaleDateString('vi-VN') : '—';

        card.innerHTML = `
        <div class="wf-card-header">
            <div class="wf-card-icon">${this.getWorkflowIcon(w.name)}</div>
            <div class="wf-card-meta">
                <div class="wf-card-name">${escapeHtml(w.name)}</div>
                <div class="wf-card-time">Cập nhật ${timeFmt}</div>
            </div>
            <div class="wf-card-badge ${triggerBadge.cls}">${triggerBadge.label}</div>
        </div>
        <div class="wf-card-desc markdown-body">${renderMarkdown(w.description || 'Không có mô tả.')}</div>
        ${(w as any).schedule_cron ? `<div class="wf-card-cron">🕐 Cron: <code>${escapeHtml((w as any).schedule_cron)}</code></div>` : ''}
        <div class="wf-card-actions">
            <button class="wf-btn wf-btn-primary wf-btn-sm" data-action="run" data-id="${w.id}">▶ Chạy</button>
            <button class="wf-btn wf-btn-secondary wf-btn-sm" data-action="history" data-id="${w.id}">📋 Lịch sử</button>
            <button class="wf-btn wf-btn-secondary wf-btn-sm" data-action="edit" data-id="${w.id}">✏️ Sửa</button>
            <button class="wf-btn wf-btn-danger wf-btn-sm" data-action="delete" data-id="${w.id}">🗑</button>
        </div>`;

        card.addEventListener('click', async (e) => {
            const btn = (e.target as HTMLElement).closest('[data-action]');
            if (!btn) return;
            const action = btn.getAttribute('data-action');
            if (action === 'run') this.openRunModal(w);
            else if (action === 'edit') this.openWorkflowBuilder(w);
            else if (action === 'history') this.openRunHistory(w);
            else if (action === 'delete') this.deleteWorkflow(w);
        });

        container.appendChild(card);
    }

    private getWorkflowIcon(name: string): string {
        const n = name.toLowerCase();
        if (n.includes('meeting') || n.includes('họp')) return '📅';
        if (n.includes('report') || n.includes('báo cáo')) return '📊';
        if (n.includes('sdlc') || n.includes('ba') || n.includes('sa')) return '⚙️';
        if (n.includes('research') || n.includes('nghiên')) return '🔍';
        if (n.includes('daily') || n.includes('hàng ngày')) return '📆';
        return '🤖';
    }

    private getTriggerBadge(type: string): { cls: string; label: string } {
        if (type === 'scheduled') return { cls: 'wf-badge-scheduled', label: '⏰ Scheduled' };
        if (type === 'webhook') return { cls: 'wf-badge-webhook', label: '🔗 Webhook' };
        return { cls: 'wf-badge-manual', label: '▶ Manual' };
    }

    // ── Workflow Builder Modal ─────────────────────────────────────────────────

    private openWorkflowBuilder(workflow: AIWorkflow | null): void {
        const isEdit = !!workflow;
        const nodes: AIWorkflowNode[] = (workflow as any)?.nodes || [{ step_order: 1, name: 'Step 1', node_type: 'llm', system_prompt: '', model_override: null }];

        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
        <div class="wf-builder">
            <!-- Basic Info -->
            <div class="wf-form-section">
                <div class="wf-form-group">
                    <label class="wf-label">Tên Workflow <span class="wf-required">*</span></label>
                    <input id="wfBuilderName" class="wf-input" type="text" placeholder="Vd: Daily Research Report" value="${escapeHtml(workflow?.name || '')}">
                </div>
                <div class="wf-form-group">
                    <label class="wf-label">Mô tả</label>
                    <textarea id="wfBuilderDesc" class="wf-input wf-textarea" placeholder="Mô tả ngắn về workflow này...">${escapeHtml(workflow?.description || '')}</textarea>
                </div>
                <div style="display:flex;gap:16px;">
                    <div class="wf-form-group" style="flex:1">
                        <label class="wf-label">Trigger Type</label>
                        <select id="wfBuilderTrigger" class="wf-input wf-select">
                            <option value="manual" ${workflow?.trigger_type === 'manual' ? 'selected' : ''}>▶ Manual (chạy tay)</option>
                            <option value="scheduled" ${workflow?.trigger_type === 'scheduled' ? 'selected' : ''}>⏰ Scheduled (cron)</option>
                            <option value="webhook" ${workflow?.trigger_type === 'webhook' ? 'selected' : ''}>🔗 Webhook (API)</option>
                        </select>
                    </div>
                    <div class="wf-form-group" id="wfCronGroup" style="flex:1; display:${workflow?.trigger_type === 'scheduled' ? 'block' : 'none'}">
                        <label class="wf-label">Cron Expression</label>
                        <input id="wfBuilderCron" class="wf-input" type="text" placeholder="0 8 * * 1-5" value="${escapeHtml((workflow as any)?.schedule_cron || '')}">
                    </div>
                </div>
            </div>

            <!-- Nodes Builder -->
            <div class="wf-form-section">
                <div class="wf-nodes-header">
                    <span class="wf-section-title">🔗 Pipeline Nodes</span>
                    <div class="wf-vars-hint">Variables: <code>{{START}}</code> · <code>{{node_N_output}}</code></div>
                </div>
                <div id="wfNodesList" class="wf-nodes-list"></div>
                <button class="wf-btn wf-btn-add-node" id="btnAddNode">＋ Thêm Node</button>
            </div>
        </div>`;

        // Show/hide cron field
        const triggerSel = wrapper.querySelector('#wfBuilderTrigger') as HTMLSelectElement;
        const cronGroup = wrapper.querySelector('#wfCronGroup') as HTMLElement;
        triggerSel?.addEventListener('change', () => {
            if (cronGroup) cronGroup.style.display = triggerSel.value === 'scheduled' ? 'block' : 'none';
        });

        // Render existing nodes
        const nodesList = wrapper.querySelector('#wfNodesList') as HTMLElement;
        let nodeData = [...nodes];

        const renderNodes = () => {
            if (!nodesList) return;
            nodesList.innerHTML = '';
            nodeData.forEach((node, idx) => {
                const nodeEl = document.createElement('div');
                nodeEl.className = 'wf-node-card';
                nodeEl.setAttribute('data-idx', String(idx));
                nodeEl.innerHTML = `
                <div class="wf-node-header">
                    <div class="wf-node-num">${idx + 1}</div>
                    <input class="wf-input wf-node-name" placeholder="Tên bước" value="${escapeHtml(node.name || '')}" data-field="name" data-idx="${idx}">
                    <select class="wf-input wf-node-type wf-select-sm" data-field="node_type" data-idx="${idx}">
                        <option value="llm" ${(node as any).node_type === 'llm' || !(node as any).node_type ? 'selected' : ''}>🧠 LLM</option>
                        <option value="rag" ${(node as any).node_type === 'rag' ? 'selected' : ''}>🔍 RAG</option>
                        <option value="doc_writer" ${(node as any).node_type === 'doc_writer' ? 'selected' : ''}>✍️ Doc Writer</option>
                    </select>
                    <button class="wf-btn-icon wf-btn-remove" data-remove="${idx}" title="Xóa node">✕</button>
                </div>
                <div class="wf-node-prompt-wrap">
                    <label class="wf-label wf-label-sm">System Prompt / Instructions</label>
                    <textarea class="wf-input wf-node-prompt" placeholder="Hướng dẫn cho AI. Dùng {{START}} cho dữ liệu ban đầu, {{node_1_output}} cho kết quả bước 1..." data-field="system_prompt" data-idx="${idx}">${escapeHtml(node.system_prompt || '')}</textarea>
                </div>
                <div class="wf-node-footer">
                    <div class="wf-form-group wf-node-model">
                        <label class="wf-label wf-label-sm">Model Override (tuỳ chọn)</label>
                        <input class="wf-input wf-input-sm" placeholder="Vd: gemma3:12b" value="${escapeHtml(node.model_override || '')}" data-field="model_override" data-idx="${idx}">
                    </div>
                </div>`;

                // Remove node
                nodeEl.querySelector('[data-remove]')?.addEventListener('click', (e) => {
                    const removeIdx = parseInt((e.currentTarget as HTMLElement).getAttribute('data-remove') || '0');
                    nodeData.splice(removeIdx, 1);
                    // Renumber
                    nodeData = nodeData.map((n, i) => ({ ...n, step_order: i + 1 }));
                    renderNodes();
                });

                // Sync field changes
                nodeEl.querySelectorAll('[data-field]').forEach(el => {
                    el.addEventListener('input', (e) => {
                        const field = (e.target as HTMLElement).getAttribute('data-field') as keyof AIWorkflowNode;
                        const elIdx = parseInt((e.target as HTMLElement).getAttribute('data-idx') || '0');
                        (nodeData[elIdx] as any)[field] = (e.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value;
                    });
                    el.addEventListener('change', (e) => {
                        const field = (e.target as HTMLElement).getAttribute('data-field') as keyof AIWorkflowNode;
                        const elIdx = parseInt((e.target as HTMLElement).getAttribute('data-idx') || '0');
                        (nodeData[elIdx] as any)[field] = (e.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value;
                    });
                });

                nodesList.appendChild(nodeEl);
            });
        };

        renderNodes();

        // Add node button
        wrapper.querySelector('#btnAddNode')?.addEventListener('click', () => {
            nodeData.push({
                step_order: nodeData.length + 1,
                name: `Step ${nodeData.length + 1}`,
                node_type: 'llm',
                system_prompt: '',
                model_override: null,
            } as any);
            renderNodes();
        });

        kpOpenModal({
            title: isEdit ? `✏️ Sửa Workflow: ${workflow?.name}` : '＋ Tạo Workflow Mới',
            content: wrapper,
            okText: isEdit ? 'Lưu thay đổi' : 'Tạo Workflow',
            contentStyles: { maxWidth: '720px', width: '90vw' },
            onOk: async () => {
                const name = (wrapper.querySelector('#wfBuilderName') as HTMLInputElement)?.value?.trim();
                const description = (wrapper.querySelector('#wfBuilderDesc') as HTMLTextAreaElement)?.value?.trim() || '';
                const trigger_type = (wrapper.querySelector('#wfBuilderTrigger') as HTMLSelectElement)?.value;
                const schedule_cron = (wrapper.querySelector('#wfBuilderCron') as HTMLInputElement)?.value?.trim() || null;

                if (!name) return { error: 'Vui lòng nhập tên workflow.' };

                // Collect final node values from DOM
                const finalNodes = nodeData.map((n, i) => {
                    const nameInput = wrapper.querySelector(`[data-field="name"][data-idx="${i}"]`) as HTMLInputElement;
                    const typeSelect = wrapper.querySelector(`[data-field="node_type"][data-idx="${i}"]`) as HTMLSelectElement;
                    const promptArea = wrapper.querySelector(`[data-field="system_prompt"][data-idx="${i}"]`) as HTMLTextAreaElement;
                    const modelInput = wrapper.querySelector(`[data-field="model_override"][data-idx="${i}"]`) as HTMLInputElement;
                    return {
                        step_order: i + 1,
                        name: nameInput?.value?.trim() || n.name,
                        node_type: typeSelect?.value || 'llm',
                        system_prompt: promptArea?.value?.trim() || n.system_prompt,
                        model_override: modelInput?.value?.trim() || null,
                        input_vars: [],
                    };
                });

                if (finalNodes.length === 0) return { error: 'Workflow cần ít nhất 1 node.' };

                try {
                    const body = { name, description, trigger_type, schedule_cron, nodes: finalNodes };
                    const url = isEdit ? `${API}/workflows/${workflow?.id}` : `${API}/workflows`;
                    const method = isEdit ? 'PUT' : 'POST';
                    const res = await authFetch(url, {
                        method,
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(body),
                    });
                    if (!res.ok) throw new Error(await res.text());
                    showToast(isEdit ? 'Đã cập nhật workflow!' : 'Đã tạo workflow mới!', 'success');
                    this.loadWorkflowsPage();
                    return true;
                } catch (e) {
                    return { error: (e as Error).message };
                }
            }
        });
    }

    // ── Template Gallery ────────────────────────────────────────────────────────

    private openTemplateGallery(): void {
        const wrapper = document.createElement('div');
        wrapper.className = 'wf-template-gallery';
        wrapper.innerHTML = `
        <div class="wf-gallery-intro">Chọn một template để tạo nhanh workflow. Bạn có thể tuỳ chỉnh sau khi tạo.</div>
        <div class="wf-gallery-grid" id="galleryGrid"></div>`;

        const grid = wrapper.querySelector('#galleryGrid') as HTMLElement;
        WORKFLOW_TEMPLATES.forEach((tpl, idx) => {
            const card = document.createElement('div');
            card.className = 'wf-template-card';
            card.innerHTML = `
            <div class="wf-tpl-icon">${tpl.icon}</div>
            <div class="wf-tpl-name">${escapeHtml(tpl.name)}</div>
            <div class="wf-tpl-desc">${escapeHtml(tpl.description)}</div>
            <div class="wf-tpl-nodes">${tpl.nodes.length} nodes · ${this.getTriggerBadge(tpl.trigger_type).label}</div>
            <button class="wf-btn wf-btn-primary wf-btn-sm" data-tpl="${idx}">Dùng Template này</button>`;
            card.querySelector('button')?.addEventListener('click', () => {
                // Pre-fill builder with template data
                const wfLike = {
                    name: tpl.name,
                    description: tpl.description,
                    trigger_type: tpl.trigger_type,
                    schedule_cron: (tpl as any).schedule_cron || null,
                    nodes: tpl.nodes,
                } as any;
                // Close gallery and open builder
                document.querySelector('.kp-modal-overlay')?.remove();
                setTimeout(() => this.openWorkflowBuilder(wfLike), 50);
            });
            grid.appendChild(card);
        });

        kpOpenModal({
            title: '📚 Template Gallery',
            content: wrapper,
            okText: 'Đóng',
            contentStyles: { maxWidth: '800px', width: '90vw' },
            onOk: async () => true,
        });
    }

    // ── Run Modal with Inline Execution Tracker ──────────────────────────────

    private async openRunModal(w: AIWorkflow): Promise<void> {
        // If we don't have node info, fetch it
        let workflowFull = w;
        if (!(w as any).nodes) {
            try {
                const res = await authFetch(`${API}/workflows/${w.id}`);
                if (res.ok) {
                    const data = await res.json();
                    workflowFull = data.workflow;
                }
            } catch (_) {}
        }
        const nodes: AIWorkflowNode[] = (workflowFull as any).nodes || [];

        const wrapper = document.createElement('div');
        wrapper.innerHTML = `
        <div class="wf-run-modal">
            <!-- Input Section -->
            <div id="wfRunInputSection">
                <div class="wf-run-desc">
                    Nhập dữ liệu khởi động. Nó sẽ được gán vào biến <code>{{START}}</code> trong tất cả các nodes.
                </div>
                <textarea id="wfRunContext" class="wf-input wf-textarea wf-textarea-lg" placeholder="Nhập yêu cầu, câu hỏi, hoặc dữ liệu đầu vào..."></textarea>

                <!-- Pipeline Preview -->
                <div class="wf-pipeline-preview">
                    ${nodes.map((n, i) => `
                    <div class="wf-pipeline-step" id="pipeStep_${i}">
                        <div class="wf-pipeline-step-num">${i + 1}</div>
                        <div class="wf-pipeline-step-info">
                            <div class="wf-pipeline-step-name">${escapeHtml(n.name)}</div>
                            <div class="wf-pipeline-step-type">${(n as any).node_type === 'rag' ? '🔍 RAG' : (n as any).node_type === 'doc_writer' ? '✍️ Doc Writer' : '🧠 LLM'}</div>
                        </div>
                        <div class="wf-pipeline-step-status wf-step-pending" id="pipeStepStatus_${i}">⏳ Chờ</div>
                    </div>`).join('<div class="wf-pipeline-arrow">↓</div>')}
                </div>
            </div>

            <!-- Execution Tracker (hidden initially) -->
            <div id="wfExecSection" style="display:none;">
                <div class="wf-exec-header">
                    <div class="wf-exec-title">🚀 Đang thực thi Workflow</div>
                    <div class="wf-exec-name">${escapeHtml(w.name)}</div>
                </div>
                <div class="wf-exec-progress" id="wfExecProgress">
                    <div class="wf-progress-bar" id="wfProgressBar" style="width:0%"></div>
                </div>
                <div class="wf-exec-nodes" id="wfExecNodes">
                    ${nodes.map((n, i) => `
                    <div class="wf-exec-node" id="execNode_${i}">
                        <div class="wf-exec-node-header">
                            <div class="wf-exec-node-num">${i + 1}</div>
                            <div class="wf-exec-node-name">${escapeHtml(n.name)}</div>
                            <div class="wf-exec-node-badge ${(n as any).node_type === 'rag' ? 'badge-rag' : 'badge-llm'}">${(n as any).node_type === 'rag' ? '🔍 RAG' : (n as any).node_type === 'doc_writer' ? '✍️ Doc Writer' : '🧠 LLM'}</div>
                            <div class="wf-exec-node-status" id="execNodeStatus_${i}">⏳</div>
                        </div>
                        <div class="wf-exec-node-output" id="execNodeOutput_${i}" style="display:none"></div>
                    </div>`).join('')}
                </div>
                <div class="wf-exec-final" id="wfExecFinal" style="display:none">
                    <div class="wf-exec-final-title">✅ Kết quả cuối cùng</div>
                    <div class="wf-exec-final-content markdown-body" id="wfExecFinalContent"></div>
                </div>
            </div>
        </div>`;

        let jobId: string | null = null;
        let isRunning = false;

        await kpOpenModal({
            title: `▶ Run: ${w.name}`,
            content: wrapper,
            okText: 'Execute Workflow',
            contentStyles: { maxWidth: '680px', width: '90vw' },
            onOk: async () => {
                if (isRunning) return true; // allow close while running
                const context = (wrapper.querySelector('#wfRunContext') as HTMLTextAreaElement)?.value?.trim();
                if (!context) return { error: 'Vui lòng nhập dữ liệu đầu vào.' };

                // Switch to execution view
                const inputSection = wrapper.querySelector('#wfRunInputSection') as HTMLElement;
                const execSection = wrapper.querySelector('#wfExecSection') as HTMLElement;
                if (inputSection) inputSection.style.display = 'none';
                if (execSection) execSection.style.display = 'block';

                // Update button
                const okBtn = document.querySelector('.kp-modal-ok') as HTMLButtonElement;
                if (okBtn) { okBtn.textContent = 'Đang chạy...'; okBtn.disabled = true; }
                isRunning = true;

                try {
                    const res = await authFetch(`${API}/workflows/${w.id}/run`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ initial_context: context }),
                    });
                    if (!res.ok) throw new Error(await res.text());
                    const data = await res.json();
                    jobId = data.job_id;
                    // run_id available in data.run_id for future use

                    // Start polling for status
                    this.startExecutionPolling(jobId!, nodes, wrapper, () => {
                        if (okBtn) { okBtn.textContent = 'Đóng'; okBtn.disabled = false; }
                    });
                    return null; // Keep modal open
                } catch (e) {
                    isRunning = false;
                    if (okBtn) { okBtn.textContent = 'Execute Workflow'; okBtn.disabled = false; }
                    if (inputSection) inputSection.style.display = 'block';
                    if (execSection) execSection.style.display = 'none';
                    return { error: (e as Error).message };
                }
            }
        });
    }

    private startExecutionPolling(jobId: string, nodes: AIWorkflowNode[], wrapper: HTMLElement, onDone: () => void): void {
        if (this.activePollingInterval) clearInterval(this.activePollingInterval);

        let attempts = 0;
        let lastNodeCount = 0;

        const interval = setInterval(async () => {
            attempts++;
            if (attempts > 600) { clearInterval(interval); return; } // 10 min max

            try {
                const res = await authFetch(`${API}/ask/jobs/${jobId}`);
                if (!res.ok) return;
                const data = await res.json();

                // Update progress from thoughts
                const thoughts = data.thoughts || [];
                const completedNodes = thoughts.filter((t: any) => t.step === 'node_complete');

                if (completedNodes.length > lastNodeCount) {
                    lastNodeCount = completedNodes.length;
                    const progress = Math.min(100, (completedNodes.length / Math.max(1, nodes.length)) * 100);
                    const bar = wrapper.querySelector('#wfProgressBar') as HTMLElement;
                    if (bar) bar.style.width = `${progress}%`;

                    // Mark completed nodes
                    completedNodes.forEach((t: any) => {
                        const nodeIdx = (t.step_order || 1) - 1;
                        const statusEl = wrapper.querySelector(`#execNodeStatus_${nodeIdx}`);
                        const outputEl = wrapper.querySelector(`#execNodeOutput_${nodeIdx}`) as HTMLElement;
                        const nodeEl = wrapper.querySelector(`#execNode_${nodeIdx}`);
                        if (statusEl) statusEl.textContent = '✅';
                        if (nodeEl) nodeEl.classList.add('exec-node-complete');
                        if (outputEl && t.output_preview) {
                            outputEl.style.display = 'block';
                            outputEl.innerHTML = `<div class="wf-exec-preview">${escapeHtml(t.output_preview)}${t.output_preview.length >= 200 ? '...' : ''}</div>`;
                        }
                    });

                    // Mark in-progress next node
                    if (completedNodes.length < nodes.length) {
                        const nextIdx = completedNodes.length;
                        const statusEl = wrapper.querySelector(`#execNodeStatus_${nextIdx}`);
                        const nodeEl = wrapper.querySelector(`#execNode_${nextIdx}`);
                        if (statusEl) statusEl.innerHTML = '<span class="wf-spinner-sm"></span>';
                        if (nodeEl) nodeEl.classList.add('exec-node-running');
                    }
                } else if (attempts === 1) {
                    // Mark first node as running immediately
                    const statusEl = wrapper.querySelector(`#execNodeStatus_0`);
                    const nodeEl = wrapper.querySelector(`#execNode_0`);
                    if (statusEl) statusEl.innerHTML = '<span class="wf-spinner-sm"></span>';
                    if (nodeEl) nodeEl.classList.add('exec-node-running');
                }

                if (data.status === 'completed') {
                    clearInterval(interval);
                    const bar = wrapper.querySelector('#wfProgressBar') as HTMLElement;
                    if (bar) bar.style.width = '100%';

                    // Mark all nodes complete
                    nodes.forEach((_, i) => {
                        const statusEl = wrapper.querySelector(`#execNodeStatus_${i}`);
                        const nodeEl = wrapper.querySelector(`#execNode_${i}`);
                        if (statusEl) statusEl.textContent = '✅';
                        if (nodeEl) { nodeEl.classList.remove('exec-node-running'); nodeEl.classList.add('exec-node-complete'); }
                    });

                    // Show final output
                    const result = data.result;
                    const answer = typeof result === 'string' ? result : (result?.answer || '');
                    const finalSection = wrapper.querySelector('#wfExecFinal') as HTMLElement;
                    const finalContent = wrapper.querySelector('#wfExecFinalContent') as HTMLElement;
                    if (finalSection) finalSection.style.display = 'block';
                    if (finalContent) finalContent.innerHTML = renderMarkdown(answer);

                    showToast('Workflow hoàn thành!', 'success');
                    onDone();

                } else if (data.status === 'failed') {
                    clearInterval(interval);
                    // Find running node and mark as failed
                    nodes.forEach((_, i) => {
                        const nodeEl = wrapper.querySelector(`#execNode_${i}`);
                        if (nodeEl?.classList.contains('exec-node-running')) {
                            const statusEl = wrapper.querySelector(`#execNodeStatus_${i}`);
                            if (statusEl) statusEl.textContent = '❌';
                            nodeEl.classList.remove('exec-node-running');
                            nodeEl.classList.add('exec-node-failed');
                        }
                    });
                    showToast('Workflow thất bại: ' + (data.error || 'Unknown error'), 'error');
                    onDone();
                }

            } catch (_) { /* ignore polling errors */ }
        }, 1500);

        this.activePollingInterval = interval;
    }

    // ── Run History Modal ────────────────────────────────────────────────────

    private async openRunHistory(w: AIWorkflow): Promise<void> {
        const wrapper = document.createElement('div');
        wrapper.innerHTML = '<div class="wf-loading"><div class="wf-spinner"></div><span>Đang tải lịch sử...</span></div>';

        kpOpenModal({
            title: `📋 Lịch sử runs: ${w.name}`,
            content: wrapper,
            okText: 'Đóng',
            contentStyles: { maxWidth: '700px', width: '90vw' },
            onOk: async () => true,
        });

        try {
            const res = await authFetch(`${API}/workflows/${w.id}/runs?limit=20`);
            if (!res.ok) throw new Error('Không thể tải lịch sử.');
            const data = await res.json();
            const runs: WorkflowRun[] = data.runs || [];

            if (runs.length === 0) {
                wrapper.innerHTML = `<div class="wf-empty-state" style="padding:40px"><div class="wf-empty-icon">📭</div><div class="wf-empty-title">Chưa có lần chạy nào</div></div>`;
                return;
            }

            wrapper.innerHTML = `
            <div class="wf-history-list">
                ${runs.map(run => {
                    const statusIcon = { queued: '⏳', running: '🔄', completed: '✅', failed: '❌' }[run.status] || '?';
                    const dt = run.created_at ? new Date(run.created_at).toLocaleString('vi-VN') : '—';
                    const duration = run.started_at && run.finished_at
                        ? Math.round((new Date(run.finished_at).getTime() - new Date(run.started_at).getTime()) / 1000) + 's'
                        : '—';
                    return `
                    <div class="wf-history-item ${run.status}">
                        <div class="wf-history-item-header">
                            <span class="wf-history-status">${statusIcon} ${run.status}</span>
                            <span class="wf-history-time">${dt}</span>
                            <span class="wf-history-dur">⏱ ${duration}</span>
                            <span class="wf-history-trigger">${run.trigger_type}</span>
                        </div>
                        <div class="wf-history-context">${escapeHtml((run.initial_context || '').substring(0, 100))}${(run.initial_context || '').length > 100 ? '...' : ''}</div>
                        ${run.final_output ? `<div class="wf-history-output markdown-body">${renderMarkdown(run.final_output.substring(0, 500))}${run.final_output.length > 500 ? '...' : ''}</div>` : ''}
                        ${run.error ? `<div class="wf-history-error">❌ ${escapeHtml(run.error.substring(0, 300))}</div>` : ''}
                    </div>`;
                }).join('')}
            </div>`;
        } catch (e) {
            wrapper.innerHTML = `<div class="wf-empty-state"><div class="wf-empty-icon">⚠️</div><div>${escapeHtml((e as Error).message)}</div></div>`;
        }
    }

    // ── Delete ────────────────────────────────────────────────────────────────

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
        } catch (e) {
            showToast((e as Error).message, 'error');
        }
    }
}
