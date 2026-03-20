import { API, authFetch } from './client';
import { User, Group } from './models';
import { AuthModule } from './auth';
import { showToast, kpConfirm, kpOpenModal, _kpBuildModalField } from './ui';

export function AdminAlpine() {
    return {
        users: [] as User[],
        groups: [] as Group[],
        isLoadingUsers: false,
        isLoadingGroups: false,

        init() {
            // Chỉ load nếu đã đăng nhập
            if (!AuthModule.isAuthenticated()) return;

            // Lắng nghe sự kiện refresh từ main tab hoặc các module khác
            document.addEventListener('kp-refresh-users', () => {
                this.loadUsersTable();
                this.loadGroupsTable();
            });
            
            // Load dữ liệu lần đầu
            this.loadUsersTable();
            this.loadGroupsTable();
        },

        // ─── Quản lý Users ──────────────────────────────────────────────────
        async loadUsersTable() {
            this.isLoadingUsers = true;
            try {
                const response = await authFetch(`${API}/users`);
                if (!response.ok) throw new Error('Không thể tải danh sách User');
                const data = await response.json() as User[] | { users: User[] };
                this.users = Array.isArray(data) ? data : (data.users || []);
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            } finally {
                this.isLoadingUsers = false;
            }
        },

        openUserModal(userId: string | null = null) {
            const isEdit = !!userId;
            const existingUser = userId ? this.users.find(u => u.user_id === userId) : null;

            const body = document.createElement('div');
            body.className = 'kp-modal-form';

            const { wrap: wName, input: nameIn } = _kpBuildModalField({ 
                id: 'uName', 
                label: 'Tên hiển thị', 
                value: existingUser?.display_name || '',
                placeholder: 'Nguyễn Văn A', 
                required: true 
            });
            const { wrap: wEmail, input: emailIn } = _kpBuildModalField({ 
                id: 'uEmail', 
                label: 'Email', 
                type: 'email', 
                value: existingUser?.email || '',
                placeholder: 'user@technica.vn', 
                required: true 
            });
            const { wrap: wPwd, input: pwdIn } = _kpBuildModalField({ 
                id: 'uPwd', 
                label: isEdit ? 'Mật khẩu mới (để trống nếu không đổi)' : 'Mật khẩu', 
                type: 'password', 
                required: !isEdit 
            });
            
            body.append(wName, wEmail, wPwd);

            kpOpenModal({
                title: isEdit ? '✏️ Sửa Người dùng' : '👤 Thêm Người dùng',
                content: body,
                okText: 'Lưu',
                onOk: async () => {
                    const payload: Record<string, string> = {
                        display_name: (nameIn as HTMLInputElement).value.trim(),
                        email: (emailIn as HTMLInputElement).value.trim(),
                    };
                    const pwd = (pwdIn as HTMLInputElement).value;
                    if (pwd) payload.password = pwd;

                    try {
                        const url = isEdit ? `${API}/users/${userId}` : `${API}/users`;
                        const method = isEdit ? 'PUT' : 'POST';
                        const res = await authFetch(url, {
                            method,
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify(payload)
                        });
                        if (!res.ok) throw new Error('Lỗi lưu thông tin');
                        showToast('Lưu thông tin User thành công', 'success');
                        this.loadUsersTable();
                        return true;
                    } catch (err) {
                        const error = err as Error;
                        return { error: error.message };
                    }
                }
            });
        },

        async deleteUser(userId: string) {
            if (!await kpConfirm({ title: 'Xóa User', message: 'Bạn có chắc chắn muốn xóa user này?', danger: true })) return;
            try {
                const res = await authFetch(`${API}/users/${userId}`, { method: 'DELETE' });
                if (!res.ok) throw new Error('Không thể xóa user');
                showToast('Đã xóa user', 'success');
                this.loadUsersTable();
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            }
        },

        // ─── Quản lý Groups ─────────────────────────────────────────────────
        async loadGroupsTable() {
            this.isLoadingGroups = true;
            try {
                const response = await authFetch(`${API}/groups`);
                if (!response.ok) throw new Error('Không thể tải danh sách Group');
                const data = await response.json() as Group[] | { groups: Group[] };
                this.groups = Array.isArray(data) ? data : (data.groups || []);
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            } finally {
                this.isLoadingGroups = false;
            }
        },

        openGroupModal() {
            showToast('Tính năng thêm Group đang được phát triển', 'info');
        },

        async deleteGroup(_groupId: string) {
            showToast('Tính năng xóa Group đang được phát triển', 'warning');
        }
    };
}