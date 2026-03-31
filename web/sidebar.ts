import { AuthModule } from './auth';
import { isAllowed, ADMIN_ONLY_TARGETS } from './permissions';

export class SidebarModule {
    constructor() {
        // Active state is managed by main.ts renderPage
    }

    public async init() {
        this.bindEvents();
        const user = await this.updateUserCard();
        if (user) {
            this.applyPermissions(user);
        }
    }

    private bindEvents() {
        // Events for common sidebar items if any
    }

    public async updateUserCard() {
        try {
            const user = await AuthModule.getCurrentUser();
            const avatar = document.getElementById('sidebarAvatar');
            const username = document.getElementById('sidebarUsername');
            const roleEl = document.querySelector('.user-role');

            if (avatar) avatar.textContent = (user.display_name || user.email || '?').charAt(0).toUpperCase();
            if (username) username.textContent = user.display_name || user.email;
            if (roleEl) roleEl.textContent = user.is_admin ? 'System Admin' : (user.role || 'Member');
            return user;
        } catch (err) {
            return null;
        }
    }

    private applyPermissions(user: any) {
        const role = (user.role || '').toLowerCase();
        const isSystemAdmin = user.is_admin === true || role === 'system_admin' || role === 'admin';

        // 1. If admin, EVERYTHING is visible (early return)
        if (isSystemAdmin) {
            console.log('Sidebar: Admin mode enabled, skipping filters');
            return;
        }

        // 2. Strict enforcement for Admin-only modules (Connectors, Users)
        // Hidden for anyone who is NOT a System Admin, regardless of role list
        ADMIN_ONLY_TARGETS.forEach(target => {
            const el = document.getElementById(`nav-${target}`);
            if (el) {
                el.style.setProperty('display', 'none', 'important');
            }
        });

        // 3. Filter all nav items with data-target based on role mapping
        document.querySelectorAll('.nav-item').forEach(item => {
            const target = item.getAttribute('data-target');
            
            // Special cases: always show chat and search
            if (target === 'chat' || target === 'search') return;

            if (target && !isAllowed(user, target)) {
                (item as HTMLElement).style.setProperty('display', 'none', 'important');
            }
        });

        // 4. Cleanup UI (hide empty sections)
        this.refineSections();
    }

    private refineSections() {
        document.querySelectorAll('.nav-section').forEach(section => {
            let next = section.nextElementSibling;
            let hasVisibleItem = false;
            while (next && !next.classList.contains('nav-section')) {
                if ((next as HTMLElement).style.display !== 'none') {
                    hasVisibleItem = true;
                    break;
                }
                next = next.nextElementSibling;
            }
            if (!hasVisibleItem) {
                (section as HTMLElement).style.display = 'none';
            }
        });
    }
}
