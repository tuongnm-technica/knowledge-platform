import { API, authFetch } from './client';
import { User, Group } from './models';
import { AuthModule } from './auth';
import { showToast, kpConfirm, kpOpenModal, _kpBuildModalField, escapeHtml } from './ui';

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
                const resp = await authFetch(`${API}/users`);
                if (!resp.ok) throw new Error('Không thể tải danh sách User');
                const data = await resp.json() as any;
                console.log('Admin: Users API Response:', data);
                this.users = Array.isArray(data) ? data : (data.users || []);
                console.log('Admin Module: Users Loaded:', this.users.length, this.users);
                
                // Set explicitly for double-check
                if (this.users.length > 0) {
                    console.log('Admin Module: User 0 ID:', this.users[0].id);
                }
                // If the response contains groups, we can also use them to avoid double fetch
                if (data.groups && Array.isArray(data.groups) && this.groups.length === 0) {
                    this.groups = data.groups;
                }
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            } finally {
                this.isLoadingUsers = false;
            }
        },

        openUserModal(userId: string | null = null) {
            const isEdit = !!userId;
            const existingUser = userId ? this.users.find(u => u.id === userId) : null;

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

            const { wrap: wRole, input: roleIn } = _kpBuildModalField({ 
                id: 'uRole', 
                label: 'Vai trò (Role)', 
                type: 'select',
                value: existingUser?.role || 'standard',
                options: [
                    { label: 'Member (Standard)', value: 'standard' },
                    { label: 'Knowledge Architect', value: 'knowledge_architect' },
                    { label: 'PM / Product Owner', value: 'pm_po' },
                    { label: 'Business Analyst', value: 'ba_sa' },
                    { label: 'Developer / QA', value: 'dev_qa' },
                    { label: 'System Admin', value: 'system_admin' }
                ]
            });

            const { wrap: wAdmin, input: adminIn } = _kpBuildModalField({ 
                id: 'uIsAdmin', 
                label: 'Quyền quản trị hệ thống (Root Admin)', 
                type: 'checkbox',
                value: (existingUser?.is_admin ? 'true' : 'false') as any
            });
            
            // Render danh sách chọn Group dạng Checkbox Grid
            const groupsWrap = document.createElement('div');
            groupsWrap.style.marginBottom = '12px';
            groupsWrap.innerHTML = `<label class="kp-modal-label">Cơ quan / Nhóm (Groups)</label>`;
            
            const groupList = document.createElement('div');
            groupList.className = 'connector-scope-list'; // Tận dụng style grid có sẵn trong CSS
            
            const userGroupIds = existingUser?.group_ids || [];
            
            if (this.groups.length === 0) {
                groupList.innerHTML = `<div class="connector-scope-empty">Chưa có nhóm nào. Vui lòng tạo nhóm ở bảng bên dưới trước.</div>`;
            } else {
                this.groups.forEach(g => {
                    const isChecked = userGroupIds.includes(g.id);
                    const label = document.createElement('label');
                    label.className = 'scope-item';
                    label.style.cursor = 'pointer';
                    label.innerHTML = `
                        <input type="checkbox" class="user-group-cb" value="${escapeHtml(g.id)}" ${isChecked ? 'checked' : ''}>
                        <span style="word-break:break-all">${escapeHtml(g.name)}</span>
                    `;
                    groupList.appendChild(label);
                });
            }
            groupsWrap.appendChild(groupList);

            body.append(wName, wEmail, wPwd, wRole, wAdmin, groupsWrap);

            kpOpenModal({
                title: isEdit ? '✏️ Sửa Người dùng' : '👤 Thêm Người dùng',
                content: body,
                okText: 'Lưu',
                onOk: async () => {
                    const checkedCbs = Array.from(body.querySelectorAll('.user-group-cb:checked')) as HTMLInputElement[];
                    const groupIds = checkedCbs.map(cb => cb.value);

                    const payload: Record<string, any> = {
                        display_name: (nameIn as HTMLInputElement).value.trim(),
                        email: (emailIn as HTMLInputElement).value.trim(),
                        role: (roleIn as HTMLSelectElement).value,
                        is_admin: (adminIn as HTMLInputElement).checked,
                        group_ids: groupIds
                    };
                    const pwd = (pwdIn as HTMLInputElement).value;
                    if (pwd) payload.password = pwd;

                    try {
                        const url = isEdit ? `${API}/users/${userId}` : `${API}/users`;
                        const method = isEdit ? 'PATCH' : 'POST';
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
                const resp = await authFetch(`${API}/groups`);
                if (!resp.ok) throw new Error('Không thể tải danh sách Group');
                const data = await resp.json() as any;
                console.log('Admin: Groups API Response:', data);
                this.groups = Array.isArray(data) ? data : (data.groups || []);
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            } finally {
                this.isLoadingGroups = false;
            }
        },

        openGroupModal(groupId: string | null = null) {
            const isEdit = !!groupId;
            const existingGroup = groupId ? this.groups.find(g => g.id === groupId) : null;

            const body = document.createElement('div');
            body.className = 'kp-modal-form';

            const { wrap: wName, input: nameIn } = _kpBuildModalField({ 
                id: 'gName', 
                label: 'Tên Nhóm', 
                value: existingGroup?.name || '',
                placeholder: 'Ban Giám đốc, Phòng Kỹ thuật...', 
                required: true 
            });
            
            body.append(wName);

            kpOpenModal({
                title: isEdit ? '✏️ Sửa Nhóm' : '👨‍👩‍👧‍👦 Thêm Nhóm mới',
                content: body,
                okText: 'Lưu',
                onOk: async () => {
                    const name = (nameIn as HTMLInputElement).value.trim();
                    if (!name) return { error: 'Tên nhóm không được để trống' };

                    try {
                        const url = isEdit ? `${API}/groups/${groupId}` : `${API}/groups`;
                        const method = isEdit ? 'PUT' : 'POST';
                        const res = await authFetch(url, {
                            method,
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({ name })
                        });
                        if (!res.ok) throw new Error('Lỗi lưu thông tin nhóm');
                        showToast('Đã lưu thông tin Nhóm', 'success');
                        this.loadGroupsTable();
                        return true;
                    } catch (err) {
                        return { error: (err as Error).message };
                    }
                }
            });
        },

        async deleteGroup(groupId: string) {
            if (!await kpConfirm({ 
                title: 'Xóa Nhóm', 
                message: 'Bạn có chắc chắn muốn xóa nhóm này? Các thành viên sẽ bị loại khỏi nhóm này.', 
                danger: true 
            })) return;

            try {
                const res = await authFetch(`${API}/groups/${groupId}`, { method: 'DELETE' });
                if (!res.ok) throw new Error('Không thể xóa nhóm');
                showToast('Đã xóa nhóm thành công', 'success');
                this.loadGroupsTable();
            } catch (err) {
                showToast((err as Error).message, 'error');
            }
        }
    };
}