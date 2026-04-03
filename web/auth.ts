import { API, authFetch } from './client';
import { User, AuthResponse } from './models';
import { i18n } from './i18n';

export class AuthModule {
    private static TOKEN_KEY = 'kp_access_token';

    static getToken(): string | null {
        return localStorage.getItem(this.TOKEN_KEY);
    }

    static setToken(token: string): void {
        localStorage.setItem(this.TOKEN_KEY, token);
    }

    static clearToken(): void {
        localStorage.removeItem(this.TOKEN_KEY);
    }

    static isAuthenticated(): boolean {
        return !!this.getToken();
    }

    static async login(email: string, password: string): Promise<void> {
        const response = await fetch(`${API}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password }),
        });

        if (!response.ok) {
            let errorMsg = (window as any).$t('auth.login_failed', { defaultValue: 'Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.' });
            try {
                const errData = await response.json();
                if (errData.detail) {
                    if (Array.isArray(errData.detail)) {
                        errorMsg = errData.detail.map((e: any) => e.msg).join(', ');
                    } else {
                        errorMsg = errData.detail;
                    }
                }
            } catch (e) {}
            throw new Error(errorMsg);
        }

        const data: AuthResponse = await response.json();
        this.setToken(data.access_token);
        
        if (data.language) {
            i18n.changeLanguage(data.language);
        }
        
        // Save user info to local storage for quick access if needed
        localStorage.setItem('kp_user', JSON.stringify(data));
    }

    static logout(): void {
        this.clearToken();
        localStorage.removeItem('kp_user');
        window.location.href = window.location.origin;
    }

    static async getCurrentUser(): Promise<User> {
        const response = await authFetch(`${API}/auth/me`);
        if (!response.ok) throw new Error('Không thể lấy thông tin user');
        const user = (await response.json()) as User;
        return user;
    }
    
    // --- DOM Binding Helpers ---
    static setupLoginForm(emailId: string, passwordId: string, errorId: string): void {
        const emailInput = document.getElementById(emailId) as HTMLInputElement | null;
        const passwordInput = document.getElementById(passwordId) as HTMLInputElement | null;
        const errorDiv = document.getElementById(errorId) as HTMLElement | null;

        // Login is handled via button click in index.html login-screen
        const loginBtn = document.getElementById('loginBtn');
        if (!loginBtn || !emailInput || !passwordInput) return;

        // Tránh bind sự kiện nhiều lần nếu hàm được gọi lại bởi Router
        if (loginBtn.hasAttribute('data-hooked')) return;
        loginBtn.setAttribute('data-hooked', 'true');

        const handleEnter = (e: KeyboardEvent) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                loginBtn.click();
            }
        };
        emailInput.addEventListener('keydown', handleEnter);
        passwordInput.addEventListener('keydown', handleEnter);

        loginBtn.addEventListener('click', async (e) => {
            e.preventDefault(); // Ngăn hành vi submit form mặc định làm reload trang
            if (errorDiv) errorDiv.style.display = 'none';
            
            if (!emailInput.value.trim() || !passwordInput.value) {
                if (errorDiv) {
                    errorDiv.textContent = (window as any).$t('auth.enter_credentials', { defaultValue: 'Vui lòng nhập đầy đủ email và mật khẩu' });
                    errorDiv.style.display = 'block';
                }
                return;
            }

            loginBtn.classList.add('loading');
            try {
                await AuthModule.login(emailInput.value, passwordInput.value);
                window.location.href = window.location.origin; 
            } catch (err) {
                const error = err as Error;
                if (errorDiv) { 
                    errorDiv.textContent = error.message; 
                    errorDiv.style.display = 'block'; 
                }
            } finally {
                loginBtn.classList.remove('loading');
            }
        });
    }
}