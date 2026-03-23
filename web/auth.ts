import { API, authFetch } from './client';
import { User, AuthResponse } from './models';

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
            throw new Error('Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.');
        }

        const data: AuthResponse = await response.json();
        this.setToken(data.access_token);
        
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
        return (await response.json()) as User;
    }
    
    // --- DOM Binding Helpers ---
    static setupLoginForm(emailId: string, passwordId: string, errorId: string): void {
        const emailInput = document.getElementById(emailId) as HTMLInputElement | null;
        const passwordInput = document.getElementById(passwordId) as HTMLInputElement | null;
        const errorDiv = document.getElementById(errorId) as HTMLElement | null;

        // Login is handled via button click in index.html login-screen
        const loginBtn = document.getElementById('loginBtn');
        if (!loginBtn || !emailInput || !passwordInput) return;

        const handleEnter = (e: KeyboardEvent) => {
            if (e.key === 'Enter') loginBtn.click();
        };
        emailInput.addEventListener('keyup', handleEnter);
        passwordInput.addEventListener('keyup', handleEnter);

        loginBtn.addEventListener('click', async () => {
            if (errorDiv) errorDiv.style.display = 'none';
            loginBtn.classList.add('loading');
            try {
                await this.login(emailInput.value, passwordInput.value);
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