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
        const basketNav = document.getElementById('nav-basket');
        if (basketNav) {
            basketNav.addEventListener('click', () => {
                // Dispatch event to open basket drawer
                document.dispatchEvent(new CustomEvent('kp-open-basket'));
            });
        }
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
        // 1. If admin, EVERYTHING is visible (early return)
        if (user.is_admin || user.role === 'system_admin' || user.role === 'admin') {
            console.log('Sidebar: Admin mode enabled, skipping filters');
            return;
        }

        // 2. Filter all nav items with data-target
        document.querySelectorAll('.nav-item').forEach(item => {
            const target = item.getAttribute('data-target');
            
            // Special cases: always show chat and search
            if (target === 'chat' || target === 'search') return;

            if (target && !isAllowed(user, target)) {
                (item as HTMLElement).style.setProperty('display', 'none', 'important');
            }
        });

        // 3. Strict enforcement for Admin-only modules (Connectors, Users)
        // This is a safety layer in case data-target is missing or being overridden
        ADMIN_ONLY_TARGETS.forEach(target => {
            const el = document.getElementById(`nav-${target}`);
            if (el) {
                el.style.setProperty('display', 'none', 'important');
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
