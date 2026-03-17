export const API =
  window.__KP_API_BASE__
  || localStorage.getItem('kp_api_base')
  || ((window.location.origin && window.location.origin !== 'null')
    ? window.location.origin
    : 'http://localhost:8000');

export const AUTH = {
  get token() { return localStorage.getItem('kp_token'); },
  get refreshToken() { return localStorage.getItem('kp_refresh'); },
  get user() {
    try { return JSON.parse(localStorage.getItem('kp_user') || '{}'); }
    catch { return {}; }
  },
  save(data) {
    const currentUser = this.user;
    localStorage.setItem('kp_token', data.access_token);
    localStorage.setItem('kp_refresh', data.refresh_token);
    localStorage.setItem('kp_user', JSON.stringify({
      user_id: data.user_id,
      email: data.email,
      display_name: data.display_name || currentUser.display_name || '',
      is_admin: data.is_admin,
      role: data.role || currentUser.role || 'standard',
    }));
  },
  clear() {
    ['kp_token', 'kp_refresh', 'kp_user'].forEach(k => localStorage.removeItem(k));
  },
  isExpired() {
    const t = this.token;
    if (!t) return true;
    try {
      const p = JSON.parse(atob(t.split('.')[1]));
      return (p.exp * 1000) < (Date.now() + 60000);
    } catch {
      return true;
    }
  },
};

let _onAuthExpired = null;
export function setAuthExpiredHandler(fn) {
  _onAuthExpired = typeof fn === 'function' ? fn : null;
}

export async function tryRefresh() {
  try {
    const r = await fetch(API + '/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: AUTH.refreshToken }),
    });
    if (!r.ok) { AUTH.clear(); return false; }
    AUTH.save(await r.json());
    return true;
  } catch {
    AUTH.clear();
    return false;
  }
}

export async function authFetch(url, options = {}) {
  if (AUTH.isExpired() && AUTH.refreshToken) await tryRefresh();
  const resp = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(AUTH.token ? { Authorization: 'Bearer ' + AUTH.token } : {}),
      ...(options.headers || {}),
    },
  });
  if (resp.status === 401) {
    const ok = AUTH.refreshToken ? await tryRefresh() : false;
    if (ok) return authFetch(url, options);
    if (_onAuthExpired) _onAuthExpired();
    throw new Error('Phiên đăng nhập hết hạn');
  }
  return resp;
}

