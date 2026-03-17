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
      err.textContent = d.detail || 'Email hoặc mật khẩu không đúng';
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
  s.style.transition = 'opacity .3s';
  setTimeout(() => s.remove(), 300);
  applyUser(AUTH.user);
  Basket.renderBasket();
  Basket.updateBasketBadges();
  Tasks.loadTasksCount();
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
  if (navUsers) navUsers.style.display = u.is_admin ? '' : 'none';
  if (navGraph) navGraph.style.display = u.is_admin ? '' : 'none';
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
let chatHistory = [];
let currentUserId = '';
let adminDirectory = { users: [], groups: [] };
let connectorDirectory = { summary: null, tabs: [] };
let connectorIndex = {};
let connectorActiveTab = localStorage.getItem('kp_connector_tab') || 'confluence';
let connectorDiagnostics = {};
let connectorScopeCache = {};
let tasksDirectory = { drafts: [] };
let taskSelection = new Set();
let taskGroupCollapsed = {};
let assistantMessageStore = {};
let userEditorState = null;
let groupEditorState = null;

// ── Navigation ──
function navigate(page, el) {
  let targetPage = page;
  let targetEl = el;
  if (page === 'users' && !AUTH.user.is_admin) {
    targetPage = 'chat';
    targetEl = document.querySelector('.nav-item');
    showToast('Users admin requires admin access.', 'error');
  }
  if (page === 'graph' && !AUTH.user.is_admin) {
    targetPage = 'chat';
    targetEl = document.querySelector('.nav-item');
    showToast('Knowledge graph requires admin access.', 'error');
  }
  document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
  if (targetEl) targetEl.classList.add('active');
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById('page-' + targetPage).classList.add('active');
  if (targetPage === 'tasks') Tasks.loadTasks();
  if (targetPage === 'connectors') Connectors.loadConnectorStats(true);
  if (targetPage === 'basket') Basket.loadBasketPage();
  if (targetPage === 'drafts') loadDraftsPage(true);
  if (targetPage === 'users') Admin.loadUsersAdmin();
  if (targetPage === 'graph') Graph.loadGraphDashboard(true);
  const titles = { chat: 'Chat AI', search: 'Search', basket: 'Giỏ Ngữ Cảnh', drafts: 'Drafts', tasks: '🤖 AI Tasks', connectors: 'Connectors', history: 'Lịch sử Chat', users: 'Users & Permissions' };
  if (targetPage === 'graph') {
    document.getElementById('pageTitle').textContent = 'Knowledge Graph';
  } else {
    document.getElementById('pageTitle').textContent = titles[targetPage] || targetPage;
  }
  if (targetPage === 'history') 

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

// ── User ──
function updateUser() {
  applyUser(AUTH.user);
}

// ── Chat ──
function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

function useSuggestion(el) {
  document.getElementById('chatInput').value = el.textContent;
  document.getElementById('emptyState') && (document.getElementById('emptyState').style.display = 'none');
  sendMessage();
}

/* moved to ./utils/format.js
function formatTime() {
  return new Date().toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' });
}

function getSourceIcon(source) {
  if (source === 'confluence') return '📘';
  if (source === 'jira') return '🟣';
  if (source === 'slack') return '💬';
  return '📄';
}

function getBadgeClass(source) {
  if (source === 'confluence') return 'badge-confluence';
  if (source === 'jira') return 'badge-jira';
  if (source === 'slack') return 'badge-slack';
  return 'badge-confluence';
}

function parseThinking(content) {
  // Tách <think>...</think> ra khỏi answer
  const thinkMatch = content.match(/<think>([\s\S]*?)<\/think>/i);
  const thinking = thinkMatch ? thinkMatch[1].trim() : null;
  const answer   = content.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
  return { thinking, answer };
}

function safeHostname(url) {
  try {
    return new URL(url).hostname;
  } catch {
    return '';
  }
}

function formatRelevancePercent(score) {
  const n = Number(score);
  if (!Number.isFinite(n) || n <= 0) return '';

  // Heuristic: backend scores are often 0-3 (LLM relevance), sometimes 0-1.
  let pct = 0;
  if (n <= 1.00001) pct = n * 100;
  else if (n <= 3.5) pct = (n / 3) * 100;
  else if (n <= 100) pct = n;
  else pct = 100;

  pct = Math.max(0, Math.min(100, pct));
  return pct.toFixed(0) + '%';
}

*/

function buildAgentStepsHTML(steps, usedTools, plan) {
  if (!steps || steps.length === 0) return '';
  const toolIcons = {
    search_confluence: '\u{1F4D8}', search_jira: '\u{1F7E3}', search_slack: '\u{1F4AC}',
    search_files: '\u{1F4C1}', search_all: '\u{1F50D}',
    get_jira_issue: '\u{1F7E3}', list_jira_issues: '\u{1F7E3}',
    get_slack_messages: '\u{1F4AC}', summarize_document: '\u{1F4C4}',
  };
  let planHTML = '';
  if (plan && plan.length > 0) {
    const planItems = plan.map(p =>
      `<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        <span style="background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:1px 7px;font-size:10px;color:var(--text-muted);font-weight:600">${p.step}</span>
        <span style="font-size:11px;color:var(--accent)">${toolIcons[p.tool]||'\u{1F527}'} ${p.tool}</span>
        <span style="font-size:11px;color:var(--text-dim)">\u2014 ${p.reason}</span>
      </div>`
    ).join('');
    planHTML = `<div style="padding:10px 14px;border-bottom:1px solid var(--border);background:rgba(99,179,237,.03)">
      <div style="font-size:10px;font-weight:600;letter-spacing:.5px;color:var(--text-dim);margin-bottom:8px;text-transform:uppercase">&#128506;&#65039; K&#7871; ho&#7841;ch</div>
      ${planItems}
    </div>`;
  }
  const stepsHTML = steps.map((s) => {
    const obs = s.observation
      ? `<div style="margin-top:6px;padding:6px 10px;background:var(--bg);border-radius:6px;font-size:11px;color:var(--text-muted);border-left:2px solid var(--accent3)">${s.observation.substring(0,300)}${s.observation.length>300?'...':''}</div>`
      : '';
    const action = s.action
      ? `<div style="color:var(--accent);font-size:11px;margin-top:4px">${toolIcons[s.action]||'\u{1F527}'} <b>${s.action}</b>(${JSON.stringify(s.action_input||{}).substring(0,80)})</div>`
      : '';
    const badge = s.is_final
      ? `<span style="background:rgba(104,211,145,.15);color:var(--accent3);border-radius:4px;padding:1px 6px;font-size:10px;margin-left:6px">&#10003; Final</span>`
      : `<span style="background:var(--bg3);color:var(--text-dim);border-radius:4px;padding:1px 6px;font-size:10px;margin-left:6px">Step ${s.iteration}</span>`;
    return `<div style="padding:10px 14px;border-bottom:1px solid var(--border)">
      <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px">${badge}</div>
      <div style="font-size:12px;color:var(--text)">&#128161; ${s.thought.substring(0,200)}</div>
      ${action}${obs}
    </div>`;
  }).join('');
  const toolBadges = [...new Set(usedTools||[])].map(t =>
    `<span style="background:var(--bg3);border:1px solid var(--border);border-radius:20px;padding:2px 8px;font-size:10px;color:var(--text-muted)">${toolIcons[t]||'\u{1F527}'} ${t}</span>`
  ).join(' ');
  return `<div class="thinking-block">
    <div class="thinking-toggle" onclick="toggleThinking(this)">
      <span class="thinking-icon">&#129504;</span>
      <span>Agent reasoning (${steps.length} b\u01b0\u1edbc \u00b7 ${toolBadges||'no tools'})</span>
      <span class="thinking-chevron">&#9662;</span>
    </div>
    <div class="thinking-content" style="display:none;padding:0">${planHTML}${stepsHTML}</div>
  </div>`;
}

function renderAnswer(text) {
  // Xóa [Source: ...] text do LLM tự sinh ra
  text = text.replace(/\[Source[s]?:?[^\]]*\]/gi, '').trim();
  // Escape HTML rồi format markdown cơ bản
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="background:var(--bg3);padding:1px 5px;border-radius:4px;font-size:12px">$1</code>')
    .replace(/\n/g, '<br>');
}

