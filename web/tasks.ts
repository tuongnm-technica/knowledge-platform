import { API, authFetch } from './client';
import { Task } from './models';
import { showToast, kpOpenModal, kpConfirm } from './ui';

export class TasksModule {
    private tasks: Task[] = [];
    private selectedIds: string[] = [];
    private isLoading = false;
    private includeSubmitted = false;
    private slackDays = 1;
    private confluenceDays = 1;

    constructor() {
        // Initial setup
        document.addEventListener('kp-refresh-tasks', () => {
            this.loadTasks();
            this.loadTasksCount();
        });
    }

    public async init() {
        await this.loadTasks();
        await this.loadTasksCount();
        this.bindGlobalActions();
    }

    public async loadTasks() {
        this.isLoading = true;
        this.selectedIds = [];
        this.render(); // Render loading state
        try {
            const query = this.includeSubmitted ? '?limit=50' : '?limit=50&status=pending';
            const res = await authFetch(`${API}/tasks${query}`);
            if (!res.ok) throw new Error('Failed to load tasks');
            const data = await res.json() as { tasks: Task[] };
            this.tasks = data.tasks || [];
        } catch (err) {
            console.error(err);
            showToast('Lỗi tải danh sách task', 'error');
        } finally {
            this.isLoading = false;
            this.render();
        }
    }

    public async loadTasksCount() {
        try {
            const res = await authFetch(`${API}/tasks/count`);
            if (!res.ok) return;
            const data = await res.json() as { total_pending: number };
            // Update Alpine store for badges (compat layer)
            const alpine = (window as any).Alpine;
            if (alpine?.store('badges')) {
                alpine.store('badges').tasks = data.total_pending || 0;
            }
            // Update text in UI if visible
            const countEl = document.querySelector('#tasks-open-count');
            if (countEl) countEl.textContent = String(data.total_pending || 0);
        } catch (e) {
            console.error('Error loading tasks count:', e);
        }
    }

    public async triggerScan() {
        showToast('Đang quét dữ liệu từ Slack & Confluence...', 'info');
        try {
            const res = await authFetch(`${API}/tasks/scan`, { 
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ slack_days: this.slackDays, confluence_days: this.confluenceDays })
            });
            if (!res.ok) throw new Error('Lỗi khi quét');
            const data = await res.json() as { status: string, stats?: any };
            
            let message = 'Đã quét xong.';
            if (data.stats) {
                const s = data.stats;
                const slack = s.slack_tasks_created || 0;
                const confluence = s.confluence_tasks_created || 0;
                message = `Quét hoàn tất: +${slack} task từ Slack, +${confluence} từ Confluence.`;
            }
            
            showToast(message, 'success');
            await this.loadTasks();
            await this.loadTasksCount();
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    private toggleSelection(id: string) {
        const idx = this.selectedIds.indexOf(id);
        if (idx > -1) this.selectedIds.splice(idx, 1);
        else this.selectedIds.push(id);
        this.render();
    }

