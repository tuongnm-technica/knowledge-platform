export const API = '/api';

export async function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
    const token = localStorage.getItem('kp_access_token');
    
    const headers = new Headers(options.headers || {});
    if (token) {
        headers.set('Authorization', `Bearer ${token}`);
    }

    const response = await fetch(url, { ...options, headers });
    
    // Tự động xử lý khi token hết hạn
    if (response.status === 401) {
        localStorage.removeItem('kp_access_token');
        // Tránh loop: Chỉ redirect nếu không phải đang ở trang chủ
        if (window.location.pathname !== '/' && window.location.pathname !== '') {
            window.location.href = '/';
        }
    }
    
    return response;
}