function appendMessage(role, content, sources = [], agentSteps = [], usedTools = [], agentPlan = [], meta = {}) {
  const empty = document.getElementById('emptyState');
  if (empty) empty.remove();

  const wrap = document.getElementById('chatMessages');
  const div  = document.createElement('div');
  div.className = `message ${role}`;

  const avatarHTML = role === 'user'
    ? `<div class="msg-avatar user-av">${document.getElementById('sidebarAvatar').textContent}</div>`
    : `<div class="msg-avatar ai-av">🤖</div>`;

  // Tách thinking và answer
  let thinkingHTML = '';
  let displayContent = content;

  if (role === 'assistant') {
    const { thinking, answer } = parseThinking(content);
    displayContent = answer;

    if (agentSteps && agentSteps.length > 0) {
      thinkingHTML = buildAgentStepsHTML(agentSteps, usedTools, agentPlan);
    } else if (thinking) {
      thinkingHTML = `
        <div class="thinking-block">
          <div class="thinking-toggle" onclick="toggleThinking(this)">
            <span class="thinking-icon">🧠</span>
            <span>Quá trình suy nghĩ</span>
            <span class="thinking-chevron">▾</span>
          </div>
          <div class="thinking-content">${thinking.replace(/\n/g, '<br>')}</div>
        </div>`;
    }
  }

  // Sources
  let sourcesHTML = '';
  if (sources && sources.length > 0) {
    const items = sources
      .filter(s => s.title && s.title !== 'Unknown' && s.url)
      .map(s => `
        <a class="source-item" href="${s.url}" target="_blank">
          <span class="source-icon">${getSourceIcon(s.source)}</span>
          <div class="source-info">
            <div class="source-title">${s.title}</div>
            <div class="source-meta">${s.source || ''} · ${s.url ? safeHostname(s.url) : ''}</div>
          </div>
          <span class="source-score">${formatRelevancePercent(s.score) || ''}</span>
        </a>`).join('');

    if (items) {
      sourcesHTML = `
        <div class="sources-list">
          <div class="source-label">📎 NGUỒN THAM KHẢO</div>
          ${items}
        </div>`;
    }
  }

  const msgId = 'msg-' + Date.now();

  if (role === 'assistant' && meta && meta.question) {
    assistantMessageStore[msgId] = {
      question: String(meta.question || ''),
      answer: String(displayContent || ''),
      sources: (sources || []).slice(0, 12),
    };
  }

  // Build sources panel (hidden by default)
  let sourcesPanelHTML = '';
  const validSources = (sources || []).filter(s => s.title || s.url || s.source);
  if (role === 'assistant' && validSources.length > 0) {
    const items = validSources.map(s => {
      const href = s.url ? `href="${s.url}" target="_blank"` : '';
      const title = s.title && s.title !== 'Unknown' ? s.title : (s.url ? s.url.split('/').pop() : 'Tài liệu');
      const score = formatRelevancePercent(s.score);
      const snippet = escapeHtml(String(s.snippet || s.quote || s.content || '').trim()).substring(0, 420);
      const docId = String(s.document_id || '').trim();
      const pinBtn = docId
        ? `<button class="pin-mini" onclick="event.preventDefault(); event.stopPropagation(); basketAddDocument('${docId}')">📌</button>`
        : '';
      return `<a class="source-item" ${href} data-snippet="${snippet}" onmouseenter="showCitationPeek(event)" onmouseleave="hideCitationPeek()">
        <span class="source-icon">${getSourceIcon(s.source)}</span>
        <div class="source-info">
          <div class="source-title">${title}</div>
          <div class="source-meta">${s.source || ''}</div>
        </div>
        ${score ? `<span class="source-score">${score}</span>` : ''}
        ${pinBtn}
      </a>`;
    }).join('');
    sourcesPanelHTML = `
      <div class="sources-panel" id="sp-${msgId}" style="display:none">
        <div class="sources-panel-header">📎 Nguồn tham khảo (${validSources.length})</div>
        ${items}
      </div>`;
  }

  // Footer với time + sources toggle btn
  const sourcesBtn = (role === 'assistant' && validSources.length > 0)
    ? `<button class="sources-toggle-btn" onclick="toggleSources('sp-${msgId}', this)">
        📎 ${validSources.length} nguồn
       </button>`
    : '';

  const taskBtn = (role === 'assistant' && assistantMessageStore[msgId])
    ? `<button class="sources-toggle-btn" onclick="createTaskFromAnswer('${msgId}')">🧾 Create task</button>`
    : '';

  const docDraftBtn = (role === 'assistant' && assistantMessageStore[msgId] && (assistantMessageStore[msgId].sources || []).some(s => s && s.document_id))
    ? `<button class="sources-toggle-btn" onclick="generateDocFromAnswer('${msgId}')">✨ Tạo draft</button>`
    : '';

  div.innerHTML = `
    ${avatarHTML}
    <div class="msg-body">
      ${thinkingHTML}
      <div class="msg-bubble">${renderAnswer(displayContent)}</div>
      ${sourcesPanelHTML}
      <div class="msg-footer">
        <span class="msg-time-inline">${formatTime()}</span>
        ${taskBtn}
        ${docDraftBtn}
        ${sourcesBtn}
      </div>
    </div>`;

  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
  return div;
}

function toggleSources(id, btn) {
  const panel = document.getElementById(id);
  if (!panel) return;
  const isOpen = panel.style.display !== 'none';
  panel.style.display = isOpen ? 'none' : 'block';
  btn.classList.toggle('active', !isOpen);
}