    public async approveTask(id: string, skipReload = false) {
        try {
            const res = await authFetch(`${API}/tasks/${id}/status`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'approved' })
            });
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(`Duyệt thất bại: ${errorData.detail || res.statusText}`);
            }
            if (!skipReload) {
                showToast('Đã duyệt thành công', 'success');
                await this.loadTasks();
                await this.loadTasksCount();
            }
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    public async deleteTask(id: string) {
        if (!await kpConfirm({ 
            title: 'Xóa Task', 
            message: 'Bạn có chắc chắn muốn xóa task này?', 
            danger: true 
        })) return;
        try {
            const res = await authFetch(`${API}/tasks/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Xóa thất bại');
            showToast('Đã xóa task', 'success');
            await this.loadTasks();
            await this.loadTasksCount();
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    private async bulkConfirmTasks() {
        if (this.selectedIds.length === 0) return;
        if (!await kpConfirm({ 
            title: 'Duyệt hàng loạt', 
            message: `Bạn có chắc muốn duyệt ${this.selectedIds.length} tasks đã chọn?` 
        })) return;
        
        showToast(`Đang duyệt ${this.selectedIds.length} tasks...`, 'info');
        for (const id of this.selectedIds) {
            await this.approveTask(id, true);
        }
        this.selectedIds = [];
        showToast('Đã duyệt xong hàng loạt', 'success');
        await this.loadTasks();
        await this.loadTasksCount();
    }

    private async bulkRejectTasks() {
        if (this.selectedIds.length === 0) return;
        if (!await kpConfirm({ 
            title: 'Xóa hàng loạt', 
            message: `Bạn có chắc muốn xóa ${this.selectedIds.length} tasks đã chọn?`, 
            danger: true 
        })) return;

        showToast(`Đang xóa ${this.selectedIds.length} tasks...`, 'info');
        for (const id of this.selectedIds) {
            try { await authFetch(`${API}/tasks/${id}`, { method: 'DELETE' }); } catch (e) {}
        }
        this.selectedIds = [];
        showToast('Đã xóa xong hàng loạt', 'success');
        await this.loadTasks();
        await this.loadTasksCount();
    }

    private clearSelection() {
        this.selectedIds = [];
        this.render();
    }

    private formatDate(dateStr: string) {
        if (!dateStr) return 'N/A';
        try { return new Date(dateStr).toLocaleString('vi-VN'); } catch (e) { return dateStr; }
    }

    private escapeHtml(unsafe: string) {
        if (!unsafe) return '';
        return String(unsafe).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
    }

    private viewTaskDetails(task: any) {
        const body = document.createElement('div');
        body.className = 'kp-modal-form';
        const meta = task.meta || {};
        const desc = task.description || meta.description || '';
        const assignee = task.suggested_assignee || meta.assignee || '';
        const issueType = task.issue_type || meta.issue_type || 'Task';
        const parentKey = task.jira_project || meta.parent_key || '';
        const evidence = meta.evidence || task.source_summary || '';
        
        const typeOptions = ['Task', 'Story', 'Bug', 'Epic', 'Sub-task'].map(t => 
            `<option value="${t}" ${issueType === t ? 'selected' : ''}>${t}</option>`
        ).join('');

        body.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 16px;">
                <div>
                    <label class="kp-modal-label">Tiêu đề (Title)</label>
                    <input type="text" id="editTaskTitle" class="admin-input" style="width: 100%; font-weight: 600;" value="${this.escapeHtml(task.title)}">
                </div>
                <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 120px;">
                        <label class="kp-modal-label">Loại Issue</label>
                        <select id="editTaskType" class="admin-input" style="width: 100%">
                            <option value="">-- Chọn --</option>
                            ${typeOptions}
                        </select>
                    </div>
                    <div style="flex: 1; min-width: 120px;">
                        <label class="kp-modal-label">Assignee</label>
                        <input type="text" id="editTaskAssignee" class="admin-input" style="width: 100%" value="${this.escapeHtml(assignee)}">
                    </div>
                    <div style="flex: 1; min-width: 120px;">
                        <label class="kp-modal-label">Parent Key</label>
                        <input type="text" id="editTaskParent" class="admin-input" style="width: 100%" value="${this.escapeHtml(parentKey)}">
                    </div>
                </div>
                <div>
                    <label class="kp-modal-label">Mô tả chi tiết</label>
                    <textarea id="editTaskDesc" class="admin-input" style="width: 100%; height: 180px; resize: vertical; font-family: monospace;">${this.escapeHtml(desc)}</textarea>
                </div>
                ${evidence ? `<div style="border-top: 1px dashed var(--border); padding-top: 16px;">
                    <div style="font-size: 11px; color: var(--text-dim); text-transform: uppercase; font-weight: 800;">Evidence</div>
                    <div style="font-size: 13px; color: var(--text-muted); background: var(--bg); padding: 12px; border-radius: 8px; border-left: 3px solid var(--accent); font-style: italic;">"${this.escapeHtml(evidence)}"</div>
                </div>` : ''}
            </div>`;

        kpOpenModal({
            title: '✏️ Chỉnh sửa & Duyệt Task',
            content: body, okText: '💾 Lưu & Duyệt',
            onOk: async () => {
                const updated = {
                    title: (document.getElementById('editTaskTitle') as HTMLInputElement).value.trim(),
                    description: (document.getElementById('editTaskDesc') as HTMLTextAreaElement).value.trim(),
                    suggested_assignee: (document.getElementById('editTaskAssignee') as HTMLInputElement).value.trim(),
                    jira_project: (document.getElementById('editTaskParent') as HTMLInputElement).value.trim(),
                };
                try {
                    await authFetch(`${API}/tasks/${task.id}`, {
                        method: 'PUT', headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(updated)
                    });
                    await this.approveTask(task.id, false);
                    return true;
                } catch (e) { return { error: (e as Error).message }; }
            }
        });
    }

    private render() {
        const listDiv = document.querySelector('.task-list-flex');
        const emptyDiv = document.querySelector('#tasks-empty-state') as HTMLElement;
        const loadingDiv = document.querySelector('#tasks-loading') as HTMLElement;
        const bulkBar = document.querySelector('.bulk-actions-bar') as HTMLElement;

        if (!listDiv || !emptyDiv || !loadingDiv || !bulkBar) return;

        loadingDiv.style.display = this.isLoading ? 'block' : 'none';
        
        if (this.isLoading) {
            listDiv.innerHTML = '';
            emptyDiv.style.display = 'none';
            bulkBar.style.display = 'none';
            return;
        }

        if (this.tasks.length === 0) {
            listDiv.innerHTML = '';
            emptyDiv.style.display = 'flex';
            bulkBar.style.display = 'none';
        } else {
            emptyDiv.style.display = 'none';
            bulkBar.style.display = this.selectedIds.length > 0 ? 'flex' : 'none';
            const countLabel = bulkBar.querySelector('.selection-count');
            if (countLabel) countLabel.textContent = `${this.selectedIds.length} selected`;

            listDiv.innerHTML = this.tasks.map(task => {
                const isSelected = this.selectedIds.includes(task.id);
                const sourceEmoji = task.source === 'confluence' ? '📘' : (task.source === 'slack' ? '💬' : '🤖');
                return `
                    <div class="task-card-modern ${isSelected ? 'selected' : ''}" data-id="${task.id}">
                        <div class="task-checkbox ${isSelected ? 'checked' : ''}" data-id="${task.id}">
                            ${isSelected ? '✓' : ''}
                        </div>
                        <div class="task-card-body">
                            <div class="task-card-header">
                                <div class="task-card-title">${this.escapeHtml(task.title || 'Untitled')}</div>
                                <div class="task-status-wrap">
                                    <span class="status-badge status-${task.status || 'pending'}">${task.status || 'pending'}</span>
                                </div>
                            </div>
                            <div class="task-card-meta">
                                <span class="source-tag">${sourceEmoji} ${(task.source || 'system').toUpperCase()}</span>
                                <span>Tạo lúc: ${this.formatDate(task.created_at)}</span>
                                ${task.meta?.issue_type ? `<span class="meta-tag type-tag">Type: ${task.meta.issue_type}</span>` : ''}
                                ${task.meta?.assignee ? `<span class="meta-tag assignee-tag">👤 ${task.meta.assignee}</span>` : ''}
                            </div>
                        </div>
                        <div class="task-card-actions">
                            ${task.status !== 'approved' ? `<button class="secondary-btn mini approve-btn" data-id="${task.id}">✅ Duyệt</button>` : ''}
                            <button class="danger-btn mini ghost-btn delete-btn" data-id="${task.id}">🗑 Xóa</button>
                        </div>
                    </div>
                `;
            }).join('');

            // Bind card event listeners
            listDiv.querySelectorAll('.task-card-modern').forEach(card => {
                const id = card.getAttribute('data-id')!;
                const task = this.tasks.find(t => t.id === id);
                card.addEventListener('click', () => this.viewTaskDetails(task));
                
                card.querySelector('.task-checkbox')?.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.toggleSelection(id);
                });
                card.querySelector('.approve-btn')?.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.approveTask(id);
                });
                card.querySelector('.delete-btn')?.addEventListener('click', (e) => {
                    e.stopPropagation();
                    this.deleteTask(id);
                });
            });
        }
    }

    private bindGlobalActions() {
        document.querySelector('#tasks-refresh-btn')?.addEventListener('click', () => this.loadTasks());
        document.querySelector('#tasks-scan-btn')?.addEventListener('click', () => this.triggerScan());
        document.querySelector('#tasks-bulk-confirm')?.addEventListener('click', () => this.bulkConfirmTasks());
        document.querySelector('#tasks-bulk-reject')?.addEventListener('click', () => this.bulkRejectTasks());
        document.querySelector('#tasks-clear-selection')?.addEventListener('click', () => this.clearSelection());
        
        const slackDaysIn = document.querySelector('#tasks-slack-days') as HTMLInputElement;
        const confDaysIn = document.querySelector('#tasks-conf-days') as HTMLInputElement;
        const showSubIn = document.querySelector('#tasks-show-submitted') as HTMLInputElement;

        slackDaysIn?.addEventListener('change', () => { this.slackDays = parseInt(slackDaysIn.value) || 1; });
        confDaysIn?.addEventListener('change', () => { this.confluenceDays = parseInt(confDaysIn.value) || 1; });
        showSubIn?.addEventListener('change', () => { 
            this.includeSubmitted = showSubIn.checked;
            this.loadTasks();
        });
    }
}