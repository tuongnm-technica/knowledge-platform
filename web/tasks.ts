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
                const data = await res.json();
                this.tasks = data.tasks || [];
            } catch (e: any) {
                console.error(e);
                showToast('Lỗi tải danh sách task', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        async loadTasksCount() {
            try {
                const res = await authFetch(`${API}/tasks/count`);
                if (!res.ok) return;
                const data = await res.json();
                // Cập nhật State Global của Alpine
                (window as any).Alpine.store('badges').tasks = data.total_pending || 0;
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
            } catch (e: any) { showToast(e.message, 'error'); }
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
            } catch (e: any) { showToast(e.message, 'error'); }
        },

        async deleteTask(id: string) {
            if (!confirm('Xóa task này?')) return;
            try {
                const res = await authFetch(`${API}/tasks/${id}`, { method: 'DELETE' });
                if (!res.ok) throw new Error('Xóa thất bại');
                showToast('Đã xóa task', 'success');
                this.loadTasks();
                this.loadTasksCount();
            } catch (e: any) { showToast(e.message, 'error'); }
        },

        async bulkConfirmTasks() {
            if (this.selectedIds.length === 0) return;
            if (!confirm(`Duyệt ${this.selectedIds.length} task đã chọn?`)) return;
            await Promise.all(this.selectedIds.map(id => this.approveTask(id, true)));
            showToast('Đã duyệt các task được chọn', 'success');
            this.loadTasks();
            this.loadTasksCount();
        },

        async bulkRejectTasks() {
            if (this.selectedIds.length === 0) return;
            if (!confirm(`Xóa ${this.selectedIds.length} task đã chọn?`)) return;
            await Promise.all(this.selectedIds.map(id => authFetch(`${API}/tasks/${id}`, { method: 'DELETE' })));
            showToast('Đã xóa các task được chọn', 'success');
            this.loadTasks();
            this.loadTasksCount();
        },

        clearSelection() { this.selectedIds = []; },

        formatDate(d: string) {
            if (!d) return '';
            return new Date(d).toLocaleString('vi-VN');
        }
    };
}