// Citations Quick Peek (hover popover)
let _citationPeekEl = null;
let _citationPeekHideTimer = null;

function _ensureCitationPeek() {
  if (_citationPeekEl) return _citationPeekEl;
  const el = document.createElement('div');
  el.className = 'citation-peek';
  el.style.display = 'none';
  document.body.appendChild(el);
  _citationPeekEl = el;
  return el;
}

function showCitationPeek(ev) {
  const a = ev && ev.currentTarget;
  if (!a) return;
  const snippet = String(a.getAttribute('data-snippet') || '').trim();
  if (!snippet) return;

  if (_citationPeekHideTimer) {
    clearTimeout(_citationPeekHideTimer);
    _citationPeekHideTimer = null;
  }

  const el = _ensureCitationPeek();
  el.innerHTML = `<div class="citation-peek-title">Quick peek</div><div class="citation-peek-body">${snippet}</div>`;
  el.style.display = 'block';

  const rect = a.getBoundingClientRect();
  const pad = 10;
  const maxW = Math.min(520, window.innerWidth - pad * 2);
  el.style.maxWidth = maxW + 'px';

  const desiredTop = rect.top + window.scrollY - 10;
  const desiredLeft = rect.left + window.scrollX + 10;

  // Place above if near bottom
  const elRect = el.getBoundingClientRect();
  let top = desiredTop - elRect.height;
  if (top < (window.scrollY + pad)) {
    top = rect.bottom + window.scrollY + 8;
  }
  let left = desiredLeft;
  if (left + elRect.width > window.scrollX + window.innerWidth - pad) {
    left = window.scrollX + window.innerWidth - pad - elRect.width;
  }
  el.style.top = Math.max(window.scrollY + pad, top) + 'px';
  el.style.left = Math.max(window.scrollX + pad, left) + 'px';
}

function hideCitationPeek() {
  if (!_citationPeekEl) return;
  if (_citationPeekHideTimer) clearTimeout(_citationPeekHideTimer);
  _citationPeekHideTimer = setTimeout(() => {
    if (_citationPeekEl) _citationPeekEl.style.display = 'none';
  }, 60);
}

function toggleThinking(el) {
  const content = el.nextElementSibling;
  const chevron = el.querySelector('.thinking-chevron');
  const isOpen  = content.style.display !== 'none';
  content.style.display = isOpen ? 'none' : 'block';
  chevron.textContent   = isOpen ? '▸' : '▾';
}

function appendTyping() {
  const wrap = document.getElementById('chatMessages');
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.id = 'typingMsg';
  div.innerHTML = `
    <div class="msg-avatar ai-av">🤖</div>
    <div class="msg-body">
      <div class="msg-bubble">
        <div class="typing-indicator">
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
          <div class="typing-dot"></div>
        </div>
      </div>
    </div>`;
  wrap.appendChild(div);
  wrap.scrollTop = wrap.scrollHeight;
  return div;
}

