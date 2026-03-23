import { API, authFetch } from './client';
import { Task } from './models';
import { showToast, kpOpenModal, kpConfirm } from './ui';

export function TasksAlpine() {
    return {
        tasks: [] as Task[],
        selectedIds: [] as string[],
        isLoading: false,
        includeSubmitted: false,
        slackDays: 1,
        confluenceDays: 1,

        async init() {
            await this.loadTasks();
            await this.loadTasksCount();
            // Gắn event listener để router từ main.ts có thể yêu cầu refresh
            document.addEventListener('kp-refresh-tasks', () => {
                this.loadTasks();
                this.loadTasksCount();
            });
        },

        async loadTasks() {
            this.isLoading = true;
            this.selectedIds = [];
            try {
                const query = this.includeSubmitted ? '?limit=50' : '?limit=50&status=pending';
                const res = await authFetch(`${API}/tasks${query}`);
                if (!res.ok) throw new Error('Failed to load tasks');
                const data = await res.json() as { tasks: Task[] };
                this.tasks = data.tasks || [];
            } catch (err) {
                const error = err as Error;
                console.error(error);
                showToast('Lỗi tải danh sách task', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        async loadTasksCount() {
            try {
                const res = await authFetch(`${API}/tasks/count`);
                if (!res.ok) return;
                const data = await res.json() as { total_pending: number };
                // Cập nhật State Global của Alpine
                const alpine = (window as any).Alpine;
                if (alpine && alpine.store('badges')) {
                    alpine.store('badges').tasks = data.total_pending || 0;
                }
            } catch (e) {
                console.error('Error loading tasks count:', e);
            }
        },

        async triggerScan() {
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
                this.loadTasks();
                this.loadTasksCount();
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            }
        },

        toggleSelection(id: string) {
            const idx = this.selectedIds.indexOf(id);
            if (idx > -1) this.selectedIds.splice(idx, 1);
            else this.selectedIds.push(id);
        },

        async approveTask(id: string, skipReload = false) {
            try {
                console.log(`Task: Approving ${id}...`);
                const res = await authFetch(`${API}/tasks/${id}/status`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'approved' })
                });
                console.log(`Task: Approve ${id} Response:`, res.status, res.statusText);
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    throw new Error(`Duyệt thất bại: ${errorData.detail || res.statusText}`);
                }
                if (!skipReload) {
                    showToast('Đã duyệt thành công', 'success');
                    this.loadTasks();
                    this.loadTasksCount();
                }
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            }
        },

        async deleteTask(id: string) {
            if (!await kpConfirm({ 
                title: 'Xóa Task', 
                message: 'Bạn có chắc chắn muốn xóa task này?', 
                danger: true 
            })) return;
            try {
                console.log(`Task: Deleting ${id}...`);
                const res = await authFetch(`${API}/tasks/${id}`, { method: 'DELETE' });
                console.log(`Task: Delete ${id} Response:`, res.status, res.statusText);
                if (!res.ok) {
                    const errorData = await res.json().catch(() => ({}));
                    throw new Error(`Xóa thất bại: ${errorData.detail || res.statusText}`);
                }
                showToast('Đã xóa task', 'success');
                this.loadTasks();
                this.loadTasksCount();
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            }
        },

        async bulkConfirmTasks() {
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
        },

        async bulkRejectTasks() {
            if (this.selectedIds.length === 0) return;
            if (!await kpConfirm({ 
                title: 'Xóa hàng loạt', 
                message: `Bạn có chắc muốn xóa ${this.selectedIds.length} tasks đã chọn?`, 
                danger: true 
            })) return;

            showToast(`Đang xóa ${this.selectedIds.length} tasks...`, 'info');
            for (const id of this.selectedIds) {
                try {
                    await authFetch(`${API}/tasks/${id}`, { method: 'DELETE' });
                } catch (e) {
                    console.error('Error deleting task:', id, e);
                }
            }
            this.selectedIds = [];
            showToast('Đã xóa xong hàng loạt', 'success');
            await this.loadTasks();
            await this.loadTasksCount();
        },

        clearSelection() {
            this.selectedIds = [];
        },

        formatDate(dateStr: string) {
            if (!dateStr) return 'N/A';
            try {
                const d = new Date(dateStr);
                return d.toLocaleString('vi-VN');
            } catch (e) { return dateStr; }
        },

        escapeHtml(unsafe: string) {
            if (!unsafe) return '';
            return String(unsafe)
                 .replace(/&/g, "&amp;")
                 .replace(/</g, "&lt;")
                 .replace(/>/g, "&gt;")
                 .replace(/"/g, "&quot;")
                 .replace(/'/g, "&#039;");
        },

        viewTaskDetails(task: any) {
            const body = document.createElement('div');
            body.className = 'kp-modal-form';

            const meta = task.meta || {};
            const desc = task.description || meta.description || '';
            const assignee = task.suggested_assignee || meta.assignee || '';
            const issueType = task.issue_type || meta.issue_type || 'Task';
            const parentKey = task.jira_project || meta.parent_key || meta.parent_id || '';
            const evidence = meta.evidence || task.source_summary || '';
            
            const typeOptions = ['Task', 'Story', 'Bug', 'Epic', 'Sub-task'].map(t => 
                `<option value="${t}" ${issueType === t ? 'selected' : ''}>${t}</option>`
            ).join('');

            body.innerHTML = `
                <div style="display: flex; flex-direction: column; gap: 16px;">
                    <div>
                        <label class="kp-modal-label" style="font-size:11px;font-weight:700;color:var(--text-dim);text-transform:uppercase;">Tiêu đề (Title)</label>
                        <input type="text" id="editTaskTitle" class="admin-input" style="width: 100%; font-weight: 600;" value="${this.escapeHtml(task.title)}">
                    </div>
                    
                    <div style="display: flex; gap: 12px; flex-wrap: wrap;">
                        <div style="flex: 1; min-width: 120px;">
                            <label class="kp-modal-label" style="font-size:11px;font-weight:700;color:var(--text-dim);text-transform:uppercase;">Loại Issue</label>
                            <select id="editTaskType" class="admin-input" style="width: 100%">
                                <option value="">-- Chọn --</option>
                                ${typeOptions}
                            </select>
                        </div>
                        <div style="flex: 1; min-width: 120px;">
                            <label class="kp-modal-label" style="font-size:11px;font-weight:700;color:var(--text-dim);text-transform:uppercase;">Assignee</label>
                            <input type="text" id="editTaskAssignee" class="admin-input" style="width: 100%" placeholder="Tên hoặc email" value="${this.escapeHtml(assignee)}">
                        </div>
                        <div style="flex: 1; min-width: 120px;">
                            <label class="kp-modal-label" style="font-size:11px;font-weight:700;color:var(--text-dim);text-transform:uppercase;">Parent Key</label>
                            <input type="text" id="editTaskParent" class="admin-input" style="width: 100%" placeholder="VD: KP-123" value="${this.escapeHtml(parentKey)}">
                        </div>
                    </div>

                    <div>
                        <label class="kp-modal-label" style="font-size:11px;font-weight:700;color:var(--text-dim);text-transform:uppercase;">Mô tả chi tiết (Description)</label>
                        <textarea id="editTaskDesc" class="admin-input" style="width: 100%; height: 180px; resize: vertical; font-family: monospace; font-size: 13px; line-height: 1.6;">${this.escapeHtml(desc)}</textarea>
                    </div>
                    
                    ${evidence ? `
                    <div style="border-top: 1px dashed var(--border); padding-top: 16px;">
                        <div style="font-size: 11px; color: var(--text-dim); text-transform: uppercase; font-weight: 800; margin-bottom: 8px;">Trích dẫn gốc (Evidence)</div>
                        <div style="font-size: 13px; line-height: 1.5; color: var(--text-muted); background: var(--bg); padding: 12px; border-radius: 8px; border-left: 3px solid var(--accent); font-style: italic;">"${this.escapeHtml(evidence)}"</div>
                    </div>` : ''}
                </div>
            `;

            kpOpenModal({
                title: '✏️ Chỉnh sửa & Duyệt Task',
                content: body,
                okText: '💾 Lưu & Duyệt',
                onOk: async () => {
                    const newTitle = (document.getElementById('editTaskTitle') as HTMLInputElement).value.trim();
                    const newType = (document.getElementById('editTaskType') as HTMLSelectElement).value;
                    const newAssignee = (document.getElementById('editTaskAssignee') as HTMLInputElement).value.trim();
                    const newParent = (document.getElementById('editTaskParent') as HTMLInputElement).value.trim();
                    const newDesc = (document.getElementById('editTaskDesc') as HTMLTextAreaElement).value.trim();

                    try {
                        // 1. Cập nhật thông tin Task
                        const updateRes = await authFetch(`${API}/tasks/${task.id}`, {
                            method: 'PUT',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                title: newTitle,
                                description: newDesc,
                                suggested_assignee: newAssignee,
                                jira_project: newParent,
                                meta: { ...meta, description: newDesc, issue_type: newType, assignee: newAssignee, parent_key: newParent }
                            })
                        });
                        if (!updateRes.ok) console.warn('Lỗi cập nhật chi tiết Task. Vẫn tiếp tục duyệt.');
                        
                        // 2. Duyệt Task
                        await this.approveTask(task.id, false);
                        return true;
                    } catch (e) {
                        return { error: (e as Error).message };
                    }
                }
            });
        }
    };
}