// ═══════════════════════════════════════════════════════
// AUTH MODULE — JWT + auto-refresh
// ═══════════════════════════════════════════════════════
import {
  formatTime,
  safeHostname,
  parseThinking,
  getSourceIcon,
  getBadgeClass,
  formatRelevancePercent,
} from './utils/format.js';
import {
  API,
  AUTH,
  authFetch,
  tryRefresh,
  setAuthExpiredHandler,
} from './api/client.js';
import {
  readApiError, escapeHtml, formatDateTime, formatNumber,
  showToast, kpOpenModal, kpConfirm, _kpBuildModalField
} from './utils/ui.js';
import * as Basket from './modules/basket.js';
import * as Graph from './modules/graph.js';
import * as Admin from './modules/admin.js';
import * as Connectors from './modules/connectors.js';
import * as Tasks from './modules/tasks.js';
import * as Chat from './modules/chat.js';
import * as Drafts from './modules/drafts.js';
import * as PromptsModule from './modules/prompts.js';

setAuthExpiredHandler(showLoginScreen);

/* moved to ./api/client.js
const AUTH = {
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
      const p = JSON.parse(atob(t.split('.')[1]));
      return (p.exp * 1000) < (Date.now() + 60000);
    } catch { return true; }
  }
};

// authFetch: tự gắn Bearer token, auto-refresh nếu hết hạn
async function authFetch(url, options = {}) {
  if (AUTH.isExpired() && AUTH.refreshToken) await tryRefresh();
  const resp = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(AUTH.token ? { 'Authorization': 'Bearer ' + AUTH.token } : {}),
      ...(options.headers || {}),
    }
  });
  if (resp.status === 401) {
    const ok = AUTH.refreshToken ? await tryRefresh() : false;
    if (ok) return authFetch(url, options);
    showLoginScreen();
    throw new Error('Phiên đăng nhập hết hạn');
  }
  return resp;
}

async function tryRefresh() {
  try {
    const r = await fetch(API + '/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: AUTH.refreshToken }),
    });
    if (!r.ok) { AUTH.clear(); return false; }
    AUTH.save(await r.json());
    return true;
  } catch { AUTH.clear(); return false; }
}
*/

async function doLogin() {
  const email = document.getElementById('loginEmail').value.trim();
  const pwd   = document.getElementById('loginPwd').value;
  const err   = document.getElementById('loginError');
  const btn   = document.getElementById('loginBtn');
  if (!email || !pwd) {
    err.textContent = 'Vui lòng nhập đầy đủ thông tin';
    err.style.display = 'block';
    return;
  }
  btn.disabled = true;
  document.getElementById('loginBtnText').textContent = 'Đang đăng nhập...';
  err.style.display = 'none';
  try {
    const r = await fetch(API + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pwd }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      const detailStr = typeof d.detail === 'string' ? d.detail : (d.detail ? JSON.stringify(d.detail) : null);
      err.textContent = detailStr || 'Email hoặc mật khẩu không đúng';
      err.style.display = 'block';
      return;
    }
    AUTH.save(await r.json());
    hideLoginScreen();
  } catch {
    err.textContent = 'Không kết nối được server. Kiểm tra API đang chạy.';
    err.style.display = 'block';
  } finally {
    btn.disabled = false;
    document.getElementById('loginBtnText').textContent = 'Đăng nhập';
  }
}

function hideLoginScreen() {
  const s = document.getElementById('login-screen');
  if (!s) return;
  s.style.opacity = '0';
  s.style.pointerEvents = 'none';
  s.style.transition = 'opacity .3s';
  setTimeout(() => s.remove(), 300);
  applyUser(AUTH.user);
  Basket.renderBasket();
  Basket.updateBasketBadges();
  Tasks.loadTasksCount();
  loadSupportedDocTypes();
  checkHealth();
  Connectors.loadConnectorStats();
  if (document.getElementById('page-users')?.classList.contains('active') && AUTH.user.is_admin) {
    Admin.loadUsersAdmin();
  }
}