async function syncConnector(name) {
  const conn = connectorIndex[String(name || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }
  const button = document.querySelector(`[data-connector-sync="${name}"]`);
  if (button) {
    button.disabled = true;
    button.classList.add('syncing');
    button.innerHTML = '<span class="spin">⟳</span> Syncing...';
  }

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}/sync`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json().catch(() => ({}));
    if (String(data.status || '') !== 'started') {
      showToast(data.reason || 'Sync skipped.', 'info');
      await loadConnectorStats(true);
      return;
    }

    const connectorKey = String(data.connector || `${conn.connector_type}:${conn.instance_id}`);
    showToast('Đã bắt đầu sync. Đang theo dõi tiến độ...', 'success');
    await openSyncProgressModal({
      title: `Sync progress`,
      connectors: [connectorKey],
    });
  } catch (error) {
    showToast(error.message || `Cannot sync ${name}.`, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.classList.remove('syncing');
      button.innerHTML = 'Sync now';
    }
  }
}

async function createTaskFromAnswer(msgId) {
  const payload = assistantMessageStore[msgId];
  if (!payload) {
    showToast('No message context found.', 'error');
    return;
  }
  try {
    const response = await authFetch(`${API}/tasks/from-answer`, {
      method: 'POST',
      body: JSON.stringify({
        question: payload.question,
        answer: payload.answer,
        sources: payload.sources || [],
      }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast('Task draft created from this answer.', 'success');
    await Tasks.loadTasksCount();
    navigate('tasks', document.getElementById('nav-tasks'));
    await Tasks.loadTasks();
  } catch (error) {
    showToast(error.message || 'Cannot create task draft.', 'error');
  }
}

async function openSyncProgressModal({ title = 'Sync progress', connectors = [], skipped = [] } = {}) {
  const keys = Array.isArray(connectors) ? connectors.map(k => String(k || '').trim()).filter(Boolean) : [];
  if (!keys.length) return;

  const body = document.createElement('div');
  body.className = 'kp-modal-form-wrap';

  const header = document.createElement('div');
  header.className = 'kp-modal-help';
  header.textContent = 'Mẹo: bạn có thể đóng cửa sổ này; sync vẫn chạy ở background.';
  body.appendChild(header);

  const list = document.createElement('div');
  list.style.display = 'flex';
  list.style.flexDirection = 'column';
  list.style.gap = '10px';
  list.style.marginTop = '10px';
  body.appendChild(list);

  const skippedBox = document.createElement('div');
  skippedBox.className = 'kp-modal-help';
  skippedBox.style.marginTop = '10px';
  body.appendChild(skippedBox);

  function labelForKey(key) {
    const c = connectorIndex[String(key)] || null;
    if (c && c.name) return `${c.name} (${key})`;
    return key;
  }

  function renderRow(key, run) {
    const status = run ? String(run.status || '') : 'never';
    const fetched = run ? Number(run.fetched || 0) : 0;
    const indexed = run ? Number(run.indexed || 0) : 0;
    const errors = run ? Number(run.errors || 0) : 0;
    const startedAt = run ? (run.started_at || '') : '';

    const indeterminate = status === 'running' && fetched <= 0;
    const pct = (status !== 'running')
      ? 100
      : (fetched > 0 ? Math.max(0, Math.min(99, Math.round((indexed / Math.max(1, fetched)) * 100))) : 0);
    const barClass = indeterminate ? 'connector-progress indeterminate' : 'connector-progress';
    const color = errors > 0 ? `linear-gradient(90deg, var(--warn), var(--danger))` : `linear-gradient(90deg, var(--accent3), var(--accent))`;

    return `
      <div style="border:1px solid var(--border);border-radius:16px;padding:10px 10px;background:rgba(255,255,255,0.62)">
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:8px">
          <div style="font-weight:900">${escapeHtml(labelForKey(key))}</div>
          <div style="font-size:12px;color:var(--text-muted)">${escapeHtml(status)}${startedAt ? ` · ${escapeHtml(formatDateTime(startedAt))}` : ''}</div>
        </div>
        <div class="${barClass}"><div class="connector-progress-fill" style="width:${pct}%;background:${color}"></div></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;font-size:12px;color:var(--text-muted)">
          <span>Fetched ${formatNumber(fetched)}</span>
          <span>Indexed ${formatNumber(indexed)}</span>
          <span>Errors ${formatNumber(errors)}</span>
        </div>
      </div>
    `;
  }

  let stopped = false;
  let tick = 0;

  async function poll() {
    if (stopped) return;
    tick++;
    try {
      const r = await authFetch(`${API}/connectors/sync/status`, {
        method: 'POST',
        body: JSON.stringify({ connectors: keys }),
      });
      if (!r.ok) throw new Error(await readApiError(r));
      const data = await r.json();
      const statuses = (data && data.statuses) ? data.statuses : {};

      let doneCount = 0;
      list.innerHTML = keys.map(key => {
        const run = statuses[key] ? statuses[key].run : null;
        if (run && String(run.status || '') !== 'running' && run.finished_at) doneCount++;
        return renderRow(key, run);
      }).join('');

      if (Array.isArray(skipped) && skipped.length) {
        const txt = skipped.slice(0, 10).map(s => `${s.connector || ''}: ${s.reason || ''}`.trim()).filter(Boolean).join(' · ');
        skippedBox.textContent = `Skipped: ${txt}${skipped.length > 10 ? ' ...' : ''}`;
        skippedBox.style.display = '';
      } else {
        skippedBox.style.display = 'none';
      }

      if (doneCount === keys.length) {
        stopped = true;
        showToast('Sync hoàn tất.', 'success');
        await loadConnectorStats(true);
      }
    } catch (e) {
      if (tick <= 2) {
        // ignore transient on start
      } else {
        showToast(e.message || 'Không lấy được tiến độ sync.', 'error');
      }
    }
  }

  await poll();
  const intervalId = setInterval(poll, 1200);

  await kpOpenModal({
    title,
    subtitle: `${keys.length} connector(s)`,
    content: body,
    okText: 'Đóng',
    cancelText: '',
    onOk: () => true,
  });

  stopped = true;
  clearInterval(intervalId);
  await loadConnectorStats(true);
}

async function loadDraftsPage(force = false) {
  if (!AUTH.token) return;
  const list = document.getElementById('draftsList');
  if (!list) return;
  if (!force && !document.getElementById('page-drafts')?.classList.contains('active')) return;

  const typeEl = document.getElementById('draftsTypeFilter');
  const docType = String(typeEl ? typeEl.value : '').trim();

  list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:40px">Loading drafts...</div>';
  try {
    const url = `${API}/docs/drafts?limit=120${docType ? `&doc_type=${encodeURIComponent(docType)}` : ''}`;
    const r = await authFetch(url);
    if (!r.ok) throw new Error(await readApiError(r));
    const data = await r.json();
    const drafts = (data && data.drafts) ? data.drafts : [];

    updateDraftsBadge(drafts.length);

    if (!drafts.length) {
      list.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:40px">Chưa có draft nào.</div>';
      return;
    }

    list.innerHTML = drafts.map(d => {
      const idRaw = String(d.id || '').trim();
      const id = escapeHtml(idRaw);
      const title = escapeHtml(String(d.title || 'Draft'));
      const type = escapeHtml(String(d.doc_type || ''));
      const st = escapeHtml(String(d.status || 'draft'));
      const updated = formatDateTime(d.updated_at || d.created_at);
      const srcIds = Array.isArray(d.source_document_ids) ? d.source_document_ids.length : (d.source_document_ids ? 1 : 0);
      const srcSnap = (d && d.source_snapshot && typeof d.source_snapshot === 'object') ? d.source_snapshot : {};
      const sources = Array.isArray(srcSnap.sources) ? srcSnap.sources : [];
      const sourcesHtml = sources.length
        ? `<div class="draft-sources">
            ${sources.slice(0, 5).map(s => {
              const ss = (s && typeof s === 'object') ? s : {};
              const src = escapeHtml(String(ss.source || ''));
              const url = String(ss.url || '').trim();
              const stitle = escapeHtml(String(ss.title || 'Untitled'));
              const icon = getSourceIcon(String(ss.source || ''));
              const link = url ? `<a href="${escapeHtml(url)}" target="_blank" rel="noreferrer">${stitle}</a>` : `<span>${stitle}</span>`;
              return `<div class="draft-source"><span>${icon}</span><span class="result-source-badge ${getBadgeClass(src)}">${src || 'doc'}</span>${link}</div>`;
            }).join('')}
            ${sources.length > 5 ? `<div class="draft-source"><span>…</span><span>${sources.length - 5} nguồn khác</span></div>` : ''}
          </div>`
        : '';
      return `
        <div class="draft-card" id="draft-${idRaw}">
          <div class="result-header" style="margin-bottom:6px">
            <span class="result-source-badge badge-confluence">${type || 'draft'}</span>
            <span class="result-title">${title}</span>
            <span class="result-score">${st}</span>
          </div>
          <div class="result-content">Updated: ${escapeHtml(updated || '—')} · Sources: ${formatNumber(srcIds)}</div>
          ${sourcesHtml}
          <div class="draft-actions">
            <button class="secondary-btn" onclick="openDocDraftEditor('${id}')">Edit</button>
            <button class="danger-btn" onclick="deleteDocDraft('${id}')">Delete</button>
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    list.innerHTML = `<div style="color:var(--danger);text-align:center;padding:40px">Cannot load drafts: ${escapeHtml(e.message || 'API error')}</div>`;
  }
}

function updateDraftsBadge(count) {
  const badge = document.getElementById('draftsBadge');
  if (!badge) return;
  const n = Number(count || 0) || 0;
  badge.textContent = String(n);
  badge.style.display = n ? '' : 'none';
}

async function loadDraftsCount() {
  try {
    const r = await authFetch(`${API}/docs/drafts?limit=200`);
    if (!r.ok) return;
    const data = await r.json();
    const drafts = (data && data.drafts) ? data.drafts : [];
    updateDraftsBadge(Array.isArray(drafts) ? drafts.length : 0);
  } catch {}
}

async function deleteDocDraft(draftId) {
  const id = String(draftId || '').trim();
  if (!id) return;
  const ok = await kpConfirm({
    title: 'Xóa draft',
    message: 'Bạn chắc chắn muốn xóa draft này?',
    okText: 'Xóa',
    cancelText: 'Hủy',
    danger: true,
  });
  if (!ok) return;

  try {
    const r = await authFetch(`${API}/docs/drafts/${encodeURIComponent(id)}`, { method: 'DELETE' });
    if (!r.ok) throw new Error(await readApiError(r));
    const el = document.getElementById(`draft-${id}`);
    if (el) el.remove();
    showToast('Đã xóa draft.', 'success');
    await loadDraftsCount();
  } catch (e) {
    showToast(e.message || 'Không thể xóa draft.', 'error');
  }
}

