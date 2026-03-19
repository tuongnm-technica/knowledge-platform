export class ThemeModule {
    private static THEME_KEY = 'kp_theme';

    // Khởi tạo theme khi trang vừa load xong
    static initTheme(): void {
        const savedTheme = localStorage.getItem(this.THEME_KEY) || 'light';
        document.documentElement.setAttribute('data-theme', savedTheme);
    }

    // Hàm thực hiện chuyển đổi qua lại giữa Dark và Light
    static toggleTheme(): void {
        const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
        const newTheme = currentTheme === 'light' ? 'dark' : 'light';
        
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem(this.THEME_KEY, newTheme);
    }

    // Gắn sự kiện click cho nút chuyển đổi trên giao diện
    static setupThemeToggle(buttonId: string): void {
        const btn = document.getElementById(buttonId);
        if (btn) {
            btn.addEventListener('click', () => this.toggleTheme());
        }
    }
}