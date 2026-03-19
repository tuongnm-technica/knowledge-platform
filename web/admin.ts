import { API, authFetch } from './client';
import { User, Group } from './models';
import { escapeHtml, showToast, kpConfirm, kpOpenModal, _kpBuildModalField } from './ui';

export class AdminModule {
    constructor() {
        this.initEvents();
    }
    private initEvents() {
        document.getElementById('createUserBtn')?.addEventListener('click', () => this.openUserModal());
        document.getElementById('createGroupBtn')?.addEventListener('click', () => this.openGroupModal());
    }

    public async loadUsersAdmin(): Promise<void> {
        this.loadUsersTable();
        this.loadGroupsTable();
    }

    // ─── Lấy và hiển thị Users ────────────────────────────────────────────────
    private async loadUsersTable(): Promise<void> {
        const container = document.getElementById('usersTableContainer');
        if (container) container.innerHTML = '<div class="loading-state">Đang tải users...</div>';

        try {
            const response = await authFetch(`${API}/users`);
            if (!response.ok) throw new Error('Không thể tải danh sách User');
            const data = await response.json();
            const users: User[] = Array.isArray(data) ? data : data.users || [];
            this.renderUsers(users);
        } catch (e: any) {
            if (container) container.innerHTML = `<div class="search-empty">Lỗi: ${e.message}</div>`;
        }
    }

    private renderUsers(users: User[]): void {
        const container = document.getElementById('usersTableContainer');
        if (!container) return;
        if (users.length === 0) {
            container.innerHTML = '<div class="search-empty">Chưa có người dùng nào.</div>';
            return;
        }

        let html = `
            <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 14px;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--border); color: var(--text-dim);">
                        <th style="padding: 12px 8px;">Tên hiển thị</th>
                        <th style="padding: 12px 8px;">Email</th>
                        <th style="padding: 12px 8px;">Vai trò</th>
                        <th style="padding: 12px 8px;">Thao tác</th>
                    </tr>
                </thead>
                <tbody>
        `;

        users.forEach(u => {
            const roleBadge = u.is_admin ? '<span style="color:var(--danger);font-weight:bold;">Admin</span>' : escapeHtml(u.role || 'Member');
            html += `
                <tr style="border-bottom: 1px solid var(--border-light);">
                    <td style="padding: 12px 8px; font-weight: 600;">${escapeHtml(u.display_name)}</td>
                    <td style="padding: 12px 8px;">${escapeHtml(u.email)}</td>
                    <td style="padding: 12px 8px;">${roleBadge}</td>
                    <td style="padding: 12px 8px;">
                        <button class="secondary-btn mini edit-user-btn" data-id="${escapeHtml(u.id)}">Sửa</button>
                        <button class="danger-btn mini del-user-btn" data-id="${escapeHtml(u.id)}">Xóa</button>
                    </td>
                </tr>
            `;
        });

        html += '</tbody></table>';
        container.innerHTML = html;

        container.querySelectorAll('.edit-user-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
                if (id) this.openUserModal(id);
            });
        });

        container.querySelectorAll('.del-user-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
                if (id) this.deleteUser(id);
            });
        });
    }

    public openUserModal(userId: string | null = null): void {
        const isEdit = !!userId;
        const body = document.createElement('div');
        body.className = 'kp-modal-form';

        const { wrap: wName, input: nameIn } = _kpBuildModalField({ id: 'uName', label: 'Tên hiển thị', placeholder: 'Nguyễn Văn A', required: true });
        const { wrap: wEmail, input: emailIn } = _kpBuildModalField({ id: 'uEmail', label: 'Email', type: 'email', placeholder: 'user@technica.vn', required: true });
        const { wrap: wPwd, input: pwdIn } = _kpBuildModalField({ id: 'uPwd', label: isEdit ? 'Mật khẩu mới (để trống nếu không đổi)' : 'Mật khẩu', type: 'password', required: !isEdit });
        
        body.append(wName, wEmail, wPwd);

        kpOpenModal({
            title: isEdit ? '✏️ Sửa Người dùng' : '👤 Thêm Người dùng',
            content: body,
            okText: 'Lưu',
            onOk: async () => {
                const payload: any = {
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
                        body: JSON.stringify(payload)
                    });
                    if (!res.ok) throw new Error('Lỗi lưu thông tin');
                    showToast('Lưu thông tin User thành công', 'success');
                    this.loadUsersTable();
                    return true;
                } catch (e: any) {
                    return { error: e.message };
                }
            }
        });
    }

    private async deleteUser(userId: string): Promise<void> {
        if (!await kpConfirm({ title: 'Xóa User', message: 'Bạn có chắc chắn muốn xóa user này?', danger: true })) return;
        try {
            const res = await authFetch(`${API}/users/${userId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Không thể xóa user');
            showToast('Đã xóa user', 'success');
            this.loadUsersTable();
        } catch (e: any) {
            showToast(e.message, 'error');
        }
    }

    // ─── Lấy và hiển thị Groups ───────────────────────────────────────────────
    private async loadGroupsTable(): Promise<void> {
        const container = document.getElementById('groupsTableContainer');
        if (container) container.innerHTML = '<div class="loading-state">Đang tải groups...</div>';

        try {
            const response = await authFetch(`${API}/groups`);
            if (!response.ok) throw new Error('Không thể tải danh sách Group');
            const data = await response.json();
            const groups: Group[] = Array.isArray(data) ? data : data.groups || [];
            this.renderGroups(groups);
        } catch (e: any) {
            if (container) container.innerHTML = `<div class="search-empty">Lỗi: ${e.message}</div>`;
        }
    }

    private renderGroups(groups: Group[]): void {
        const container = document.getElementById('groupsTableContainer');
        if (!container) return;
        if (groups.length === 0) {
            container.innerHTML = '<div class="search-empty">Chưa có group nào.</div>';
            return;
        }

        let html = `<div style="display:flex; flex-wrap:wrap; gap:12px;">`;
        groups.forEach(g => {
            html += `
                <div style="border: 1px solid var(--border); padding: 12px 16px; border-radius: 8px; background: var(--bg2);">
                    <div style="font-weight:bold; margin-bottom: 4px;">${escapeHtml(g.name)}</div>
                    <div style="font-size: 11px; color: var(--text-dim); margin-bottom: 8px;">ID: ${escapeHtml(g.id)}</div>
                    <button class="secondary-btn mini del-group-btn" data-id="${escapeHtml(g.id)}">Xóa</button>
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;

        container.querySelectorAll('.del-group-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
                if (id) this.deleteGroup(id);
            });
        });
    }

    public openGroupModal(): void {
        showToast('Tính năng thêm Group đang được phát triển', 'info');
    }

    private async deleteGroup(groupId: string): Promise<void> {
        showToast('Tính năng xóa Group đang được phát triển', 'warning');
    }
}