function showLoginScreen() {
  AUTH.clear();
  location.reload();
}

function applyUser(u) {
  if (!u || !u.email) return;
  const name = u.display_name || u.email.split('@')[0];
  const el = document.getElementById('sidebarAvatar');
  const nm = document.getElementById('sidebarUsername');
  const rl = document.querySelector('.user-role');
  const navUsers = document.getElementById('nav-users');
  const navGraph = document.getElementById('nav-graph');
  const clearBtn = document.getElementById('clearTabDataBtn');
  const clearAllBtn = document.getElementById('clearAllDataBtn');
  const addConnBtn = document.getElementById('addConnectorBtn');
  const syncJiraBtn = document.getElementById('syncJiraStatusBtn');
  if (el) el.textContent = (name[0] || 'U').toUpperCase();
  if (nm) nm.textContent = name;
  if (rl) {
    const roleCode = Admin.normalizeUserRole(u.role, u.is_admin);
    rl.textContent = Admin.getUserRoleLabel(roleCode);
  }
  if (navUsers) navUsers.style.display = u.is_admin ? 'flex' : 'none';
  if (navGraph) navGraph.style.display = u.is_admin ? 'flex' : 'none';
  if (clearBtn) clearBtn.style.display = u.is_admin ? '' : 'none';
  if (clearAllBtn) clearAllBtn.style.display = u.is_admin ? '' : 'none';
  if (addConnBtn) addConnBtn.style.display = u.is_admin ? '' : 'none';
  if (syncJiraBtn) syncJiraBtn.style.display = u.is_admin ? '' : 'none';
  currentUserId = u.user_id || '';
}

function doLogout() {
  AUTH.clear();
  location.reload();
}

// Auto-login nếu đã có token hợp lệ trong localStorage
(function autoLogin() {
  if (AUTH.token && !AUTH.isExpired()) {
    // Token còn hạn → ẩn login screen ngay
    window.addEventListener('DOMContentLoaded', hideLoginScreen);
  } else if (AUTH.refreshToken) {
    // Token hết hạn nhưng có refresh token → thử refresh
    tryRefresh().then(ok => {
      if (ok) window.addEventListener('DOMContentLoaded', hideLoginScreen);
    });
  }
  // Không có gì → login screen hiển thị bình thường
})();


/* moved to ./api/client.js
const API = window.__KP_API_BASE__
  || localStorage.getItem('kp_api_base')
  || ((window.location.origin && window.location.origin !== 'null')
    ? window.location.origin
    : 'http://localhost:8000');
*/
let currentUserId = '';

// ── Navigation ──
function navigate(page, el) {
  let targetPage = page;
  let targetEl = el;
  if (page === 'users' && !AUTH.user.is_admin) {
    targetPage = 'chat';
    targetEl = document.getElementById('nav-chat') || document.querySelector('.nav-item');
    showToast('Users admin requires admin access.', 'error');
  }
  if (page === 'graph' && !AUTH.user.is_admin) {
    targetPage = 'chat';
    targetEl = document.getElementById('nav-chat') || document.querySelector('.nav-item');
    showToast('Knowledge graph requires admin access.', 'error');
  }
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  if (targetEl) targetEl.classList.add('active');
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + targetPage).classList.add('active');
  if (targetPage === 'tasks') Tasks.loadTasks();
  if (targetPage === 'connectors') Connectors.loadConnectorStats(true);
  if (targetPage === 'basket') Basket.loadBasketPage();
  if (targetPage === 'drafts') Drafts.loadDraftsPage(true);
  if (targetPage === 'users') Admin.loadUsersAdmin();
  if (targetPage === 'graph') Graph.loadGraphDashboard(true);
  if (targetPage === 'prompts') PromptsModule.loadPromptsPage();
  const titles = { chat: 'Chat AI', search: 'Search', basket: 'Giỏ Ngữ Cảnh', drafts: 'Drafts', tasks: '🤖 AI Tasks', connectors: 'Connectors', history: 'Lịch sử Chat', users: 'Users & Permissions', prompts: '🗂️ Skill Prompts' };
  if (targetPage === 'graph') {
    document.getElementById('pageTitle').textContent = 'Knowledge Graph';
  } else {
    document.getElementById('pageTitle').textContent = titles[targetPage] || targetPage;
  }
  if (targetPage === 'history') Chat.renderHistory();
}

