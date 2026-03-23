import { AuthModule } from './auth';

export class SidebarModule {
    constructor() {
        // Active state is managed by main.ts renderPage
    }

    public async init() {
        this.bindEvents();
        await this.updateUserCard();
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
        } catch (err) {
            // Probably not logged in or token expired
        }
    }
}
