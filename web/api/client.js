export const API = window.__KP_API_BASE__
  || localStorage.getItem('kp_api_base')
  || ((window.location.origin && window.location.origin !== 'null')
    ? window.location.origin
    : 'http://localhost:8000');

let onAuthExpired = () => {
  console.warn("Auth expired, but no handler was set.");
};

export function setAuthExpiredHandler(handler) {
  onAuthExpired = handler;
}

export const AUTH = {
  get token()        { return localStorage.getItem('kp_token'); },
  get refreshToken() { return localStorage.getItem('kp_refresh'); },
  get user()         {
    try { return JSON.parse(localStorage.getItem('kp_user') || '{}'); }
    catch { return {}; }
  },
  save(data) {
    const currentUser = this.user;
    localStorage.setItem('kp_token',   data.access_token);
    localStorage.setItem('kp_refresh', data.refresh_token);
    localStorage.setItem('kp_user', JSON.stringify({
      user_id: data.user_id,
      email: data.email,
      display_name: data.display_name || currentUser.display_name || '',
      is_admin: data.is_admin,
      role: data.role || currentUser.role || 'standard'
    }));
  },
  clear() {
    ['kp_token','kp_refresh','kp_user'].forEach(k => localStorage.removeItem(k));
  },
  isExpired() {
    const t = this.token;
    if (!t) return true;
    try {
      // Lấy payload của JWT và kiểm tra thời gian hết hạn (exp)
      const p = JSON.parse(atob(t.split('.')[1]));
      // Trả về true nếu token sẽ hết hạn trong vòng 1 phút (60000ms) tới
      return (p.exp * 1000) < (Date.now() + 60000);
    } catch { return true; }
  }
};

// Sử dụng biến này để "khóa" (lock) việc gọi refresh nhiều lần cùng lúc
let refreshPromise = null;

export async function tryRefresh() {
  // Nếu đang có một tiến trình refresh đang chạy, hãy đợi nó hoàn thành
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      if (!AUTH.refreshToken) throw new Error("No refresh token");
      
      const r = await fetch(API + '/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: AUTH.refreshToken }),
      });
      
      if (!r.ok) throw new Error("Refresh failed");
      
      AUTH.save(await r.json());
      return true;
    } catch {
      AUTH.clear();
      return false;
    } finally {
      // Xóa khóa sau khi hoàn tất
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function authFetch(url, options = {}) {
  // Kiểm tra trước khi gọi API, nếu token đã/sắp hết hạn thì chủ động đi refresh
  if (AUTH.isExpired() && AUTH.refreshToken) {
    await tryRefresh();
  }

  const headers = {
    'Content-Type': 'application/json',
    ...(AUTH.token ? { 'Authorization': 'Bearer ' + AUTH.token } : {}),
    ...(options.headers || {}),
  };

  let resp = await fetch(url, { ...options, headers });

  // Phòng trường hợp backend trả về 401 dù Frontend nghĩ token vẫn còn hạn
  if (resp.status === 401) {
    const ok = AUTH.refreshToken ? await tryRefresh() : false;
    if (ok) {
      // Refresh thành công, gọi lại API vừa bị lỗi (Retry)
      headers['Authorization'] = 'Bearer ' + AUTH.token;
      resp = await fetch(url, { ...options, headers });
    } else {
      // Bó tay, đăng xuất người dùng
      onAuthExpired();
      throw new Error('Phiên đăng nhập hết hạn');
    }
  }
  
  return resp;
}