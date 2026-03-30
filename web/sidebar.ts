import { AuthModule } from './auth';

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
        if (user.is_admin || user.role === 'system_admin') return;

        // Role-based visibility mapping (allowed data-target values)
        const PERMISSIONS: Record<string, string[]> = {
            'knowledge_architect': ['chat', 'search', 'documents', 'graph', 'prompts', 'memory'],
            'pm_po': ['chat', 'search', 'documents', 'graph', 'tasks', 'drafts', 'memory', 'ba-suite', 'workflows'],
            'ba_sa': ['chat', 'search', 'documents', 'graph', 'tasks', 'drafts', 'ba-suite', 'workflows'],
            'dev_qa': ['chat', 'search', 'documents', 'graph', 'tasks'],
            'standard': ['chat', 'search', 'documents', 'graph'],
        };

        const allowedTargets = PERMISSIONS[user.role] || PERMISSIONS['standard'];
        
        // Hide/Show items
        document.querySelectorAll('.nav-item').forEach(item => {
            const target = item.getAttribute('data-target');
            if (target && !allowedTargets.includes(target)) {
                (item as HTMLElement).style.display = 'none';
            }
        });

        // Hide special nav items without data-target but with IDs
        if (!allowedTargets.includes('prompts')) document.getElementById('nav-prompts')?.style.setProperty('display', 'none');
        if (!allowedTargets.includes('tasks')) document.getElementById('nav-tasks')?.style.setProperty('display', 'none');
        if (!allowedTargets.includes('drafts')) document.getElementById('nav-drafts')?.style.setProperty('display', 'none');
        if (!allowedTargets.includes('ba-suite')) document.getElementById('nav-ba-suite')?.style.setProperty('display', 'none');
        if (!allowedTargets.includes('workflows')) document.getElementById('nav-workflows')?.style.setProperty('display', 'none');
        
        // Always hide admin-only items if not admin
        document.getElementById('nav-connectors')?.style.setProperty('display', 'none');
        document.getElementById('nav-users')?.style.setProperty('display', 'none');

        // Optional: Hide sections if no visible items (simplified approach)
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