function docDraftTypeLabel(docType) {
  const key = String(docType || '').trim().toLowerCase();
  // TODO: This should be fetched from an API to stay in sync with the backend.
  // For now, we can create a simple mapping for display purposes.
  const labels = {
    srs: 'SRS',
    brd: 'BRD',
    api_spec: 'API Spec',
    use_cases: 'Use Cases',
    validation_rules: 'Validation Rules',
    user_stories: 'User Stories',
    requirements_intake: 'Requirements Intake',
    requirement_review: 'Requirement Review',
    solution_design: 'Solution Design',
    fe_spec: 'FE Spec',
    qa_test_spec: 'QA Test Spec',
    deployment_spec: 'Deployment Spec',
    change_request: 'Change Request',
    release_notes: 'Release Notes',
    function_list: 'Function List',
    risk_log: 'Risk Log',
  };
  return labels[key] || key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || 'Draft';
}

async function generateDocFromDocuments(docIds, presetDocType = '') {
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
  let goal = '';

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
  // TODO: Fetch this from an API endpoint, e.g., GET /docs/supported-types
  const supportedTypes = ['srs', 'brd', 'api_spec', 'use_cases', 'validation_rules', 'user_stories', 'requirements_intake', 'requirement_review', 'solution_design', 'fe_spec', 'qa_test_spec', 'deployment_spec', 'change_request', 'release_notes', 'function_list', 'risk_log'];
  supportedTypes.forEach(k => {
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
  } t. u
//fe') === 'dark';
    html.removeAttribute('data-theme');
    document.getElementById('themeToggle').textContent = '🌙';
    localStorage.setItem('theme', 'light');
  } else {
    html.setAttribute('data-theme', 'dark');
    document.getElementById('themeToggle').textContent = '☀️';
    localStorage.setItem('theme', 'dark');
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

// ── Init ──
checkHealth();
setInterval(checkHealth, 30000);
Connectors.loadConnectorStats();
setInterval(Connectors.loadConnectorStats, 450000);
document.getElementById('searchInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') Chat.doSearch();
});

async function loadTasksCount() {
  try {
    const response = await authFetch(`${API}/tasks/count`);
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json();
    updateTasksCount(data.count || 0);
  } catch (error) {
    console.warn('Cannot load task count:', error);
  }
}

function updateTasksCount(count) {
  const badge = document.getElementById('tasksBadge');
  const panel = document.getElementById('tasksPanelCount');

  if (badge) {
    badge.textContent = count;
    badge.style.display = count ? 'inline-block' : 'none';
  }
  if (panel) {
    panel.textContent = `${count} open`;
  }
}

function normalizeEvidence(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === 'string') {
    try {
      const parsed = JSON.parse(value);
      return Array.isArray(parsed) ? parsed : [];
    } catch {
      return [];
    }
  }
  return [];
}

function updateBulkBar() {
  const bar = document.getElementById('tasksBulkBar');
  const countEl = document.getElementById('tasksBulkCount');
  const count = taskSelection.size;
  if (countEl) countEl.textContent = `${count} selected`;
  if (bar) bar.style.display = count ? '' : 'none';
}

function toggleTaskSelect(id, checked) {
  const key = String(id);
  if (checked) taskSelection.add(key);
  else taskSelection.delete(key);
  updateBulkBar();
}

function clearTaskSelection() {
  taskSelection = new Set();
  document.querySelectorAll('input[data-task-select]').forEach(el => { el.checked = false; });
  updateBulkBar();
}

function selectedTaskIds() {
  return Array.from(taskSelection.values());
}

async function bulkConfirmTasks() {
  con ,;: 'POST',
      body: JSON.stringify({ ids }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Dismissed ${ids.length} tasks.`, 'success');
    clearTaskSelection();
    await loadTasks();
    await loadTasksCount();
  } catch (error) {
    showToast(error.message || 'Bulk dismiss failed.', 'error');
  }
}

async function bulkAssignTasks() {
  const ids = selectedTaskIds();
  if (!ids.length) return;
  const assigneeEl = document.getElementById('bulkAssigneeInput');
  const suggested_assignee = assigneeEl ? (assigneeEl.value || '').trim() : '';
  if (!suggested_assignee) {
    showToast('Please enter an assignee (email/name).', 'error');
    return;
  }
  try {
    const response = await authFetch(`${API}/tasks/batch/update`, {
      method: 'POST',
      body: JSON.stringify({ ids, suggested_assignee }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Assigned ${ids.length} tasks.`, 'success');
    clearTaskSelection();
    await loadTasks();
    showToast(error.message || 'Bulk assign failed.', 'error');
  }
}

