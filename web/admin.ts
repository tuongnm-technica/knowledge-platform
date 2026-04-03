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
            this.switchTab('groups');
        } else {
            this.switchTab('users');
        }
        this.updateStats();
    }

    public switchTab(tabId: string) {
        // Update tab buttons
        document.querySelectorAll('.admin-tab').forEach(btn => {
            const isTarget = btn.getAttribute('data-admin-tab') === tabId;
            btn.classList.toggle('active', isTarget);
            btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
        });

        // Update panels
        const usersPanel = document.getElementById('admin-users-panel');
        const groupsPanel = document.getElementById('admin-groups-panel');
        
        if (usersPanel) {
            usersPanel.classList.toggle('active', tabId === 'users');
            if (tabId === 'users') usersPanel.removeAttribute('hidden');
            else usersPanel.setAttribute('hidden', '');
        }
        if (groupsPanel) {
            groupsPanel.classList.toggle('active', tabId === 'groups');
            if (tabId === 'groups') groupsPanel.removeAttribute('hidden');
            else groupsPanel.setAttribute('hidden', '');
        }
    }

    public updateStats() {
        const totalUsers = this.users.length;
        const totalAdmins = this.users.filter(u => u.is_admin).length;
        const totalGroups = this.groups.length;
        const unassigned = this.users.filter(u => !u.group_ids || u.group_ids.length === 0).length;

        const elUsers = document.getElementById('admin-stat-users');
        const elAdmins = document.getElementById('admin-stat-admins');
        const elGroups = document.getElementById('admin-stat-groups');
        const elUnassigned = document.getElementById('admin-stat-unassigned');

        if (elUsers) elUsers.textContent = totalUsers.toString();
        if (elAdmins) elAdmins.textContent = totalAdmins.toString();
        if (elGroups) elGroups.textContent = totalGroups.toString();
        if (elUnassigned) elUnassigned.textContent = unassigned.toString();

        const userTabCount = document.getElementById('admin-users-tab-count');
        const groupTabCount = document.getElementById('admin-groups-tab-count');
        if (userTabCount) userTabCount.textContent = totalUsers.toString();
        if (groupTabCount) groupTabCount.textContent = totalGroups.toString();
    }

    public async loadUsersTable() {
        this.isLoadingUsers = true;
        this.render();
        try {
            const resp = await authFetch(`${API}/users`);
            if (!resp.ok) throw new Error((window as any).$t('users.err_load_users'));
            const data = await resp.json() as { users: User[], groups?: Group[] };
            this.users = data.users || [];
            if (data.groups) this.groups = data.groups;
        } catch (err) {
            showToast((err as Error).message, 'error');
        } finally {
            this.isLoadingUsers = false;
            this.render();
            this.updateStats();
        }
    }

    public async loadGroupsTable() {
        this.isLoadingGroups = true;
        this.render();
        try {
            const resp = await authFetch(`${API}/groups`);
            if (!resp.ok) throw new Error((window as any).$t('users.err_load_groups'));
            const data = await resp.json() as Group[] | { groups: Group[] };
            this.groups = Array.isArray(data) ? data : (data.groups || []);
        } catch (err) {
            showToast((err as Error).message, 'error');
        } finally {
            this.isLoadingGroups = false;
            this.render();
            this.updateStats();
        }
    }

    public openUserModal(userId: string | null = null) {
        const isEdit = !!userId;
        const existingUser = userId ? this.users.find(u => u.id === userId) : null;

        const body = document.createElement('div');
        body.className = 'kp-modal-form';

        const { wrap: wName, input: nameIn } = _kpBuildModalField({ 
            id: 'uName', 
            label: (window as any).$t('users.label_display_name'), 
            value: existingUser?.display_name || '',
            placeholder: 'Nguyễn Văn A', 
            required: true 
        });
        const { wrap: wEmail, input: emailIn } = _kpBuildModalField({ 
            id: 'uEmail', 
            label: (window as any).$t('users.label_email', { defaultValue: 'Email' }), 
            type: 'email', 
            value: existingUser?.email || '',
            placeholder: 'user@technica.vn', 
            required: true 
        });
        const { wrap: wPwd, input: pwdIn } = _kpBuildModalField({ 
            id: 'uPwd', 
            label: isEdit ? (window as any).$t('users.label_password_edit') : (window as any).$t('users.label_password'), 
            type: 'password', 
            required: !isEdit 
        });

        const { wrap: wRole, input: roleIn } = _kpBuildModalField({ 
            id: 'uRole', 
            label: (window as any).$t('users.label_role_field'), 
            type: 'select',
            value: existingUser?.role || 'standard',
            options: [
                { label: (window as any).$t('users.role_standard'), value: 'standard' },
                { label: (window as any).$t('users.role_ka'), value: 'knowledge_architect' },
                { label: (window as any).$t('users.role_pm'), value: 'pm_po' },
                { label: (window as any).$t('users.role_ba'), value: 'ba_sa' },
                { label: (window as any).$t('users.role_dev'), value: 'dev_qa' },
                { label: (window as any).$t('users.role_admin'), value: 'system_admin' }
            ]
        });

        const { wrap: wAdmin, input: adminIn } = _kpBuildModalField({ 
            id: 'uIsAdmin', 
            label: (window as any).$t('users.label_is_admin'), 
            type: 'checkbox',
            value: (existingUser?.is_admin ? 'true' : 'false') as any
        });
        
        const groupsWrap = document.createElement('div');
        groupsWrap.style.marginBottom = '12px';
        groupsWrap.innerHTML = `<label class="kp-modal-label">${(window as any).$t('users.label_groups_field')}</label>`;
        
        const groupList = document.createElement('div');
        groupList.className = 'connector-scope-list';
        
        const userGroupIds = existingUser?.group_ids || [];
        
        if (this.groups.length === 0) {
            groupList.innerHTML = `<div class="connector-scope-empty">${(window as any).$t('users.empty_groups_hint')}</div>`;
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
            title: isEdit ? (window as any).$t('users.modal_edit_user') : (window as any).$t('users.modal_create_user'),
            content: body, okText: (window as any).$t('common.save'),
            onOk: async () => {
                const checkedCbs = Array.from(body.querySelectorAll('.user-group-cb:checked')) as HTMLInputElement[];
                const groupIds = checkedCbs.map(cb => cb.value);

                const name = (nameIn as HTMLInputElement).value.trim();
                const email = (emailIn as HTMLInputElement).value.trim();
                const pwd = (pwdIn as HTMLInputElement).value;

                // Validation
                if (!name) return { error: (window as any).$t('users.err_no_name') };
                if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
                    return { error: (window as any).$t('users.err_invalid_email') };
                }
                if (!isEdit && !pwd) {
                    return { error: (window as any).$t('users.err_no_pwd') };
                }
                if (pwd && pwd.length < 8) {
                    return { error: (window as any).$t('users.err_pwd_short') };
                }

                const payload: Record<string, any> = {
                    display_name: name,
                    email: email,
                    role: (roleIn as HTMLSelectElement).value,
                    is_admin: (adminIn as HTMLInputElement).checked,
                    group_ids: groupIds
                };
                if (pwd) payload.password = pwd;

                try {
                    const url = isEdit ? `${API}/users/${userId}` : `${API}/users`;
                    const method = isEdit ? 'PATCH' : 'POST';
                    const res = await authFetch(url, {
                        method, headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    if (!res.ok) throw new Error((window as any).$t('users.err_save_failed'));
                    showToast((window as any).$t('users.save_success'), 'success');
                    this.loadUsersTable();
                    return true;
                } catch (err) {
                    return { error: (err as Error).message };
                }
            }
        });
    }

    public async deleteUser(userId: string) {
        if (!await kpConfirm({ title: (window as any).$t('users.confirm_delete_user_title'), message: (window as any).$t('users.confirm_delete_user_msg'), danger: true })) return;
        try {
            const res = await authFetch(`${API}/users/${userId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error((window as any).$t('users.err_delete_user_failed'));
            showToast((window as any).$t('users.delete_user_success'), 'success');
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
            label: (window as any).$t('users.label_group_name'), 
            value: existingGroup?.name || '',
            placeholder: 'Ban Giám đốc, Phòng Kỹ thuật...', 
            required: true 
        });
        
        body.append(wName);

        kpOpenModal({
            title: isEdit ? (window as any).$t('users.modal_edit_group') : (window as any).$t('users.modal_create_group'),
            content: body, okText: (window as any).$t('common.save'),
            onOk: async () => {
                const name = (nameIn as HTMLInputElement).value.trim();
                if (!name) return { error: (window as any).$t('users.err_group_no_name') };
                try {
                    const url = isEdit ? `${API}/groups/${groupId}` : `${API}/groups`;
                    const method = isEdit ? 'PATCH' : 'POST';
                    const res = await authFetch(url, {
                        method, headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name })
                    });
                    if (!res.ok) throw new Error((window as any).$t('users.err_group_save_failed'));
                    showToast((window as any).$t('users.group_save_success'), 'success');
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
            title: (window as any).$t('users.confirm_delete_group_title'), 
            message: (window as any).$t('users.confirm_delete_group_msg'), 
            danger: true 
        })) return;

        try {
            const res = await authFetch(`${API}/groups/${groupId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error((window as any).$t('users.err_delete_group_failed'));
            showToast((window as any).$t('users.delete_group_success'), 'success');
            this.loadGroupsTable();
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    private bindGlobalActions() {
        if (this.isEventsBound) return;
        this.isEventsBound = true;

        // Tabs switching
        document.querySelectorAll('.admin-tab').forEach(btn => {
            btn.addEventListener('click', () => {
                const tabId = btn.getAttribute('data-admin-tab');
                if (tabId) this.switchTab(tabId);
            });
        });

        // Actions using data attributes
        document.querySelector('[data-admin-action="add-user"]')?.addEventListener('click', () => this.openUserModal());
        document.querySelector('[data-admin-action="refresh-users"]')?.addEventListener('click', () => this.loadUsersTable());
        document.querySelector('[data-admin-action="add-group"]')?.addEventListener('click', () => this.openGroupModal());
        document.querySelector('[data-admin-action="refresh-groups"]')?.addEventListener('click', () => this.loadGroupsTable());

        // Also support old IDs if any remain
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
            userTbody.innerHTML = this.users.map(u => {
                const groupNames = (u.groups || []).map(g => g.name).join(', ') || '—';
                const adminBadge = u.is_admin ? '<span class="status-badge status-active" style="background:var(--primary-light); color:var(--primary); border:1px solid var(--primary)">ROOT</span>' : `<span style="color:var(--text-muted)">${(window as any).$t('users.badge_member')}</span>`;
                const statusBadge = u.is_active !== false 
                    ? '<span style="color:var(--success)">●</span>' 
                    : '<span style="color:var(--danger)">●</span>';

                return `
                    <tr>
                        <td style="font-weight: 600;">
                            <div style="display:flex; flex-direction:column">
                                <span>${escapeHtml(u.display_name)}</span>
                                <span style="font-size:0.8em; color:var(--text-muted); font-weight:400">${escapeHtml(u.email)}</span>
                            </div>
                        </td>
                        <td>${statusBadge} <span class="status-badge status-pending" style="background: var(--bg3); color: var(--text-muted); border: 1px solid var(--border);">${escapeHtml(u.role || 'standard')}</span></td>
                        <td style="max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap" title="${escapeHtml(groupNames)}">${escapeHtml(groupNames)}</td>
                        <td>${adminBadge}</td>
                        <td style="text-align: right;">
                            <button class="secondary-btn mini edit-user" data-id="${u.id}">✏️</button>
                            <button class="danger-btn mini ghost-btn delete-user" data-id="${u.id}">🗑</button>
                        </td>
                    </tr>
                `;
            }).join('');

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
                    <td><span class="status-badge" style="background:var(--bg3)">${g.member_count || 0} ${(window as any).$t('users.badge_tv')}</span></td>
                    <td style="color:var(--text-muted); font-size:0.9em">${(window as any).$t('users.label_id')}: ${escapeHtml(g.id)}</td>
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