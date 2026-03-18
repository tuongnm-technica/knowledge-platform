// app.js - Optimized Main entry
import { formatTime, safeHostname, parseThinking, getSourceIcon, getBadgeClass, formatRelevancePercent } from './utils/format.js';
import { API, AUTH, authFetch, tryRefresh, setAuthExpiredHandler } from './api/client.js';
import { readApiError, escapeHtml, formatDateTime, formatNumber, showToast, kpOpenModal, kpConfirm, _kpBuildModalField } from './utils/ui.js';

import * as Basket from './modules/basket.js';
import * as Graph from './modules/graph.js';
import * as Admin from './modules/admin.js';
import * as Connectors from './modules/connectors.js';
import * as Tasks from './modules/tasks.js';
import * as Chat from './modules/chat.js';
import * as Drafts from './modules/drafts.js';
import * as PromptsModule from './modules/prompts.js';

console.log('[App] Starting v3.1');

setAuthExpiredHandler(() => {
  AUTH.clear();
  location.reload();
});

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
  
  if (el) el.textContent = (name[0] || 'U').toUpperCase();
  if (nm) nm.textContent = name;
  if (rl) rl.textContent = u.is_admin ? 'Quản trị' : 'Thành viên';
  if (navUsers) navUsers.style.display = u.is_admin ? 'flex' : 'none';
  if (navGraph) navGraph.style.display = u.is_admin ? 'flex' : 'none';
}

async function checkHealth() {
  try {
    const r = await fetch(`${API}/health`);
    const d = await r.json();
    const isOk = d.status === 'ok';
    const dot = document.getElementById('statusDot');
    const txt = document.getElementById('statusText');
    if (dot) dot.style.background = isOk ? '#48bb78' : '#f56565';
    if (txt) txt.textContent = isOk ? 'He thong Online' : 'He thong gap loi';
  } catch (e) {
    console.warn('[App] Health fail', e);
  }
}

function navigate(target) {
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
  }

  // Update nav active state
  document.querySelectorAll('.nav-item').forEach(li => {
    li.classList.toggle('active', li.id === 'nav-' + target);
  });
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
  showToast,
  escapeHtml,
  // Specific alias to avoid binding issues
  removeFromBasket: (id) => Basket.removeFromBasket(id),
  addNodeToBasket: (id, title) => Basket.addToBasket(id, title),
  openBasketDrawer: () => Basket.renderBasket() // simplified toggle logic elsewhere
});
