import { API, authFetch } from './client';
import { Task } from './models';
import { showToast } from './ui';

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
                showToast('Đã đẩy lệnh quét thành công', 'success');
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
                const res = await authFetch(`${API}/tasks/${id}/status`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'approved' })
                });
                if (!res.ok) throw new Error(`Duyệt thất bại`);
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
            if (!confirm('Xóa task này?')) return;
            try {
                const res = await authFetch(`${API}/tasks/${id}`, { method: 'DELETE' });
                if (!res.ok) throw new Error('Xóa thất bại');
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
            if (!confirm(`Duyệt ${this.selectedIds.length} tasks đã chọn?`)) return;
            
            showToast(`Đang duyệt ${this.selectedIds.length} tasks...`, 'info');
            for (const id of this.selectedIds) {
                await this.approveTask(id, true);
            }
            this.selectedIds = [];
            showToast('Đã duyệt xong hàng loạt', 'success');
            this.loadTasks();
            this.loadTasksCount();
        },

        async bulkRejectTasks() {
            if (this.selectedIds.length === 0) return;
            if (!confirm(`Xóa ${this.selectedIds.length} tasks đã chọn?`)) return;

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
            this.loadTasks();
            this.loadTasksCount();
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
        }
    };
}