// ── Health check ──
async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const d = await r.json();
    const ok = d.status === 'ok' || d.postgresql === 'ok';
    document.getElementById('statusDot').style.background = ok ? 'var(--accent3)' : 'var(--danger)';
    document.getElementById('statusText').textContent = ok ? 'Hệ thống hoạt động' : 'Có lỗi kết nối';
  } catch {
    document.getElementById('statusDot').style.background = 'var(--danger)';
    document.getElementById('statusText').textContent = 'Không kết nối được API';
  }
}

// Cache document types fetched from API
let supportedDocTypes = {};
let supportedDocTypesList = [];

async function loadSupportedDocTypes() {
  try {
    const response = await authFetch(`${API}/docs/supported-types`);
    if (!response.ok) throw new Error('Failed to load document types');
    const data = await response.json();
    supportedDocTypes = data.supported_types || {};
    supportedDocTypesList = Object.keys(supportedDocTypes).sort();
  } catch (e) {
    console.warn('Failed to load supported doc types, using fallback:', e);
    supportedDocTypes = {
      srs: 'SRS (Software Requirements Specification)',
      brd: 'BRD (Business Requirements Document)',
      api_spec: 'API Specification',
      use_cases: 'Use Cases',
      validation_rules: 'Validation Rules',
      user_stories: 'User Stories + Acceptance Criteria',
      requirements_intake: 'Requirements Intake (FR/NFR/BR + Assumptions)',
      requirement_review: 'Requirement Review (Gaps/Risks/Permissions)',
      solution_design: 'Solution Design (Architecture + ADR + Data Model)',
      fe_spec: 'FE Technical Spec (Components + UI States + a11y)',
      qa_test_spec: 'QA Test Spec (Unit/IT/E2E/UAT + OWASP)',
      deployment_spec: 'Deployment & Ops Spec (CI/CD + Monitoring + Runbook)',
      change_request: 'Change Request Analysis + Impact Analysis',
      release_notes: 'Release Notes',
      function_list: 'Function List',
      risk_log: 'Risk Log',
    };
    supportedDocTypesList = Object.keys(supportedDocTypes).sort();
  }
}

