import { API, authFetch } from './client';
import { User, Group } from './models';
import { AuthModule } from './auth';
import { showToast, kpConfirm, kpOpenModal, _kpBuildModalField, escapeHtml } from './ui';

export class AdminModule {
    private users: User[] = [];
    private groups: Group[] = [];
    private isLoadingUsers = false;
    private isLoadingGroups = false;
    private isEventsBound = false;

    constructor() {
        document.addEventListener('kp-refresh-users', () => {
            this.loadUsersTable();
            this.loadGroupsTable();
        });
    }

    public async init(subpage?: string) {
        if (!AuthModule.isAuthenticated()) return;
        await Promise.all([this.loadUsersTable(), this.loadGroupsTable()]);
        this.bindGlobalActions();

        if (subpage === 'groups') {
            setTimeout(() => {
                const groupsSection = document.querySelector('.section-header[style*="margin-top: 40px"]');
                if (groupsSection) groupsSection.scrollIntoView({ behavior: 'smooth' });
            }, 100);
        }
    }

    public async loadUsersTable() {
        this.isLoadingUsers = true;
        this.render();
        try {
            const resp = await authFetch(`${API}/users`);
            if (!resp.ok) throw new Error('Không thể tải danh sách User');
            const data = await resp.json() as { users: User[] };
            this.users = data.users || [];
        } catch (err) {
            showToast((err as Error).message, 'error');
        } finally {
            this.isLoadingUsers = false;
            this.render();
        }
    }

    public async loadGroupsTable() {
        this.isLoadingGroups = true;
        this.render();
        try {
            const resp = await authFetch(`${API}/groups`);
            if (!resp.ok) throw new Error('Không thể tải danh sách Group');
            const data = await resp.json() as Group[] | { groups: Group[] };
            this.groups = Array.isArray(data) ? data : (data.groups || []);
        } catch (err) {
            showToast((err as Error).message, 'error');
        } finally {
            this.isLoadingGroups = false;
            this.render();
        }
    }

    public openUserModal(userId: string | null = null) {
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
        
        const groupsWrap = document.createElement('div');
        groupsWrap.style.marginBottom = '12px';
        groupsWrap.innerHTML = `<label class="kp-modal-label">Cơ quan / Nhóm (Groups)</label>`;
        
        const groupList = document.createElement('div');
        groupList.className = 'connector-scope-list';
        
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
            content: body, okText: 'Lưu',
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
                        method, headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    if (!res.ok) throw new Error('Lỗi lưu thông tin');
                    showToast('Lưu thông tin User thành công', 'success');
                    this.loadUsersTable();
                    return true;
                } catch (err) {
                    return { error: (err as Error).message };
                }
            }
        });
    }

    public async deleteUser(userId: string) {
        if (!await kpConfirm({ title: 'Xóa User', message: 'Bạn có chắc chắn muốn xóa user này?', danger: true })) return;
        try {
            const res = await authFetch(`${API}/users/${userId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Không thể xóa user');
            showToast('Đã xóa user', 'success');
            this.loadUsersTable();
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    public openGroupModal(groupId: string | null = null) {
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
            content: body, okText: 'Lưu',
            onOk: async () => {
                const name = (nameIn as HTMLInputElement).value.trim();
                if (!name) return { error: 'Tên nhóm không được để trống' };
                try {
                    const url = isEdit ? `${API}/groups/${groupId}` : `${API}/groups`;
                    const method = isEdit ? 'PATCH' : 'POST';
                    const res = await authFetch(url, {
                        method, headers: { 'Content-Type': 'application/json' },
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
    }

    public async deleteGroup(groupId: string) {
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

    private bindGlobalActions() {
        if (this.isEventsBound) return;
        this.isEventsBound = true;
        document.querySelector('#admin-add-user')?.addEventListener('click', () => this.openUserModal());
        document.querySelector('#admin-refresh-users')?.addEventListener('click', () => this.loadUsersTable());
        document.querySelector('#admin-add-group')?.addEventListener('click', () => this.openGroupModal());
        document.querySelector('#admin-refresh-groups')?.addEventListener('click', () => this.loadGroupsTable());
    }

    private render() {
        // Users Table
        const userTbody = document.querySelector('#admin-users-tbody');
        const userLoading = document.querySelector('#admin-users-loading') as HTMLElement;
        if (userTbody && userLoading) {
            userLoading.style.display = this.isLoadingUsers ? 'block' : 'none';
            userTbody.innerHTML = this.users.map(u => `
                <tr>
                    <td style="font-weight: 600;">${escapeHtml(u.display_name)}</td>
                    <td>${escapeHtml(u.email)}</td>
                    <td><span class="status-badge status-pending" style="background: var(--bg3); color: var(--text-muted); border: 1px solid var(--border);">${escapeHtml(u.role || 'standard')}</span></td>
                    <td style="text-align: right;">
                        <button class="secondary-btn mini edit-user" data-id="${u.id}">✏️</button>
                        <button class="danger-btn mini ghost-btn delete-user" data-id="${u.id}">🗑</button>
                    </td>
                </tr>
            `).join('');

            userTbody.querySelectorAll('.edit-user').forEach(btn => {
                btn.addEventListener('click', () => this.openUserModal(btn.getAttribute('data-id')));
            });
            userTbody.querySelectorAll('.delete-user').forEach(btn => {
                btn.addEventListener('click', () => this.deleteUser(btn.getAttribute('data-id')!));
            });
        }

        // Groups Table
        const groupTbody = document.querySelector('#admin-groups-tbody');
        const groupLoading = document.querySelector('#admin-groups-loading') as HTMLElement;
        if (groupTbody && groupLoading) {
            groupLoading.style.display = this.isLoadingGroups ? 'block' : 'none';
            groupTbody.innerHTML = this.groups.map(g => `
                <tr>
                    <td style="font-weight: 600;">${escapeHtml(g.name)}</td>
                    <td style="text-align: right;">
                        <button class="secondary-btn mini edit-group" data-id="${g.id}">✏️</button>
                        <button class="danger-btn mini ghost-btn delete-group" data-id="${g.id}">🗑</button>
                    </td>
                </tr>
            `).join('');

            groupTbody.querySelectorAll('.edit-group').forEach(btn => {
                btn.addEventListener('click', () => this.openGroupModal(btn.getAttribute('data-id')));
            });
            groupTbody.querySelectorAll('.delete-group').forEach(btn => {
                btn.addEventListener('click', () => this.deleteGroup(btn.getAttribute('data-id')!));
            });
        }
    }
}