async function bulkSetIssueType() {
  const ids = selectedTaskIds();
  if (!ids.length) return;
  const el = document.getElementById('bulkIssueTypeInput');
  const issue_type = el ? (el.value || '').trim() : '';
  if (!issue_type || !['Task', 'Story', 'Bug', 'Epic'].includes(issue_type)) {
    showToast('Issue type must be one of: Task, Story, Bug, Epic.', 'error');
    return;
  }
  try {
    const response = await authFetch(`${API}/tasks/batch/update`, {
      method: 'POST',
      body: JSON.stringify({ ids, issue_type }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Updated type for ${ids.length} tasks.`, 'success');
    await loadTasks();
  } catch (error) {
    showToast(error.message || 'Bulk update failed.', 'error');
  }
}

function toggleTaskGroup(groupId) {
  const key = String(groupId || '');
  taskGroupCollapsed[key] = !taskGroupCollapsed[key];
  const body = document.getElementById(`taskGroupBody-${key}`);
  const chev = document.getElementById(`taskGroupChevron-${key}`);
  if (body) body.style.display = taskGroupCollapsed[key] ? 'none' : 'block';
  if (chev) chev.textContent = taskGroupCollapsed[key] ? '▸' : '▾';
}

function setTaskSelection(ids, selected) {
  (ids || []).forEach(id => {
    const safeId = String(id || '');
    if (!safeId) return;
    if (selected) taskSelection.add(safeId); else taskSelection.delete(safeId);
    const input = document.querySelector(`input[data-task-select][data-task-id="${safeId}"]`);
    if (input) input.checked = selected;
  });
  updateBulkBar();
}

function selectTaskGroup(groupId, selected) {
  const gid = String(groupId || '');
  const group = (tasksDirectory.groups || []).find(g => String(g.id || '') === gid);
  if (!group) return;
  setTaskSelection(group.draft_ids || [], !!selected);
}

function renderTaskGroups(groups, drafts) {
  const byId = new Map();
  (drafts || []).forEach(d => byId.set(String(d.id || ''), d));

  return (groups || []).map(g => {
    const gid = String(g.id || '');
    const collapsed = !!taskGroupCollapsed[gid];
    const items = (g.draft_ids || []).map(id => byId.get(String(id || ''))).filter(Boolean);
    const cards = items.map(renderTaskCard).join('');
    const title = escapeHtml(g.title || gid);
    const count = Number(g.count || items.length || 0);
    return `
      <div class="task-group" data-group-id="${escapeHtml(gid)}">
        <div class="task-group-head">
          <button class="task-group-toggle" onclick="toggleTaskGroup('${escapeHtml(gid)}')" aria-label="Toggle group">
            <span id="taskGroupChevron-${escapeHtml(gid)}">${collapsed ? '▸' : '▾'}</span>
          </button>
          <div class="task-group-title">${title}</div>
          <span class="count-pill">${count} items</span>
          <div style="margin-left:auto;display:flex;gap:8px;align-items:center">
            <button class="secondary-btn mini" onclick="selectTaskGroup('${escapeHtml(gid)}', true)">Select</button>
            <button class="secondary-btn mini" onclick="selectTaskGroup('${escapeHtml(gid)}', false)">Clear</button>
          </div>
        </div>
        <div class="task-group-body" id="taskGroupBody-${escapeHtml(gid)}" style="display:${collapsed ? 'none' : 'block'}">
          ${cards || `<div class="tasks-empty">No items.</div>`}
        </div>
      </div>
    `;
  }).join('');
}

function renderTaskCard(draft) {
  const srcType = String(draft.source_type || '').toLowerCase();
  const srcIcon = srcType === 'slack' ? '💬' : (srcType === 'confluence' ? '📘' : '🤖');
  const srcRefSafe = escapeHtml(draft.source_ref || '');
  const srcLabel = srcType === 'slack' ? `Slack ${srcRefSafe}` : (srcType === 'confluence' ? 'Confluence' : 'Chat');
  const issueType = escapeHtml(draft.issue_type || 'Task');
  const issueTypeChip = `<span class="task-chip" style="background:rgba(15,118,110,0.10);border-color:rgba(15,118,110,0.18);color:var(--text)">#${issueType}</span>`;
  const status = String(draft.status || '');
  const statusPill = status === 'confirmed'
    ? `<span class="task-chip" style="background:#dcfce7;color:#166534;border:1px solid rgba(34,197,94,0.25)">Confirmed</span>`
    : (status === 'submitted'
      ? `<span class="task-chip" style="background:rgba(59,130,246,0.12);color:#1d4ed8;border:1px solid rgba(59,130,246,0.18)">Submitted</span>`
      : (status === 'done'
        ? `<span class="task-chip" style="background:rgba(34,197,94,0.12);color:#166534;border:1px solid rgba(34,197,94,0.18)">Done</span>`
        : ''));
  const priBadge = {
    High: 'background:#fee2e2;color:#b91c1c',
    Medium: 'background:#fef3c7;color:#b45309',
    Low: 'background:#dcfce7;color:#166534',
  }[draft.priority] || 'background:rgba(255,255,255,0.72);color:var(--text-muted)';
  const labels = (draft.labels || []).map(label => `<span class="task-chip">${label}</span>`).join('');
  const assignee = draft.suggested_assignee ? `<span class="task-chip">👤 ${escapeHtml(draft.suggested_assignee)}</span>` : '';
  const sourceLink = draft.source_url
    ? `<a class="task-chip" href="${escapeHtml(draft.source_url)}" target="_blank" rel="noopener" style="text-decoration:none">🔗 Open source</a>`
    : '';
  const jiraKey = String(draft.jira_key || '').trim();
  const jiraUrl = String(draft.jira_url || '').trim();
  const jiraLink = jiraKey && jiraUrl
    ? `<a class="task-chip" href="${escapeHtml(jiraUrl)}" target="_blank" rel="noopener" style="text-decoration:none">Jira ${escapeHtml(jiraKey)}</a>`
    : (jiraKey ? `<span class="task-chip">Jira ${escapeHtml(jiraKey)}</span>` : '');
  const jiraStatus = draft.suggested_fields && (draft.suggested_fields.jira_status || '');
  const jiraStatusChip = jiraStatus ? `<span class="task-chip">Jira: ${escapeHtml(jiraStatus)}</span>` : '';

  const summary = draft.source_summary
    ? `<div class="task-summary">${escapeHtml(draft.source_summary.substring(0, 180))}...</div>`
    : '';

  const isSelected = taskSelection.has(String(draft.id));
  const safeId = String(draft.id || '').replace(/'/g, '');
  const selectBox = `<label class="task-select"><input data-task-select data-task-id="${safeId}" type="checkbox" ${isSelected ? 'checked' : ''} onchange="toggleTaskSelect('${safeId}', this.checked)"></label>`;

  const evidenceItems = normalizeEvidence(draft.evidence);
  let evidenceMarkup = '';
  if (evidenceItems.length) {
    const items = evidenceItems.slice(0, 2).map(ev => {
      const evUrl = String(ev.url || '').trim();
      const evQuote = String(ev.quote || '').trim();
      const evSource = String(ev.source || '').trim();
      const evTitle = String(ev.title || '').trim();
      const link = evUrl ? `<a href="${escapeHtml(evUrl)}" target="_blank" rel="noopener" class="task-chip" style="text-decoration:none">Open</a>` : '';
      return `
        <div class="evidence-item">
          <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
            <span class="task-chip">${escapeHtml(evSource || 'source')}</span>
            ${evTitle ? `<span class="task-chip">${escapeHtml(evTitle)}</span>` : ''}
            ${link}
          </div>
          ${evQuote ? `<div class="evidence-quote">${escapeHtml(evQuote)}</div>` : ''}
        </div>
      `;
    }).join('');
    evidenceMarkup = `
      <div class="task-evidence">
        <div class="task-evidence-title">Evidence</div>
        ${items}
      </div>
    `;
  }

  const isLocked = status === 'submitted' || status === 'done';
  const primaryAction = isLocked
    ? (jiraUrl
      ? `<a href="${escapeHtml(jiraUrl)}" target="_blank" rel="noopener" class="task-action primary" style="text-decoration:none;display:inline-flex;align-items:center;justify-content:center">Open Jira</a>`
      : `<button class="task-action primary" disabled>Submitted</button>`)
    : `<button onclick="submitTask('${draft.id}')" class="task-action primary">Create Jira</button>`;
  const editAction = isLocked
    ? ''
    : `<button onclick="confirmTask('${draft.id}')" class="task-action ghost">${status === 'confirmed' ? 'Edit' : 'Edit & Confirm'}</button>`;
  const dismissAction = isLocked
    ? ''
    : `<button onclick="rejectTask('${draft.id}')" class="task-action danger">Dismiss</button>`;

  return `<div id="task-${draft.id}" class="task-card">
    <div class="task-head">
      <div style="flex:1">
        <div class="task-title">${escapeHtml(draft.title || '')}</div>
        <div class="task-desc">${escapeHtml(draft.description || '')}</div>
      </div>
      <span class="priority-pill" style="${priBadge}">${draft.priority}</span>
    </div>
    <div class="task-meta">
      ${selectBox}
      <span class="task-chip">${srcIcon} ${srcLabel}</span>
      ${issueTypeChip}
      ${statusPill}
      ${assignee}
      ${labels}
      ${sourceLink}
      ${jiraLink}
      ${jiraStatusChip}
    </div>
    ${summary}
    ${evidenceMarkup}
    <div class="task-actions">
      ${primaryAction}
      ${editAction}
      ${dismissAction}
    </div>
  </div>`;
}

function loadTasks() {
  const includeSubmitted = !!document.getElementById('tasksIncludeSubmitted')?.checked;
  const url = includeSubmitted ? `${API}/tasks?include_submitted=true` : `${API}/tasks`;
  return authFetch(url)
    .then(async response => {
      if (!response.ok) {
        throw new Error(await readApiError(response));
      }
      return response.json();
    })
    .then(data => {
      const drafts = data.drafts || [];
      const groups = data.groups || [];
      tasksDirectory.drafts = drafts;
      tasksDirectory.groups = groups;
      const list = document.getElementById('tasksList');
      if (!list) return;

      if (!drafts.length) {
        list.innerHTML = `<div class="tasks-empty">No draft tasks yet. Click scan to start.</div>`;
        updateTasksCount(0);
        return;
      }

      if (groups && groups.length) {
        list.innerHTML = renderTaskGroups(groups, drafts);
      } else {
        list.innerHTML = drafts.map(renderTaskCard).join('');
      }
      updateTasksCount(drafts.length);
      updateBulkBar();
    })
    .catch(error => {
      console.error('[Tasks] loadTasks error:', error);
      const list = document.getElementById('tasksList');
      if (list) {
        list.innerHTML = `<div class="tasks-empty" style="color:var(--danger)">Failed to load tasks.</div>`;
      }
    });
}

async function sendMessage() {
  const input = document.getElementById('chatInput');
  const question = input.value.trim();
  if (!question) return;

  const empty = document.getElementById('emptyState');
  if (empty) empty.style.display = 'none';

  const btn = document.getElementById('sendBtn');
  btn.disabled = true;
  input.value = '';
  input.style.height = 'auto';

  appendMessage('user', question);
  const typing = appendTyping();

  try {
    const response = await authFetch(`${API}/ask`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    const data = await response.json();
    typing.remove();
    appendMessage(
      'assistant',
      data.answer || 'Khong co cau tra loi.',
      data.sources || [],
      data.agent_steps || [],
      data.used_tools || [],
      data.agent_plan || [],
      { question }
    );

    chatHistory.unshift({ question, answer: data.answer, time: new Date(), sources: data.sources });
    document.getElementById('historyBadge').textContent = chatHistory.length;
  } catch (error) {
    typing.remove();
    appendMessage('assistant', `Request failed: ${error.message || 'API connection error'}`);
  }

  btn.disabled = false;
  input.focus();
}

async function doSearch() {
  const query = document.getElementById('searchInput').value.trim();
  if (!query) return;

  const container = document.getElementById('searchResults');
  container.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:40px">Searching...</div>';

  try {
    const response = await authFetch(`${API}/search`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query }),
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    const payload = await response.json();
    const results = Array.isArray(payload) ? payload : (payload.results || []);

    if (!results.length) {
      container.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:40px">No matching results.</div>';
      return;
    }

    container.innerHTML = results.map(result => `
      <div class="result-card" onclick="window.open('${result.url}','_blank')">
        <div class="result-header">
          <span class="result-source-badge ${getBadgeClass(result.source)}">${result.source || 'doc'}</span>
          <span class="result-title">${result.title || 'Untitled'}</span>
          <span class="result-score">${formatRelevancePercent(result.score) || ''}</span>
          <button class="pin-mini" onclick="event.stopPropagation(); basketAddDocument('${String(result.document_id || '').trim()}')" title="Ghim ngữ cảnh">📌</button>
        </div>
        <div class="result-content">${result.content || ''}</div>
        <div class="result-url">Link: ${result.url || ''}</div>
      </div>
    `).join('');
  } catch (error) {
    container.innerHTML = `<div style="color:var(--danger);text-align:center;padding:40px">Request failed: ${escapeHtml(error.message || 'API error')}</div>`;
  }
}

async function submitTask(id) {
  const ok = await kpConfirm({
    title: 'Create Jira task',
    message: 'Create Jira task from this draft?',
    okText: 'Create',
    cancelText: 'Cancel',
  });
  if (!ok) return;
  try {
    const response = await authFetch(`${API}/tasks/${id}/submit`, { method: 'POST' });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json();
    const card = document.getElementById(`task-${id}`);
    if (card) {
      const jiraLink = data.jira_url
        ? `<a href="${data.jira_url}" target="_blank" style="color:#166534">${data.jira_key}</a>`
        : escapeHtml(data.jira_key || 'created');
      card.innerHTML = `<div class="task-summary" style="background:#dcfce7;color:#166534;border-left-color:#22c55e;font-weight:700">Created ${jiraLink}</div>`;
    }
    await loadTasks();
    loadTasksCount();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function triggerScan() {
  const btn = document.getElementById('scanBtn');
  const slackDaysEl = document.getElementById('slackDaysInput');
  const confDaysEl = document.getElementById('confluenceDaysInput');
  const slack_days = Math.max(1, Number(slackDaysEl ? slackDaysEl.value : 1) || 1);
  const confluence_days = Math.max(1, Number(confDaysEl ? confDaysEl.value : 1) || 1);
  if (btn) {
    btn.textContent = 'Scanning...';
    btn.disabled = true;
  }

  try {
    const response = await authFetch(`${API}/tasks/scan`, {
      method: 'POST',
      body: JSON.stringify({ slack_days, confluence_days }),
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    showToast('Scanning sources. Results will appear shortly.');
    setTimeout(async () => {
      await loadTasks();
      if (btn) {
        btn.textContent = 'Scan Slack + Confluence';
        btn.disabled = false;
      }
    }, 15000);
  } catch (error) {
    if (btn) {
      btn.textContent = 'Scan Slack + Confluence';
      btn.disabled = false;
    }
    showToast(error.message, 'error');
  }
}

async function rejectTask(id) {
  try {
    const response = await authFetch(`${API}/tasks/${id}/reject`, { method: 'POST' });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const card = document.getElementById(`task-${id}`);
    if (card) card.style.opacity = '0.3';
    setTimeout(() => {
      const current = document.getElementById(`task-${id}`);
      if (current) current.remove();
      loadTasksCount();
    }, 280);
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function confirmTask(id) {
  const current = (tasksDirectory.drafts || []).find(d => String(d.id) === String(id)) || {};
  const body = document.createElement('div');
  body.className = 'kp-modal-form-wrap';

  const form = document.createElement('form');
  form.className = 'kp-modal-form';
  body.appendChild(form);

  const fields = {};
  fields.issue_type = _kpBuildModalField({
    id: `kp_task_issue_type_${id}`,
    label: 'Issue type',
    type: 'select',
    value: String(current.issue_type || 'Task'),
    options: [
      { value: 'Task', label: 'Task' },
      { value: 'Story', label: 'Story' },
      { value: 'Bug', label: 'Bug' },
      { value: 'Epic', label: 'Epic' },
    ],
    required: true,
  });
  form.appendChild(fields.issue_type.wrap);

  fields.epic_key = _kpBuildModalField({
    id: `kp_task_epic_key_${id}`,
    label: 'Epic key (optional)',
    type: 'text',
    value: String(current.epic_key || ''),
    placeholder: 'EPIC-123',
    help: 'Link this draft to an Epic (leave empty to skip).',
  });
  form.appendChild(fields.epic_key.wrap);

  fields.title = _kpBuildModalField({
    id: `kp_task_title_${id}`,
    label: 'Title',
    type: 'text',
    value: String(current.title || ''),
    placeholder: 'Short summary',
    required: true,
  });
  form.appendChild(fields.title.wrap);

  fields.description = _kpBuildModalField({
    id: `kp_task_desc_${id}`,
    label: 'Description',
    type: 'textarea',
    value: String(current.description || ''),
    placeholder: 'Details (optional)',
  });
  form.appendChild(fields.description.wrap);

  fields.assignee = _kpBuildModalField({
    id: `kp_task_assignee_${id}`,
    label: 'Suggested assignee (optional)',
    type: 'text',
    value: String(current.suggested_assignee || ''),
    placeholder: 'email or name',
  });
  form.appendChild(fields.assignee.wrap);

  fields.priority = _kpBuildModalField({
    id: `kp_task_priority_${id}`,
    label: 'Priority',
    type: 'select',
    value: String(current.priority || 'Medium'),
    options: [
      { value: 'High', label: 'High' },
      { value: 'Medium', label: 'Medium' },
      { value: 'Low', label: 'Low' },
    ],
    required: true,
  });
  form.appendChild(fields.priority.wrap);

  fields.labels = _kpBuildModalField({
    id: `kp_task_labels_${id}`,
    label: 'Labels (optional)',
    type: 'text',
    value: (current.labels || []).join(', '),
    placeholder: 'comma-separated',
  });
  form.appendChild(fields.labels.wrap);

  fields.components = _kpBuildModalField({
    id: `kp_task_components_${id}`,
    label: 'Components (optional)',
    type: 'text',
    value: (current.components || []).join(', '),
    placeholder: 'comma-separated',
  });
  form.appendChild(fields.components.wrap);

  fields.due_date = _kpBuildModalField({
    id: `kp_task_due_${id}`,
    label: 'Due date (optional)',
    type: 'date',
    value: String(current.due_date || ''),
    help: 'YYYY-MM-DD',
  });
  form.appendChild(fields.due_date.wrap);

  fields.jira_project = _kpBuildModalField({
    id: `kp_task_project_${id}`,
    label: 'Jira project key (optional)',
    type: 'text',
    value: String(current.jira_project || ''),
    placeholder: 'e.g. TECH',
  });
  form.appendChild(fields.jira_project.wrap);

  const syncEpicVisibility = () => {
    const issueType = String(fields.issue_type.input.value || 'Task').trim();
    const showEpic = issueType !== 'Epic';
    fields.epic_key.wrap.style.display = showEpic ? '' : 'none';
    fields.epic_key.input.disabled = !showEpic;
    if (!showEpic) fields.epic_key.input.value = '';
  };
  fields.issue_type.input.addEventListener('change', syncEpicVisibility);
  syncEpicVisibility();

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const okBtn = document.getElementById('kpModalOkBtn');
    if (okBtn) okBtn.click();
  });

  const result = await kpOpenModal({
    title: 'Confirm task draft',
    subtitle: 'Jira fields',
    content: body,
    okText: 'Confirm',
    cancelText: 'Cancel',
    okClass: 'primary-btn',
    onOk: () => {
      const issue_type = String(fields.issue_type.input.value || '').trim();
      const title = String(fields.title.input.value || '').trim();
      const description = String(fields.description.input.value || '').trim();
      const suggested_assignee = String(fields.assignee.input.value || '').trim();
      const priority = String(fields.priority.input.value || '').trim();
      const labelsRaw = String(fields.labels.input.value || '');
      const componentsRaw = String(fields.components.input.value || '');
      const due_date = String(fields.due_date.input.value || '').trim();
      const jira_project = String(fields.jira_project.input.value || '').trim();
      const epic_key = fields.epic_key.input.disabled ? '' : String(fields.epic_key.input.value || '').trim();

      if (!issue_type || !['Task', 'Story', 'Bug', 'Epic'].includes(issue_type)) return { error: 'Issue type must be Task/Story/Bug/Epic.' };
      if (!priority || !['High', 'Medium', 'Low'].includes(priority)) return { error: 'Priority must be High/Medium/Low.' };
      if (!title) return { error: 'Title is required.' };
      if (due_date && !/^\d{4}-\d{2}-\d{2}$/.test(due_date)) return { error: 'Due date must be YYYY-MM-DD.' };

      const labels = labelsRaw.split(',').map(s => s.trim()).filter(Boolean);
      const components = componentsRaw.split(',').map(s => s.trim()).filter(Boolean);

      return {
        issue_type,
        epic_key: epic_key || null,
        title,
        description: description || null,
        suggested_assignee: suggested_assignee || null,
        priority: priority || null,
        jira_project: jira_project || null,
        labels: labels.length ? labels : null,
        components: components.length ? components : null,
        due_date: due_date || null,
      };
    },
  });
  if (!result) return;
  try {
    const response = await authFetch(`${API}/tasks/${id}/confirm`, {
      method: 'POST',
      body: JSON.stringify(result),
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    showToast('Draft confirmed. You can submit it to Jira now.');
    await loadTasks();
  } catch (error) {
    showToast(error.message, 'error');
  }
}

async function syncJiraStatuses() {
  if (!AUTH.user.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  try {
    const response = await authFetch(`${API}/tasks/sync-jira-status?limit=80`, { method: 'POST' });
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const stats = data.stats || {};
    showToast(`Jira sync: checked ${stats.checked || 0}, updated ${stats.updated || 0}.`, 'success');
    await loadTasks();
  } catch (error) {
    showToast(error.message || 'Jira sync failed.', 'error');
  }
}

setInterval(loadTasksCount, 30000);

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
  // Override import to inject app specific functionality preventing cyclic dependency
  basketRunSkill: () => Basket.basketRunSkill(generateDocFromDocuments),
  deleteDocDraft,
  doLogin,
  doLogout,
  loadDraftsPage,
  navigate,
  toggleTheme,
});