function docDraftTypeLabel(docType) {
  const key = String(docType || '').trim().toLowerCase();
  return supportedDocTypes[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || 'Draft';
}

async function generateDocFromDocuments(docIds, presetDocType = '', presetGoal = '') {
  const raw = Array.isArray(docIds) ? docIds : [];
  const ids = [];
  const seen = new Set();
  for (const v of raw) {
    const s = String(v || '').trim();
    if (!s || seen.has(s)) continue;
    seen.add(s);
    ids.push(s);
  }
  if (!ids.length) {
    showToast('Chưa chọn tài liệu nào.', 'info');
    return;
  }
  if (ids.length > 12) {
    showToast('Đang chọn quá nhiều tài liệu (max 12). Vui lòng bỏ bớt trong giỏ/selection.', 'warning');
    return;
  }

  let docType = String(presetDocType || '').trim().toLowerCase();
  let title = '';
  let goal = String(presetGoal || '').trim();

  // If docType already chosen (from Skill Selector), skip the internal modal
  if (!docType) {
    const body = document.createElement('div');
    body.className = 'kp-modal-form-wrap';
    const form = document.createElement('div');
    form.className = 'kp-modal-form';

    const typeWrap = document.createElement('div');
    typeWrap.className = 'kp-modal-field';
    const typeLab = document.createElement('div');
    typeLab.className = 'kp-modal-label';
    typeLab.textContent = 'Loại tài liệu';
    const typeSelect = document.createElement('select');
    typeSelect.className = 'time-input kp-modal-input';
    supportedDocTypesList.forEach(k => {
      const opt = document.createElement('option');
      opt.value = k;
      opt.textContent = docDraftTypeLabel(k);
      typeSelect.appendChild(opt);
    });
    typeSelect.value = docType || 'srs';
    typeWrap.appendChild(typeLab);
    typeWrap.appendChild(typeSelect);

    const titleWrap = document.createElement('div');
    titleWrap.className = 'kp-modal-field';
    const titleLab = document.createElement('div');
    titleLab.className = 'kp-modal-label';
    titleLab.textContent = 'Tiêu đề (tuỳ chọn)';
    const titleInput = document.createElement('input');
    titleInput.className = 'time-input kp-modal-input';
    titleInput.type = 'text';
    titleInput.placeholder = 'Tự động';
    titleWrap.appendChild(titleLab);
    titleWrap.appendChild(titleInput);

    const goalWrap = document.createElement('div');
    goalWrap.className = 'kp-modal-field';
    const goalLab = document.createElement('div');
    goalLab.className = 'kp-modal-label';
    goalLab.textContent = 'Mục tiêu / yêu cầu';
    const goalInput = document.createElement('textarea');
    goalInput.className = 'time-input kp-modal-input';
    goalInput.placeholder = 'Ví dụ: Soạn thảo SRS cho luồng API đồng bộ dữ liệu Ecos - ATRS';
    goalInput.style.minHeight = '120px';
    goalWrap.appendChild(goalLab);
    goalWrap.appendChild(goalInput);

    const help = document.createElement('div');
    help.className = 'kp-modal-help';
    help.textContent = `Sẽ chạy skill dựa trên ${ids.length} tài liệu đã chọn.`;

    form.appendChild(typeWrap);
    form.appendChild(titleWrap);
    form.appendChild(goalWrap);
    form.appendChild(help);
    body.appendChild(form);

    const cfg = await kpOpenModal({
      title: '🚀 Chạy Skill',
      subtitle: 'Tạo bản nháp từ giỏ/graph selection',
      content: body,
      okText: 'Chạy',
      cancelText: 'Hủy',
      onOk: async () => {
        const t = String(typeSelect.value || '').trim().toLowerCase();
        if (!t) return { error: 'Vui lòng chọn loại tài liệu.' };
        return {
          docType: t,
          title: String(titleInput.value || '').trim(),
          goal: String(goalInput.value || '').trim(),
        };
      }
    });
    if (!cfg) return;
    docType = String(cfg.docType || '').trim().toLowerCase();
    title = String(cfg.title || '').trim();
    goal = String(cfg.goal || '').trim();
  }

  try {
    showToast('Đang đọc dữ liệu...', 'info');
    const response = await authFetch(`${API}/docs/drafts/from-documents`, {
      method: 'POST',
      body: JSON.stringify({
        doc_type: docType || 'srs',
        doc_ids: ids,
        goal,
        title: title || '',
      }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const draft = data && data.draft ? data.draft : null;
    if (!draft || !draft.id) throw new Error('Invalid draft response.');
    showToast(`Đã tạo bản nháp ${docDraftTypeLabel(docType)}.`, 'success');
    await openDocDraftEditor(draft.id);
  } catch (e) {
    showToast(e.message || 'Không thể chạy skill.', 'error');
  }
}


// Load saved theme
const savedTheme = localStorage.getItem('theme') || 'light';
if (savedTheme === 'dark') {
  document.documentElement.setAttribute('data-theme', 'dark');
  document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('themeToggle');
    if (btn) btn.textContent = '☀️';
  });
}

async function openDocDraftEditor(draftId) {
  try {
    const response = await authFetch(`${API}/docs/drafts/${draftId}`);
    if (!response.ok) throw new Error('Draft không tìm thấy');
    
    const data = await response.json();
    const draft = data.draft;
    
    const body = document.createElement('div');
    body.style.padding = '20px';
    
    const contentArea = document.createElement('textarea');
    contentArea.className = 'kp-modal-input';
    contentArea.value = draft.content || '';
    contentArea.style.minHeight = '400px';
    contentArea.style.fontFamily = 'monospace';
    
    body.appendChild(contentArea);
    
    const modal = kpOpenModal({
      title: `Chỉnh sửa Draft: ${draft.title}`,
      content: body,
      okText: 'Lưu',
      cancelText: 'Đóng',
      onOk: async () => {
        try {
          const response = await authFetch(`${API}/docs/drafts/${draftId}`, {
            method: 'PUT',
            body: JSON.stringify({
              content: contentArea.value
            })
          });
          if (!response.ok) throw new Error('Lưu thất bại');
          showToast('Draft đã lưu', 'success');
          return true;
        } catch (e) {
          showToast(`Lỗi: ${e.message}`, 'error');
          return false;
        }
      }
    });
  } catch (e) {
    showToast(`Lỗi: ${e.message}`, 'error');
  }
}

function toggleTheme() {
  const html = document.documentElement;
  if (html.getAttribute('data-theme') === 'dark') {
    html.removeAttribute('data-theme');
    document.getElementById('themeToggle').textContent = '🌙';
    localStorage.setItem('theme', 'light');
  } else {
    html.setAttribute('data-theme', 'dark');
    document.getElementById('themeToggle').textContent = '☀️';
    localStorage.setItem('theme', 'dark');
  }
}

// ── Init ──
checkHealth();
setInterval(checkHealth, 30000);
setInterval(Connectors.loadConnectorStats, 450000);

const searchInput = document.getElementById('searchInput');
if (searchInput) {
  searchInput.addEventListener('keydown', e => {
    if (e.key === 'Enter') Chat.doSearch();
  });
}

setInterval(Tasks.loadTasksCount, 30000);

// Helper functions for module actions
async function deleteDraft(draftId) {
  if (!confirm('Xóa bản nháp này?')) return;
  try {
    const response = await authFetch(`${API}/docs/drafts/${draftId}`, { method: 'DELETE' });
    if (!response.ok) throw new Error('Xóa thất bại');
    showToast('Bản nháp đã xóa', 'success');
    Drafts.loadDraftsPage();
  } catch (e) {
    showToast(`Lỗi: ${e.message}`, 'error');
  }
}

async function confirmTask(taskId) {
  try {
    const response = await authFetch(`${API}/tasks/${taskId}/confirm`, { method: 'POST' });
    if (!response.ok) throw new Error('Confirm thất bại');
    showToast('Công việc đã confirm', 'success');
    Tasks.loadTasks();
  } catch (e) {
    showToast(`Lỗi: ${e.message}`, 'error');
  }
}

async function rejectTask(taskId) {
  try {
    const response = await authFetch(`${API}/tasks/${taskId}/reject`, { method: 'POST' });
    if (!response.ok) throw new Error('Reject thất bại');
    showToast('Công việc đã đặt lại', 'success');
    Tasks.loadTasks();
  } catch (e) {
    showToast(`Lỗi: ${e.message}`, 'error');
  }
}

function editUser(userId) {
  showToast(`Chỉnh sửa người dùng ${userId} (Tính năng đang phát triển)`, 'info');
}

// Expose handlers referenced from inline `onclick="..."` attributes.
Chat.setChatCallbacks({ navigate, openDocDraftEditor });
Graph.setGraphGenerateDocCallback(generateDocFromDocuments);
Object.assign(window, {
  ...Basket,
  ...Graph,
  ...Admin,
  ...Connectors,
  ...Tasks,
  ...Chat,
  ...Drafts,
  ...PromptsModule,
  // Override import to inject app specific functionality preventing cyclic dependency
  basketRunSkill: () => Basket.basketRunSkill(generateDocFromDocuments),
  doLogin,
  doLogout,
  navigate,
  openDocDraftEditor,
  toggleTheme,
});
