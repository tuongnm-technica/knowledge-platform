import { API, authFetch } from '../api/client';
import { User } from '../types/models';

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
        const formData = new URLSearchParams();
        formData.append('username', email);
        formData.append('password', password);

        const response = await fetch(`${API}/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: formData,
        });

        if (!response.ok) {
            throw new Error('Đăng nhập thất bại. Vui lòng kiểm tra lại thông tin.');
        }

        const data = await response.json();
        this.setToken(data.access_token);
    }

    static logout(): void {
        this.clearToken();
        window.location.href = '/login.html';
    }

    static async getCurrentUser(): Promise<User> {
        const response = await authFetch(`${API}/users/me`);
        if (!response.ok) throw new Error('Không thể lấy thông tin user');
        return (await response.json()) as User;
    }
    
    // --- DOM Binding Helpers ---
    static setupLoginForm(formId: string, emailId: string, passwordId: string, errorId: string): void {
        const form = document.getElementById(formId) as HTMLFormElement | null;
        const emailInput = document.getElementById(emailId) as HTMLInputElement | null;
        const passwordInput = document.getElementById(passwordId) as HTMLInputElement | null;
        const errorDiv = document.getElementById(errorId) as HTMLElement | null;

        if (!form || !emailInput || !passwordInput) return;

        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            if (errorDiv) errorDiv.style.display = 'none';
            try {
                await this.login(emailInput.value, passwordInput.value);
                window.location.href = '/'; // Đăng nhập thành công
            } catch (error: any) {
                if (errorDiv) { errorDiv.textContent = error.message; errorDiv.style.display = 'block'; }
            }
        });
    }
}