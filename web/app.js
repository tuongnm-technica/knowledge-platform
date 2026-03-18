// app.js - Optimized Main entry
import { formatTime, safeHostname, parseThinking, getSourceIcon, getBadgeClass, formatRelevancePercent } from './utils/format.js?v=3';
import { API, AUTH, authFetch, tryRefresh, setAuthExpiredHandler } from './api/client.js?v=3';
import { readApiError, escapeHtml, formatDateTime, formatNumber, showToast, kpOpenModal, kpConfirm, kpPrompt, _kpBuildModalField } from './utils/ui.js?v=3';

import * as Basket from './modules/basket.js?v=3';
import * as Graph from './modules/graph.js?v=3';
import * as Admin from './modules/admin.js?v=3';
import * as Connectors from './modules/connectors.js?v=3';
import * as Tasks from './modules/tasks.js?v=3';
import * as Chat from './modules/chat.js?v=3';
import * as Drafts from './modules/drafts.js?v=3';
import * as PromptsModule from './modules/prompts.js?v=3';
import * as Memory from './modules/memory.js?v=3';

console.log('[App] Starting v3.2');

setAuthExpiredHandler(() => {
  AUTH.clear();
  location.reload();
});

// ── Login / Logout / Theme ───────────────────────────────────────────────────

async function doLogin() {
  const email = document.getElementById('loginEmail')?.value.trim();
  const pwd   = document.getElementById('loginPwd')?.value;
  const err   = document.getElementById('loginError');
  const btn   = document.getElementById('loginBtn');
  if (!email || !pwd) {
    if (err) { err.textContent = 'Vui lòng nhập đầy đủ thông tin'; err.style.display = 'block'; }
    return;
  }
  if (btn) btn.disabled = true;
  const btnText = document.getElementById('loginBtnText');
  if (btnText) btnText.textContent = 'Đang đăng nhập...';
  if (err) err.style.display = 'none';
  try {
    const r = await fetch(API + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password: pwd }),
    });
    if (!r.ok) {
      const d = await r.json().catch(() => ({}));
      if (err) { err.textContent = d.detail || 'Email hoặc mật khẩu không đúng'; err.style.display = 'block'; }
      return;
    }
    AUTH.save(await r.json());
    hideLoginScreen();
  } catch {
    if (err) { err.textContent = 'Không kết nối được server. Kiểm tra API đang chạy.'; err.style.display = 'block'; }
  } finally {
    if (btn) btn.disabled = false;
    if (btnText) btnText.textContent = 'Đăng nhập';
  }
}

function doLogout() {
  AUTH.clear();
  location.reload();
}

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('kp_theme', next);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = next === 'dark' ? '☀️' : '🌙';
}

// Apply saved theme on load
(function applyTheme() {
  const saved = localStorage.getItem('kp_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
  const btn = document.getElementById('themeToggle');
  if (btn) btn.textContent = saved === 'dark' ? '☀️' : '🌙';
})();

// ── Screen management ────────────────────────────────────────────────────────

function hideLoginScreen() {
  console.log('[App] hideLoginScreen');
  const s = document.getElementById('login-screen');
  if (s) {
    s.style.opacity = '0';
    s.style.pointerEvents = 'none';
    setTimeout(() => s.remove(), 300);
  }
  
  applyUser(AUTH.user);
  
  // Initial data load
  Basket.updateBasketBadges();
  Tasks.loadTasksCount();
  checkHealth();
  Connectors.loadConnectorStats();
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
  if (rl) rl.textContent = u.is_admin ? 'Quản trị viên' : 'Thành viên';
  if (navUsers) navUsers.style.display = u.is_admin ? 'flex' : 'none';
  if (navGraph) navGraph.style.display = u.is_admin ? 'flex' : 'none';
  if (clearBtn) clearBtn.style.display = u.is_admin ? '' : 'none';
  if (clearAllBtn) clearAllBtn.style.display = u.is_admin ? '' : 'none';
  if (addConnBtn) addConnBtn.style.display = u.is_admin ? '' : 'none';
  if (syncJiraBtn) syncJiraBtn.style.display = u.is_admin ? '' : 'none';
}

async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const d = await r.json();
    // API returns { status: 'ok'|'degraded', components: { postgresql: 'ok', qdrant: 'ok', ... }}
    const coreOk = d.status === 'ok'
      || (d.components?.postgresql === 'ok' && d.components?.qdrant === 'ok')
      || d.postgresql === 'ok';
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (d.status === 'degraded') {
      if (dot) dot.style.background = 'var(--warn)';
      if (txt) txt.textContent = 'Hệ thống hoạt động (một phần)';
    } else if (coreOk) {
      if (dot) dot.style.background = 'var(--success)';
      if (txt) txt.textContent = 'Hệ thống hoạt động';
    } else {
      if (dot) dot.style.background = 'var(--danger)';
      if (txt) txt.textContent = 'Hệ thống gặp lỗi';
    }
  } catch (e) {
    console.warn('[App] Health fail', e);
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (dot) dot.style.background = 'var(--danger)';
    if (txt) txt.textContent = 'Không kết nối được API';
  }
}

// ── Navigation ───────────────────────────────────────────────────────────────

const PAGE_TITLES = {
  chat: 'Chat AI',
  search: 'Search',
  basket: 'Giỏ Ngữ Cảnh',
  drafts: 'Drafts',
  tasks: 'AI Task Drafts',
  connectors: 'Connectors',
  history: 'Lịch sử Chat',
  users: 'Users & Permissions',
  graph: 'Knowledge Graph',
  prompts: 'Skill Prompts',
  memory: '🧠 Project Memory',
};

function navigate(target, navEl) {
  console.log('[App] Navigate ->', target);
  
  // Hide all pages
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  
  // Show target page
  const page = document.getElementById('page-' + target);
  if (page) {
    page.classList.add('active');
    
    // Module specific loading
    if (target === 'connectors') Connectors.loadConnectorStats();
    if (target === 'users') Admin.loadUsersAdmin();
    if (target === 'graph') Graph.loadGraphDashboard();
    if (target === 'drafts') Drafts.loadDraftsPage(true);
    if (target === 'tasks') Tasks.loadTasks();
    if (target === 'basket') Basket.renderBasket();
    if (target === 'prompts') PromptsModule.loadPromptsPage();
    if (target === 'memory') {
      Memory.loadMemoryPage();
      window._memRefresh = Memory.loadMemoryPage;
    }
  }

  // Update nav active state
  document.querySelectorAll('.nav-item').forEach(li => li.classList.remove('active'));
  if (navEl) {
    navEl.classList.add('active');
  } else {
    // Fallback: try to find nav item by id
    const navItem = document.getElementById('nav-' + target) 
      || document.querySelector(`.nav-item[onclick*="'${target}'"]`);
    if (navItem) navItem.classList.add('active');
  }

  // Update page title
  const titleEl = document.getElementById('pageTitle');
  if (titleEl) titleEl.textContent = PAGE_TITLES[target] || target;
}

// Attach event listeners
window.addEventListener('DOMContentLoaded', () => {
    if (AUTH.token && !AUTH.isExpired()) {
        hideLoginScreen();
    }
});

// Expose globals for HTML inline call
Object.assign(window, {
  ...Basket,
  ...Graph,
  ...Admin,
  ...Connectors,
  ...Tasks,
  ...Chat,
  ...Drafts,
  ...PromptsModule,
  navigate,
  doLogin,
  doLogout,
  toggleTheme,
  showToast,
  escapeHtml,
  kpOpenModal,
  kpConfirm,
  // Specific alias to avoid binding issues
  removeFromBasket: (id) => Basket.removeFromBasket(id),
  addNodeToBasket: (id, title) => Basket.addToBasket(id, title),
  openBasketDrawer: () => Basket.renderBasket(),
});
