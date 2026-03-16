// ═══════════════════════════════════════════════════════
// AUTH MODULE — JWT + auto-refresh
// ═══════════════════════════════════════════════════════
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
      role: data.role || currentUser.role || 'member'
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
  checkHealth();
  loadConnectorStats();
  if (document.getElementById('page-users')?.classList.contains('active') && AUTH.user.is_admin) {
    loadUsersAdmin();
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
    const r = String(u.role || '').toLowerCase();
    const label = u.is_admin ? 'Admin' : (r === 'pm' ? 'PM' : (r === 'team_lead' || r === 'lead' ? 'Team Lead' : 'Member'));
    rl.textContent = label;
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


const API = window.__KP_API_BASE__
  || localStorage.getItem('kp_api_base')
  || ((window.location.origin && window.location.origin !== 'null')
    ? window.location.origin
    : 'http://localhost:8000');
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
  if (targetPage === 'tasks') loadTasks();
  if (targetPage === 'connectors') loadConnectorStats(true);
  if (targetPage === 'users') loadUsersAdmin();
  if (targetPage === 'graph') loadGraphDashboard(true);
  const titles = { chat: 'Chat AI', search: 'Search', tasks: '🤖 AI Tasks', connectors: 'Connectors', history: 'Lịch sử Chat', users: 'Users & Permissions' };
  if (targetPage === 'graph') {
    document.getElementById('pageTitle').textContent = 'Knowledge Graph';
  } else {
    document.getElementById('pageTitle').textContent = titles[targetPage] || targetPage;
  }
  if (targetPage === 'history') renderHistory();
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
          <span class="source-score">${((s.score || 0) * 100).toFixed(0)}%</span>
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
      const score = s.score ? ((s.score || 0) * 100).toFixed(0) + '%' : '';
      const snippet = escapeHtml(String(s.snippet || s.quote || s.content || '').trim()).substring(0, 420);
      return `<a class="source-item" ${href} data-snippet="${snippet}" onmouseenter="showCitationPeek(event)" onmouseleave="hideCitationPeek()">
        <span class="source-icon">${getSourceIcon(s.source)}</span>
        <div class="source-info">
          <div class="source-title">${title}</div>
          <div class="source-meta">${s.source || ''}</div>
        </div>
        ${score ? `<span class="source-score">${score}</span>` : ''}
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

  const srsBtn = (role === 'assistant' && assistantMessageStore[msgId] && (assistantMessageStore[msgId].sources || []).some(s => s && s.document_id))
    ? `<button class="sources-toggle-btn" onclick="generateSrsFromAnswer('${msgId}')">✨ Generate SRS</button>`
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
        ${srsBtn}
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

    showToast(`${name} sync started.`);
    await loadConnectorStats(true);
    [5000, 15000, 30000, 60000].forEach(delay => {
      setTimeout(() => loadConnectorStats(), delay);
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
    await loadTasksCount();
    navigate('tasks', document.getElementById('nav-tasks'));
    await loadTasks();
  } catch (error) {
    showToast(error.message || 'Cannot create task draft.', 'error');
  }
}

async function generateSrsFromAnswer(msgId) {
  const payload = assistantMessageStore[msgId];
  if (!payload) {
    showToast('No message context found.', 'error');
    return;
  }

  try {
    const response = await authFetch(`${API}/srs/drafts/from-answer`, {
      method: 'POST',
      body: JSON.stringify({
        title: '',
        question: payload.question,
        answer: payload.answer,
        sources: payload.sources || [],
      }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const draft = data && data.draft ? data.draft : null;
    if (!draft || !draft.id) throw new Error('Invalid draft response.');
    showToast('SRS draft generated.', 'success');
    await openSrsDraftEditor(draft.id);
  } catch (error) {
    showToast(error.message || 'Cannot generate SRS draft.', 'error');
  }
}

async function openSrsDraftEditor(draftId) {
  const id = String(draftId || '').trim();
  if (!id) return;

  let draft = null;
  try {
    const r = await authFetch(`${API}/srs/drafts/${encodeURIComponent(id)}`);
    if (!r.ok) throw new Error(await readApiError(r));
    const data = await r.json();
    draft = data && data.draft ? data.draft : null;
  } catch (e) {
    showToast(e.message || 'Cannot load SRS draft.', 'error');
    return;
  }

  const body = document.createElement('div');
  body.className = 'kp-modal-form-wrap';
  const form = document.createElement('div');
  form.className = 'kp-modal-form';

  const titleWrap = document.createElement('div');
  titleWrap.className = 'kp-modal-field';
  const titleLab = document.createElement('div');
  titleLab.className = 'kp-modal-label';
  titleLab.textContent = 'Title';
  const titleInput = document.createElement('input');
  titleInput.className = 'time-input kp-modal-input';
  titleInput.type = 'text';
  titleInput.value = String(draft.title || 'SRS Draft');
  titleWrap.appendChild(titleLab);
  titleWrap.appendChild(titleInput);

  const contentWrap = document.createElement('div');
  contentWrap.className = 'kp-modal-field';
  const contentLab = document.createElement('div');
  contentLab.className = 'kp-modal-label';
  contentLab.textContent = 'Content (Markdown)';
  const contentInput = document.createElement('textarea');
  contentInput.className = 'time-input kp-modal-input';
  contentInput.value = String(draft.content || '');
  contentInput.style.minHeight = '360px';
  contentWrap.appendChild(contentLab);
  contentWrap.appendChild(contentInput);

  const help = document.createElement('div');
  help.className = 'kp-modal-help';
  help.textContent = 'MVP: chỉnh sửa bản nháp SRS dạng Markdown. (Push to Confluence sẽ làm ở bước sau.)';

  form.appendChild(titleWrap);
  form.appendChild(contentWrap);
  form.appendChild(help);
  body.appendChild(form);

  await kpOpenModal({
    title: 'SRS Draft',
    subtitle: `Draft ID: ${id}`,
    content: body,
    okText: 'Save',
    cancelText: 'Close',
    onOk: async () => {
      const response = await authFetch(`${API}/srs/drafts/${encodeURIComponent(id)}`, {
        method: 'PUT',
        body: JSON.stringify({
          title: titleInput.value,
          content: contentInput.value,
        }),
      });
      if (!response.ok) return { error: await readApiError(response) };
      showToast('Draft saved.', 'success');
      return true;
    }
  });
}

// ── History ──
function renderHistory() {
  const container = document.getElementById('historyList');
  if (chatHistory.length === 0) {
    container.innerHTML = `<div style="text-align:center;padding:60px;color:var(--text-muted)">
      <div style="font-size:40px;opacity:0.3;margin-bottom:12px">🕘</div>
      <div>Chưa có lịch sử chat</div></div>`;
    return;
  }

  container.innerHTML = chatHistory.map((h, i) => `
    <div class="history-item" onclick="loadHistory(${i})">
      <span class="history-icon">💬</span>
      <div class="history-body">
        <div class="history-question">${h.question}</div>
        <div class="history-meta">${h.time.toLocaleString('vi-VN')} · ${h.sources?.length || 0} nguồn</div>
      </div>
      <span class="history-arrow">›</span>
    </div>`).join('');
}

function loadHistory(i) {
  const h = chatHistory[i];
  navigate('chat', document.querySelectorAll('.nav-item')[0]);
  setTimeout(() => {
    appendMessage('user', h.question);
    appendMessage('assistant', h.answer, h.sources);
  }, 100);
}

// ── Toast ──
function showToast(msg, type = 'success') {
  let container = document.getElementById('toastContainer');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toastContainer';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = msg;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}

// ── Modal (custom popup; avoid browser prompt/confirm) ──
let KP_MODAL_STATE = null;

function _kpEnsureModalElements() {
  let overlay = document.getElementById('kpModalOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'kpModalOverlay';
    overlay.className = 'kp-modal-overlay';
    overlay.style.display = 'none';
    overlay.innerHTML = `
      <div class="kp-modal" role="dialog" aria-modal="true" aria-labelledby="kpModalTitle">
        <div class="kp-modal-header">
          <div class="kp-modal-header-copy">
            <div id="kpModalTitle" class="kp-modal-title"></div>
            <div id="kpModalSubtitle" class="kp-modal-sub"></div>
          </div>
          <button id="kpModalCloseBtn" class="kp-modal-close" type="button" aria-label="Close">&times;</button>
        </div>
        <div id="kpModalBody" class="kp-modal-body"></div>
        <div id="kpModalError" class="kp-modal-error" style="display:none"></div>
        <div class="kp-modal-actions">
          <button id="kpModalCancelBtn" class="secondary-btn" type="button">Cancel</button>
          <button id="kpModalOkBtn" class="primary-btn" type="button">OK</button>
        </div>
      </div>
    `;
    document.body.appendChild(overlay);
  }

  const titleEl = document.getElementById('kpModalTitle');
  const subtitleEl = document.getElementById('kpModalSubtitle');
  const bodyEl = document.getElementById('kpModalBody');
  const errorEl = document.getElementById('kpModalError');
  const okBtn = document.getElementById('kpModalOkBtn');
  const cancelBtn = document.getElementById('kpModalCancelBtn');
  const closeBtn = document.getElementById('kpModalCloseBtn');

  return { overlay, titleEl, subtitleEl, bodyEl, errorEl, okBtn, cancelBtn, closeBtn };
}

function _kpCloseModal(result) {
  const els = _kpEnsureModalElements();
  els.overlay.style.display = 'none';
  els.bodyEl.innerHTML = '';
  els.errorEl.style.display = 'none';
  els.errorEl.textContent = '';
  document.body.classList.remove('kp-modal-open');

  const state = KP_MODAL_STATE;
  KP_MODAL_STATE = null;
  if (state && typeof state.cleanup === 'function') state.cleanup();
  if (state && state.previouslyFocused && typeof state.previouslyFocused.focus === 'function') {
    try { state.previouslyFocused.focus(); } catch (_) {}
  }
  if (state && typeof state.resolve === 'function') state.resolve(result);
}

function _kpSetModalError(message) {
  const els = _kpEnsureModalElements();
  els.errorEl.textContent = String(message || 'Invalid input.');
  els.errorEl.style.display = '';
}

function kpOpenModal({ title, subtitle, content, okText = 'OK', cancelText = 'Cancel', okClass = 'primary-btn', onOk } = {}) {
  const els = _kpEnsureModalElements();
  if (KP_MODAL_STATE) _kpCloseModal(null);

  els.titleEl.textContent = String(title || '');
  els.subtitleEl.textContent = String(subtitle || '');
  els.subtitleEl.style.display = subtitle ? '' : 'none';
  els.bodyEl.innerHTML = '';
  els.errorEl.style.display = 'none';
  els.errorEl.textContent = '';
  els.okBtn.textContent = okText;
  els.cancelBtn.textContent = cancelText;
  els.cancelBtn.style.display = cancelText ? '' : 'none';
  els.okBtn.className = okClass;

  const previouslyFocused = document.activeElement;

  if (content) {
    if (typeof content === 'string') {
      els.bodyEl.innerHTML = content;
    } else {
      els.bodyEl.appendChild(content);
    }
  }

  const handleCancel = () => _kpCloseModal(null);
  const handleOk = async () => {
    if (!KP_MODAL_STATE) return;
    try {
      const out = onOk ? await onOk() : true;
      if (out && typeof out === 'object' && out.error) {
        _kpSetModalError(out.error);
        return;
      }
      if (out === false) return;
      _kpCloseModal(out);
    } catch (e) {
      _kpSetModalError(e && e.message ? e.message : 'Action failed.');
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      e.preventDefault();
      handleCancel();
    }
  };

  const onOverlayClick = (e) => {
    if (e.target === els.overlay) handleCancel();
  };

  els.cancelBtn.addEventListener('click', handleCancel);
  els.closeBtn.addEventListener('click', handleCancel);
  els.okBtn.addEventListener('click', handleOk);
  els.overlay.addEventListener('click', onOverlayClick);
  document.addEventListener('keydown', onKeyDown);

  KP_MODAL_STATE = {
    resolve: null,
    previouslyFocused,
    cleanup: () => {
      els.cancelBtn.removeEventListener('click', handleCancel);
      els.closeBtn.removeEventListener('click', handleCancel);
      els.okBtn.removeEventListener('click', handleOk);
      els.overlay.removeEventListener('click', onOverlayClick);
      document.removeEventListener('keydown', onKeyDown);
    },
  };

  els.overlay.style.display = 'flex';
  document.body.classList.add('kp-modal-open');

  // Focus first focusable control inside modal.
  setTimeout(() => {
    const first = els.bodyEl.querySelector('input, select, textarea, button');
    if (first && typeof first.focus === 'function') first.focus();
  }, 0);

  return new Promise(resolve => {
    if (!KP_MODAL_STATE) return resolve(null);
    KP_MODAL_STATE.resolve = resolve;
  });
}

function kpConfirm({ title, message, okText = 'OK', cancelText = 'Cancel', danger = false } = {}) {
  const body = document.createElement('div');
  body.className = 'kp-modal-confirm';
  const p = document.createElement('div');
  p.className = 'kp-modal-confirm-text';
  p.textContent = String(message || '');
  body.appendChild(p);
  return kpOpenModal({
    title,
    subtitle: '',
    content: body,
    okText,
    cancelText,
    okClass: danger ? 'danger-btn' : 'primary-btn',
    onOk: () => true,
  }).then(res => !!res);
}

// ── Theme Toggle ──
function toggleTheme() {
  const html = document.documentElement;
  const isDark = html.getAttribute('data-theme') === 'dark';
  if (isDark) {
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
loadConnectorStats();
setInterval(loadConnectorStats, 450000);
document.getElementById('searchInput').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

// ─── Tasks (Phase 3) ────────────────────────────────────────────────────────

async function readApiError(response) {
  const payload = await response.json().catch(() => ({}));
  return payload.detail || payload.message || `Request failed (${response.status})`;
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function getUserDisplayName(user) {
  return user.display_name || user.email || user.id;
}

function renderUsersAccessDenied() {
  const usersBody = document.getElementById('usersTableBody');
  const groupsBody = document.getElementById('groupsTableBody');
  if (usersBody) {
    usersBody.innerHTML = `<tr><td colspan="6" class="muted-cell">Admin access required.</td></tr>`;
  }
  if (groupsBody) {
    groupsBody.innerHTML = `<tr><td colspan="4" class="muted-cell">Admin access required.</td></tr>`;
  }
  closeUserEditor();
  closeGroupEditor();
}

async function loadUsersAdmin() {
  if (!AUTH.user.is_admin) {
    renderUsersAccessDenied();
    return;
  }

  const usersBody = document.getElementById('usersTableBody');
  const groupsBody = document.getElementById('groupsTableBody');
  if (usersBody) {
    usersBody.innerHTML = `<tr><td colspan="6" class="muted-cell">Loading users...</td></tr>`;
  }
  if (groupsBody) {
    groupsBody.innerHTML = `<tr><td colspan="4" class="muted-cell">Loading groups...</td></tr>`;
  }

  try {
    const response = await authFetch(`${API}/users`);
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    const data = await response.json();
    adminDirectory = {
      users: data.users || [],
      groups: data.groups || [],
    };

    renderUsersTable(adminDirectory.users);
    renderGroupsTable(adminDirectory.groups);

    if (userEditorState) renderUserEditor();
    if (groupEditorState) renderGroupEditor();
  } catch (error) {
    if (usersBody) {
      usersBody.innerHTML = `<tr><td colspan="6" class="muted-cell" style="color:var(--danger)">Failed to load users: ${escapeHtml(error.message)}</td></tr>`;
    }
    if (groupsBody) {
      groupsBody.innerHTML = `<tr><td colspan="4" class="muted-cell" style="color:var(--danger)">Failed to load groups: ${escapeHtml(error.message)}</td></tr>`;
    }
    showToast(error.message, 'error');
  }
}

function renderUsersTable(users) {
  const body = document.getElementById('usersTableBody');
  if (!body) return;

  if (!users.length) {
    body.innerHTML = `<tr><td colspan="6" class="muted-cell">No users yet.</td></tr>`;
    return;
  }

  body.innerHTML = users.map(user => {
    const displayName = escapeHtml(getUserDisplayName(user));
    const email = escapeHtml(user.email);
    const initials = escapeHtml((displayName[0] || 'U').toUpperCase());
    const groups = (user.groups || []).map(group => (
      `<span class="tag ${group.id === 'group_admin' ? 'tag-blue' : 'tag-purple'}">${escapeHtml(group.name || group.id)}</span>`
    )).join(' ');
    const roleClass = user.is_admin ? 'tag-blue' : 'tag-green';
    const statusClass = user.is_active ? 'tag-green' : 'tag-purple';
    const toggleLabel = user.is_active ? 'Disable' : 'Enable';

    return `<tr>
      <td>
        <div class="user-td">
          <div class="avatar-sm">${initials}</div>
          <div>
            <div style="font-weight:600">${displayName}</div>
            <div class="muted-cell">${escapeHtml(user.id)}</div>
          </div>
        </div>
      </td>
      <td>${email}</td>
      <td>${groups || '<span class="muted-cell">No groups</span>'}</td>
      <td><span class="tag ${roleClass}">${user.is_admin ? 'Admin' : 'Member'}</span></td>
      <td><span class="tag ${statusClass}">${user.is_active ? 'Active' : 'Inactive'}</span></td>
      <td>
        <button class="action-btn" onclick="editUser('${escapeHtml(user.id)}')">Edit</button>
        <button class="action-btn" onclick="toggleUserActive('${escapeHtml(user.id)}')">${toggleLabel}</button>
      </td>
    </tr>`;
  }).join('');
}

function renderGroupsTable(groups) {
  const body = document.getElementById('groupsTableBody');
  if (!body) return;

  if (!groups.length) {
    body.innerHTML = `<tr><td colspan="4" class="muted-cell">No groups yet.</td></tr>`;
    return;
  }

  body.innerHTML = groups.map(group => {
    const members = (group.members || [])
      .map(member => escapeHtml(member.display_name || member.email || member.id))
      .slice(0, 4);
    const extraCount = Math.max((group.member_count || 0) - members.length, 0);
    const membersLabel = members.length ? members.join(', ') : 'No members';
    const suffix = extraCount ? ` +${extraCount}` : '';

    return `<tr>
      <td>
        <div style="font-weight:600">${escapeHtml(group.name)}</div>
        <div class="muted-cell">${escapeHtml(group.id)}</div>
      </td>
      <td class="muted-cell">${membersLabel}${suffix}</td>
      <td><span class="tag tag-blue">${group.member_count || 0} users</span></td>
      <td><button class="action-btn" onclick="editGroup('${escapeHtml(group.id)}')">Edit</button></td>
    </tr>`;
  }).join('');
}

function openCreateUser() {
  userEditorState = { mode: 'create', userId: null };
  renderUserEditor();
}

function editUser(userId) {
  userEditorState = { mode: 'edit', userId };
  renderUserEditor();
}

function closeUserEditor() {
  userEditorState = null;
  const panel = document.getElementById('userEditorPanel');
  if (!panel) return;
  panel.classList.remove('active');
  panel.innerHTML = '';
}

function renderUserEditor() {
  const panel = document.getElementById('userEditorPanel');
  if (!panel) return;
  if (!userEditorState) {
    closeUserEditor();
    return;
  }

  const isEdit = userEditorState.mode === 'edit';
  const user = isEdit
    ? adminDirectory.users.find(item => item.id === userEditorState.userId)
    : null;

  if (isEdit && !user) {
    closeUserEditor();
    showToast('User no longer exists.', 'error');
    return;
  }

  const selectedGroupIds = new Set(user?.group_ids || []);
  const groupOptions = adminDirectory.groups.length
    ? adminDirectory.groups.map(group => `
        <label class="admin-group-option">
          <input
            type="checkbox"
            name="group_ids"
            value="${escapeHtml(group.id)}"
            ${selectedGroupIds.has(group.id) ? 'checked' : ''}
          />
          <span>${escapeHtml(group.name)}</span>
        </label>
      `).join('')
    : `<div class="admin-editor-note">No groups yet. Create groups first or save without groups.</div>`;

  panel.classList.add('active');
  panel.innerHTML = `
    <form onsubmit="submitUserEditor(event)">
      <div class="admin-editor-head">
        <div>
          <div class="admin-editor-title">${isEdit ? 'Edit user' : 'Create user'}</div>
          <div class="admin-editor-note">${isEdit ? escapeHtml(user.id) : 'New user account and access settings'}</div>
        </div>
        <button type="button" class="admin-secondary" onclick="closeUserEditor()">Close</button>
      </div>

      <div class="admin-form-grid">
        <div class="admin-field">
          <label for="user-display-name">Display name</label>
          <input id="user-display-name" name="display_name" value="${escapeHtml(user?.display_name || '')}" required />
        </div>
        <div class="admin-field">
          <label for="user-email">Email</label>
          <input id="user-email" name="email" type="email" value="${escapeHtml(user?.email || '')}" required />
        </div>
        <div class="admin-field">
          <label for="user-password">${isEdit ? 'New password (optional)' : 'Password'}</label>
          <input id="user-password" name="password" type="password" ${isEdit ? '' : 'required'} minlength="8" />
        </div>
      </div>

      <div class="admin-inline-checks">
        <label class="admin-check">
          <input type="checkbox" name="is_active" ${user?.is_active === false ? '' : 'checked'} />
          <span>Active</span>
        </label>
        <label class="admin-check">
          <input type="checkbox" name="is_admin" ${user?.is_admin ? 'checked' : ''} />
          <span>Admin</span>
        </label>
      </div>

      <div class="admin-editor-note" style="margin-top:14px">Group membership</div>
      <div class="admin-group-picker">${groupOptions}</div>

      <div class="admin-editor-actions">
        <button type="submit" class="add-btn" data-submit-label>${isEdit ? 'Save changes' : 'Create user'}</button>
        <button type="button" class="admin-secondary" onclick="closeUserEditor()">Cancel</button>
      </div>
    </form>
  `;
}

async function submitUserEditor(event) {
  event.preventDefault();
  if (!userEditorState) return;

  const form = event.target;
  const button = form.querySelector('[data-submit-label]');
  const actionMode = userEditorState.mode;
  const targetUserId = userEditorState.userId;
  const payload = {
    display_name: form.display_name.value.trim(),
    email: form.email.value.trim(),
    is_active: form.is_active.checked,
    is_admin: form.is_admin.checked,
    group_ids: [...form.querySelectorAll('input[name="group_ids"]:checked')].map(input => input.value),
  };
  const password = form.password.value.trim();

  if (!payload.display_name || !payload.email) {
    showToast('Display name and email are required.', 'error');
    return;
  }

  if (button) {
    button.disabled = true;
    button.textContent = actionMode === 'edit' ? 'Saving...' : 'Creating...';
  }

  try {
    let response;
    if (actionMode === 'create') {
      if (!password) {
        throw new Error('Password is required for new users.');
      }
      payload.password = password;
      response = await authFetch(`${API}/users`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
    } else {
      if (password) payload.password = password;
      response = await authFetch(`${API}/users/${encodeURIComponent(targetUserId)}`, {
        method: 'PATCH',
        body: JSON.stringify(payload),
      });
    }

    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    closeUserEditor();
    await loadUsersAdmin();
    showToast(actionMode === 'edit' ? 'User updated.' : 'User created.');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = actionMode === 'edit' ? 'Save changes' : 'Create user';
    }
  }
}

async function toggleUserActive(userId) {
  const user = adminDirectory.users.find(item => item.id === userId);
  if (!user) return;

  const nextStatus = !user.is_active;
  const confirmText = nextStatus
    ? `Enable ${getUserDisplayName(user)}?`
    : `Disable ${getUserDisplayName(user)}?`;

  const ok = await kpConfirm({
    title: nextStatus ? 'Enable user' : 'Disable user',
    message: confirmText,
    okText: nextStatus ? 'Enable' : 'Disable',
    cancelText: 'Cancel',
    danger: !nextStatus,
  });
  if (!ok) return;

  try {
    const response = await authFetch(`${API}/users/${encodeURIComponent(userId)}`, {
      method: 'PATCH',
      body: JSON.stringify({ is_active: nextStatus }),
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    await loadUsersAdmin();
    showToast(nextStatus ? 'User enabled.' : 'User disabled.');
  } catch (error) {
    showToast(error.message, 'error');
  }
}

function openCreateGroup() {
  groupEditorState = { mode: 'create', groupId: null };
  renderGroupEditor();
}

function editGroup(groupId) {
  groupEditorState = { mode: 'edit', groupId };
  renderGroupEditor();
}

function closeGroupEditor() {
  groupEditorState = null;
  const panel = document.getElementById('groupEditorPanel');
  if (!panel) return;
  panel.classList.remove('active');
  panel.innerHTML = '';
}

function renderGroupEditor() {
  const panel = document.getElementById('groupEditorPanel');
  if (!panel) return;
  if (!groupEditorState) {
    closeGroupEditor();
    return;
  }

  const isEdit = groupEditorState.mode === 'edit';
  const group = isEdit
    ? adminDirectory.groups.find(item => item.id === groupEditorState.groupId)
    : null;

  if (isEdit && !group) {
    closeGroupEditor();
    showToast('Group no longer exists.', 'error');
    return;
  }

  const members = (group?.members || [])
    .map(member => escapeHtml(member.display_name || member.email || member.id))
    .join(', ');

  panel.classList.add('active');
  panel.innerHTML = `
    <form onsubmit="submitGroupEditor(event)">
      <div class="admin-editor-head">
        <div>
          <div class="admin-editor-title">${isEdit ? 'Edit group' : 'Create group'}</div>
          <div class="admin-editor-note">${isEdit ? escapeHtml(group.id) : 'Create a reusable access group'}</div>
        </div>
        <button type="button" class="admin-secondary" onclick="closeGroupEditor()">Close</button>
      </div>

      <div class="admin-form-grid">
        <div class="admin-field">
          <label for="group-name">Group name</label>
          <input id="group-name" name="name" value="${escapeHtml(group?.name || '')}" required />
        </div>
        ${isEdit ? '' : `
        <div class="admin-field">
          <label for="group-id">Custom group id (optional)</label>
          <input id="group-id" name="id" placeholder="group_engineering" />
        </div>`}
      </div>

      ${isEdit ? `<div class="admin-editor-note" style="margin-top:14px">Members: ${members || 'No members yet.'}</div>` : ''}

      <div class="admin-editor-actions">
        <button type="submit" class="add-btn" data-group-submit>${isEdit ? 'Save group' : 'Create group'}</button>
        <button type="button" class="admin-secondary" onclick="closeGroupEditor()">Cancel</button>
      </div>
    </form>
  `;
}

async function submitGroupEditor(event) {
  event.preventDefault();
  if (!groupEditorState) return;

  const form = event.target;
  const button = form.querySelector('[data-group-submit]');
  const actionMode = groupEditorState.mode;
  const targetGroupId = groupEditorState.groupId;
  const payload = {
    name: form.name.value.trim(),
  };
  const customIdField = form.querySelector('[name="id"]');

  if (customIdField && customIdField.value.trim()) {
    payload.id = customIdField.value.trim();
  }

  if (!payload.name) {
    showToast('Group name is required.', 'error');
    return;
  }

  if (button) {
    button.disabled = true;
    button.textContent = actionMode === 'edit' ? 'Saving...' : 'Creating...';
  }

  try {
    const response = await authFetch(
      actionMode === 'edit'
        ? `${API}/users/groups/${encodeURIComponent(targetGroupId)}`
        : `${API}/users/groups`,
      {
        method: actionMode === 'edit' ? 'PATCH' : 'POST',
        body: JSON.stringify(payload),
      }
    );

    if (!response.ok) {
      throw new Error(await readApiError(response));
    }

    closeGroupEditor();
    await loadUsersAdmin();
    showToast(actionMode === 'edit' ? 'Group updated.' : 'Group created.');
  } catch (error) {
    showToast(error.message, 'error');
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = actionMode === 'edit' ? 'Save group' : 'Create group';
    }
  }
}

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
  const ids = selectedTaskIds();
  if (!ids.length) return;
  try {
    const response = await authFetch(`${API}/tasks/batch/confirm`, {
      method: 'POST',
      body: JSON.stringify({ ids }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Confirmed ${ids.length} tasks.`, 'success');
    clearTaskSelection();
    await loadTasks();
    await loadTasksCount();
  } catch (error) {
    showToast(error.message || 'Bulk confirm failed.', 'error');
  }
}

async function bulkRejectTasks() {
  const ids = selectedTaskIds();
  if (!ids.length) return;
  const ok = await kpConfirm({
    title: 'Dismiss tasks',
    message: `Dismiss ${ids.length} selected tasks?`,
    okText: 'Dismiss',
    cancelText: 'Cancel',
    danger: true,
  });
  if (!ok) return;
  try {
    const response = await authFetch(`${API}/tasks/batch/reject`, {
      method: 'POST',
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
  } catch (error) {
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
          <span class="result-score">${((result.score || 0) * 100).toFixed(0)}%</span>
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

function formatDateTime(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('vi-VN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
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

function formatNumber(value) {
  return Number(value || 0).toLocaleString('vi-VN');
}

function getConnectorBadgeClass(code) {
  const classes = {
    healthy: 'connected',
    syncing: 'syncing',
    attention: 'error',
    ready: 'empty',
    not_configured: 'warning',
  };
  return classes[code] || 'empty';
}

function getConnectorTestClass(status) {
  if (status === 'ok') return 'success';
  if (status === 'error') return 'error';
  if (status === 'running') return 'running';
  return 'neutral';
}

function getConnectorIcon(name) {
  const icons = {
    confluence: '📘',
    jira: '🟣',
    slack: '💬',
    files: '🗂️',
    file_server: '🗂️',
  };
  return icons[name] || '🔗';
}

function renderConnectorSummary(summary) {
  const grid = document.getElementById('connectorsSummaryGrid');
  const pill = document.getElementById('connectorsSummaryPill');
  if (!grid || !summary) return;

  if (pill) {
    pill.textContent = `${summary.configured}/${summary.total} configured · ${summary.syncing} syncing`;
  }

  grid.innerHTML = [
    { label: 'Total connectors', value: summary.total, note: 'Registered data sources' },
    { label: 'Configured', value: summary.configured, note: 'Ready for manual or scheduled sync' },
    { label: 'Healthy', value: summary.healthy, note: 'Configured and already indexed' },
    { label: 'Attention', value: summary.attention, note: 'Need config or investigation' },
    { label: 'Documents', value: formatNumber(summary.documents), note: 'Indexed source documents' },
    { label: 'Chunks', value: formatNumber(summary.chunks), note: 'Retrieval units in storage' },
  ].map(item => `
    <div class="connector-summary-card">
      <span>${item.label}</span>
      <strong>${item.value}</strong>
      <small>${item.note}</small>
    </div>
  `).join('');
}

function renderConnectorHistory(history) {
  if (!history || !history.length) {
    return `<div class="connector-history-empty">No sync history yet.</div>`;
  }

  return history.map(run => `
    <div class="connector-history-item">
      <div class="connector-history-head">
        <span class="connector-history-status status-${escapeHtml(run.status || 'unknown')}">${escapeHtml(run.status || 'unknown')}</span>
        <span>${formatDateTime(run.finished_at || run.started_at || run.last_sync_at)}</span>
      </div>
      <div class="connector-history-metrics">
        <span>Fetched ${formatNumber(run.fetched)}</span>
        <span>Indexed ${formatNumber(run.indexed)}</span>
        <span>Errors ${formatNumber(run.errors)}</span>
      </div>
    </div>
  `).join('');
}

function pad2(n) {
  const v = Number(n);
  if (!Number.isFinite(v)) return '';
  return String(v).padStart(2, '0');
}

function getConnectorSelectionList(connector) {
  const state = connector.state || {};
  const sel = state.selection || {};
  const t = connector.connector_type || String(connector.id || '').split(':')[0];
  if (t === 'confluence') return sel.spaces || [];
  if (t === 'jira') return sel.projects || [];
  if (t === 'slack') return sel.channels || [];
  if (t === 'file_server') return sel.folders || [];
  return [];
}

function buildConnectorSelectionPayload(connectorId, values) {
  const unique = Array.from(new Set(values.map(v => String(v || '').trim()).filter(Boolean)));
  const t = String(connectorId || '').split(':')[0];
  if (t === 'confluence') return { spaces: unique };
  if (t === 'jira') return { projects: unique };
  if (t === 'slack') return { channels: unique };
  if (t === 'file_server') return { folders: unique };
  return {};
}

function renderConnectorManage(connector) {
  if (!AUTH.user?.is_admin) return '';

  const state = connector.state || {};
  const enabled = !!state.enabled;
  const autoSync = !!state.auto_sync;
  const timeVal = (state.schedule_hour === null || state.schedule_hour === undefined || state.schedule_minute === null || state.schedule_minute === undefined)
    ? ''
    : `${pad2(state.schedule_hour)}:${pad2(state.schedule_minute)}`;

  const cached = connectorScopeCache[connector.id] || null;
  const selected = new Set(getConnectorSelectionList(connector).map(String));

  let scopeMarkup = `<div class="connector-scope-empty">Discover available ${escapeHtml((connector.config || {}).scope_label || 'scope')} to select.</div>`;
  if (cached && Array.isArray(cached.items)) {
    const items = cached.items.slice(0, 60);
    const allNote = selected.size === 0
      ? `<div class="connector-scope-empty">No items selected = sync ALL.</div>`
      : '';
    scopeMarkup = allNote + items.map(item => {
      const value = String(item.id || item.key || item.name || '').trim();
      const label = item.key
        ? `[${item.key}] ${item.name || item.key}`
        : item.id
          ? `${item.name || item.id}${item.is_private ? ' (private)' : ''}`
          : (item.name || value);
      const checked = selected.has(value) ? 'checked' : '';
      return `
        <label class="scope-item">
          <input type="checkbox" data-scope-checkbox="${escapeHtml(connector.id)}" data-scope-value="${escapeHtml(value)}" ${checked}>
          <span>${escapeHtml(label)}</span>
        </label>
      `;
    }).join('') + (cached.items.length > 60 ? `<div class="connector-scope-empty">Showing first 60 of ${formatNumber(cached.items.length)}.</div>` : '');
  }

  return `
    <div class="connector-manage">
      <div class="connector-section-title">Manage (Demo)</div>
      <div class="connector-manage-row">
        <label class="scope-toggle">
          <input type="checkbox" id="cfg_enabled_${escapeHtml(connector.id)}" ${enabled ? 'checked' : ''}>
          <span>Enabled</span>
        </label>
        <label class="scope-toggle">
          <input type="checkbox" id="cfg_auto_${escapeHtml(connector.id)}" ${autoSync ? 'checked' : ''}>
          <span>Auto sync</span>
        </label>
        <input class="time-input" type="time" id="cfg_time_${escapeHtml(connector.id)}" value="${escapeHtml(timeVal)}">
        <button class="secondary-btn" onclick="discoverConnectorScopes('${escapeHtml(connector.id)}')">Discover</button>
        <button class="primary-btn" onclick="saveConnectorConfig('${escapeHtml(connector.id)}')">Save</button>
        <button class="secondary-btn" onclick="editConnectorInstance('${escapeHtml(connector.id)}')">Edit</button>
        <button class="danger-btn" onclick="deleteConnectorInstance('${escapeHtml(connector.id)}')">Delete</button>
      </div>
      <div class="connector-scope-list">
        ${scopeMarkup}
      </div>
      <div class="connector-action-hint">Scope selection overrides .env defaults for demo.</div>
    </div>
  `;
}

function renderConnectorCard(connector) {
  const status = connector.status || {};
  const sync = connector.sync || {};
  const config = connector.config || {};
  const data = connector.data || {};
  const actions = connector.actions || {};
  const latestCompleted = sync.latest_completed_run || null;
  const latestRun = sync.latest_run || null;
  const history = sync.history || [];
  const diagnostic = connectorDiagnostics[connector.id] || null;
  const statusClass = getConnectorBadgeClass(status.code);
  const canManage = !!actions.can_manage;
  const canTest = !!actions.can_test;
  const canSync = !!actions.can_sync;
  const liveTestMarkup = diagnostic
    ? `<div class="connector-live-test ${getConnectorTestClass(diagnostic.status)}">
        <strong>Live test</strong>
        <span>${escapeHtml(diagnostic.message || 'No details')}</span>
        <small>${diagnostic.latency_ms ? `${diagnostic.latency_ms} ms` : ''} ${diagnostic.checked_at ? `· ${formatDateTime(diagnostic.checked_at)}` : ''}</small>
      </div>`
    : '';
  const missingMarkup = connector.missing_settings && connector.missing_settings.length
    ? `<div class="connector-missing">Missing: ${connector.missing_settings.map(escapeHtml).join(', ')}</div>`
    : '';
  const syncStateText = sync.running
    ? `Running since ${formatDateTime((latestRun || {}).started_at)}`
    : `Last completed ${formatDateTime((latestCompleted || {}).finished_at || (latestCompleted || {}).last_sync_at)}.`;
  const actionHint = canManage ? '' : `<div class="connector-action-hint">Read-only for non-admin accounts.</div>`;
  const manageMarkup = renderConnectorManage(connector);

  return `
    <article class="connector-card connector-card-rich accent-${escapeHtml(connector.accent || 'default')}">
      <div class="connector-card-top">
        <div class="connector-header">
          <div class="connector-icon">${escapeHtml(getConnectorIcon(connector.icon || connector.connector_type || connector.id))}</div>
          <div>
            <div class="connector-name-row">
              <div class="connector-name">${escapeHtml(connector.name || connector.id)}</div>
              <span class="connector-kind">${escapeHtml(connector.kind || 'source')}</span>
            </div>
            <div class="connector-desc">${escapeHtml(connector.description || '')}</div>
          </div>
        </div>
        <div class="connector-status-badge ${statusClass}">
          <div class="status-dot-sm"></div><span>${escapeHtml(status.label || 'Unknown')}</span>
        </div>
      </div>

      <div class="connector-body">
        <div class="connector-body-copy">${escapeHtml(status.message || '')}</div>
        ${missingMarkup}

        <div class="connector-config-grid">
          <div class="connector-config-item">
            <span>${escapeHtml(config.target_label || 'Target')}</span>
            <strong>${escapeHtml(config.target_value || '—')}</strong>
          </div>
          <div class="connector-config-item">
            <span>${escapeHtml(config.scope_label || 'Scope')}</span>
            <strong>${escapeHtml(config.scope_value || '—')}</strong>
          </div>
          <div class="connector-config-item">
            <span>Auth</span>
            <strong>${escapeHtml(config.auth_label || 'Credentials')}: ${escapeHtml(config.auth_value || '—')}</strong>
          </div>
          <div class="connector-config-item">
            <span>Workspace binding</span>
            <strong>${escapeHtml(config.workspace_binding || '—')}</strong>
          </div>
        </div>

        <div class="connector-stats connector-stats-rich">
          <div class="stat-item">
            <div class="stat-value">${formatNumber(data.documents)}</div>
            <div class="stat-label">Documents</div>
          </div>
          <div class="stat-item">
            <div class="stat-value">${formatNumber(data.chunks)}</div>
            <div class="stat-label">Chunks</div>
          </div>
          <div class="stat-item">
            <div class="stat-value stat-value-small">${formatDateTime((latestCompleted || {}).finished_at || (latestCompleted || {}).last_sync_at)}</div>
            <div class="stat-label">Last Completed Sync</div>
          </div>
        </div>

        <div class="connector-run-strip ${sync.running ? 'running' : ''}">
          <div>
            <strong>${escapeHtml(sync.schedule_label || 'Manual')}</strong>
            <span>${escapeHtml(syncStateText)}</span>
          </div>
          <div class="connector-run-metrics">
            <span>Fetched ${formatNumber((latestRun || {}).fetched)}</span>
            <span>Indexed ${formatNumber((latestRun || {}).indexed)}</span>
            <span>Errors ${formatNumber((latestRun || {}).errors)}</span>
          </div>
        </div>

        <div class="connector-capabilities">
          ${(connector.capabilities || []).map(capability => `<span class="connector-capability">${escapeHtml(capability)}</span>`).join('')}
        </div>

        ${liveTestMarkup}
        ${manageMarkup}

        <div class="connector-actions-row">
          <button class="secondary-btn connector-action-btn" data-connector-test="${escapeHtml(connector.id)}" onclick="testConnector('${escapeHtml(connector.id)}')" ${canTest ? '' : 'disabled'}>
            Test connection
          </button>
          <button class="primary-btn connector-action-btn" data-connector-sync="${escapeHtml(connector.id)}" onclick="syncConnector('${escapeHtml(connector.id)}')" ${canSync ? '' : 'disabled'}>
            Sync now
          </button>
        </div>
        ${actionHint}

        <div class="connector-history">
          <div class="connector-section-title">Recent sync runs</div>
          ${renderConnectorHistory(history)}
        </div>
      </div>
    </article>
  `;
}

function renderConnectorDashboard() {
  renderConnectorSummary(connectorDirectory.summary);

  const tabsEl = document.getElementById('connectorTabs');
  const tabs = connectorDirectory.tabs || [];
  if (tabsEl) {
    if (!tabs.length) {
      tabsEl.innerHTML = '';
    } else {
      tabsEl.innerHTML = tabs.map(tab => {
        const active = (String(tab.type) === String(connectorActiveTab)) ? 'active' : '';
        const count = Array.isArray(tab.instances) ? tab.instances.length : 0;
        return `<button class="connector-tab-btn ${active}" onclick="setActiveConnectorTab('${tab.type}')">${escapeHtml(tab.label || tab.type)} (${count})</button>`;
      }).join('');
    }
  }

  const syncBtn = document.getElementById('syncTabConnectorsBtn');
  const clearBtn = document.getElementById('clearTabDataBtn');
  const addBtn = document.getElementById('addConnectorBtn');
  const isAdmin = !!AUTH.user?.is_admin;
  if (syncBtn) {
    syncBtn.disabled = !isAdmin;
    syncBtn.textContent = `Sync ${String(connectorActiveTab || '').toUpperCase()}`;
  }
  if (clearBtn) {
    clearBtn.style.display = isAdmin ? '' : 'none';
    clearBtn.textContent = `Clear ${String(connectorActiveTab || '').toUpperCase()}`;
  }
  if (addBtn) {
    addBtn.style.display = isAdmin ? '' : 'none';
  }

  const grid = document.getElementById('connectorsGrid');
  if (!grid) return;

  const activeTab = (tabs || []).find(t => String(t.type) === String(connectorActiveTab)) || (tabs || [])[0] || null;
  const connectors = (activeTab && activeTab.instances) ? activeTab.instances : [];
  if (!Array.isArray(connectors) || connectors.length === 0) {
    grid.innerHTML = '<div class="connectors-empty">No connector instances yet. Add one to start.</div>';
    return;
  }

  grid.innerHTML = connectors.map(renderConnectorCard).join('');
}

function setActiveConnectorTab(tabType) {
  connectorActiveTab = String(tabType || 'confluence');
  localStorage.setItem('kp_connector_tab', connectorActiveTab);
  renderConnectorDashboard();
}

async function testConnector(name) {
  const conn = connectorIndex[String(name || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }
  connectorDiagnostics[name] = {
    status: 'running',
    message: 'Testing connection...',
    checked_at: new Date().toISOString(),
  };
  renderConnectorDashboard();

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}/test`, {
      method: 'POST',
    });
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    const data = await response.json();
    connectorDiagnostics[name] = data;
    renderConnectorDashboard();
    showToast(data.status === 'ok' ? `${name} connection is healthy.` : `${name} connection check needs attention.`, data.status === 'ok' ? 'success' : 'error');
  } catch (error) {
    connectorDiagnostics[name] = {
      status: 'error',
      message: error.message || 'Connection test failed.',
      checked_at: new Date().toISOString(),
    };
    renderConnectorDashboard();
    showToast(error.message || `Cannot test ${name}.`, 'error');
  }
}

async function discoverConnectorScopes(name) {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const conn = connectorIndex[String(name || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}/discover`);
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    connectorScopeCache[name] = { items: data.items || [] };
    renderConnectorDashboard();
    showToast(`Discovered ${formatNumber((data.items || []).length)} items for ${name}.`);
  } catch (error) {
    showToast(error.message || 'Discovery failed.', 'error');
  }
}

async function saveConnectorConfig(name) {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const conn = connectorIndex[String(name || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }

  const enabledEl = document.getElementById(`cfg_enabled_${name}`);
  const autoEl = document.getElementById(`cfg_auto_${name}`);
  const timeEl = document.getElementById(`cfg_time_${name}`);

  const enabled = enabledEl ? !!enabledEl.checked : true;
  const auto_sync = autoEl ? !!autoEl.checked : false;
  const timeVal = timeEl ? (timeEl.value || '').trim() : '';

  if (auto_sync && !timeVal) {
    showToast('Please set a time for auto sync.', 'error');
    return;
  }

  let schedule_hour = null;
  let schedule_minute = null;
  if (auto_sync && timeVal.includes(':')) {
    const [hh, mm] = timeVal.split(':');
    schedule_hour = Number(hh);
    schedule_minute = Number(mm);
  }

  const safeName = (window.CSS && CSS.escape) ? CSS.escape(name) : name;
  const checks = Array.from(document.querySelectorAll(`input[data-scope-checkbox="${safeName}"]`));
  const selected = checks
    .filter(el => el.checked)
    .map(el => el.getAttribute('data-scope-value'))
    .filter(Boolean);

  const selection = buildConnectorSelectionPayload(name, selected);

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}/config`, {
      method: 'PUT',
      body: JSON.stringify({
        enabled,
        auto_sync,
        schedule_hour,
        schedule_minute,
        selection,
      }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Saved ${name} configuration.`);
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Save failed.', 'error');
  }
}

function _connectorTypeFromKey(key) {
  return String(key || '').split(':')[0] || '';
}

function _instanceIdFromKey(key) {
  return String(key || '').split(':')[1] || '';
}

async function openCreateConnectorInstance() {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const type = String(connectorActiveTab || 'confluence');

  const created = await openConnectorInstanceModal({ mode: 'create', type });
  if (!created) return;
  const { name, base_url, auth_type, username, secret, extra } = created;

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(type)}/instances`, {
      method: 'POST',
      body: JSON.stringify({ name, base_url, auth_type, username, secret, extra }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast('Connector instance created.', 'success');
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Cannot create connector.', 'error');
  }
}

async function editConnectorInstance(connectorKey) {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const conn = connectorIndex[String(connectorKey || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }
  const type = String(conn.connector_type || _connectorTypeFromKey(connectorKey));
  const instance_id = String(conn.instance_id || _instanceIdFromKey(connectorKey));

  const updated = await openConnectorInstanceModal({ mode: 'edit', type, conn });
  if (!updated) return;
  const payload = updated;

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(type)}/instances/${encodeURIComponent(instance_id)}`, {
      method: 'PUT',
      body: JSON.stringify(payload),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast('Connector updated.', 'success');
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Update failed.', 'error');
  }
}

async function deleteConnectorInstance(connectorKey) {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const conn = connectorIndex[String(connectorKey || '')];
  if (!conn) {
    showToast('Unknown connector instance.', 'error');
    return;
  }
  const ok = await kpConfirm({
    title: 'Delete connector',
    message: `Delete connector instance "${conn.instance_name || conn.name || conn.id}"?`,
    okText: 'Delete',
    cancelText: 'Cancel',
    danger: true,
  });
  if (!ok) return;

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(conn.connector_type)}/instances/${encodeURIComponent(conn.instance_id)}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast('Connector deleted.', 'success');
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Delete failed.', 'error');
  }
}

function _kpParseSmbBaseUrl(baseUrl) {
  const s = String(baseUrl || '');
  const m = s.match(/^\\\\([^\\]+)\\([^\\]+)/);
  if (!m) return { host: '', share: '' };
  return { host: m[1] || '', share: m[2] || '' };
}

function _kpBuildModalField({ id, label, type = 'text', value = '', placeholder = '', help = '', required = false, options = null } = {}) {
  const wrap = document.createElement('div');
  wrap.className = 'kp-modal-field';

  const lab = document.createElement('label');
  lab.className = 'kp-modal-label';
  lab.setAttribute('for', id);
  lab.textContent = label;
  wrap.appendChild(lab);

  let input = null;
  if (type === 'select') {
    input = document.createElement('select');
    (options || []).forEach(opt => {
      const o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.label;
      input.appendChild(o);
    });
    input.value = String(value || '');
  } else if (type === 'textarea') {
    input = document.createElement('textarea');
    input.value = String(value || '');
    input.rows = 4;
  } else {
    input = document.createElement('input');
    input.type = type;
    input.value = String(value || '');
  }

  input.id = id;
  input.name = id;
  input.className = 'time-input kp-modal-input';
  if (placeholder) input.placeholder = placeholder;
  if (required) input.required = true;

  wrap.appendChild(input);

  if (help) {
    const h = document.createElement('div');
    h.className = 'kp-modal-help';
    h.textContent = help;
    wrap.appendChild(h);
  }

  return { wrap, input };
}

async function openConnectorInstanceModal({ mode, type, conn } = {}) {
  const connectorType = String(type || '');
  const isEdit = String(mode) === 'edit';

  const currentName = isEdit ? String(conn?.instance_name || conn?.name || '') : `New ${connectorType}`;
  const currentBaseUrl = isEdit ? String((conn?.config || {}).target_value || '') : '';
  const currentAuthType = isEdit ? String((conn?.config || {}).auth_type || 'token') : 'token';
  const currentUsername = isEdit ? String((conn?.config || {}).username || '') : '';
  const currentInstanceId = isEdit ? String(conn?.instance_id || '') : '';

  let existingExtra = null;
  if (isEdit && connectorType === 'file_server' && currentInstanceId) {
    try {
      const resp = await authFetch(`${API}/connectors/${encodeURIComponent(connectorType)}/instances`);
      if (resp.ok) {
        const data = await resp.json();
        const inst = (data.instances || []).find(x => String(x.id || '') === currentInstanceId) || null;
        existingExtra = (inst && inst.extra && typeof inst.extra === 'object') ? inst.extra : {};
      }
    } catch (_) {
      existingExtra = existingExtra || {};
    }
  }

  const body = document.createElement('div');
  body.className = 'kp-modal-form-wrap';

  const form = document.createElement('form');
  form.className = 'kp-modal-form';
  body.appendChild(form);

  const fields = {};
  fields.name = _kpBuildModalField({
    id: 'kp_conn_name',
    label: 'Name',
    type: 'text',
    value: currentName,
    placeholder: 'Connector name',
    required: true,
  });
  form.appendChild(fields.name.wrap);

  if (connectorType === 'confluence' || connectorType === 'jira') {
    fields.base_url = _kpBuildModalField({
      id: 'kp_conn_base_url',
      label: 'Base URL',
      type: 'text',
      value: currentBaseUrl,
      placeholder: 'https://...',
      required: true,
    });
    form.appendChild(fields.base_url.wrap);

    fields.auth_type = _kpBuildModalField({
      id: 'kp_conn_auth_type',
      label: 'Auth type',
      type: 'select',
      value: (isEdit ? currentAuthType : 'token'),
      options: [
        { value: 'token', label: 'Token' },
        { value: 'basic', label: 'Basic' },
      ],
      required: true,
    });
    form.appendChild(fields.auth_type.wrap);

    fields.username = _kpBuildModalField({
      id: 'kp_conn_username',
      label: 'Email/Username',
      type: 'text',
      value: currentUsername,
      placeholder: 'you@example.com',
      required: false,
    });
    form.appendChild(fields.username.wrap);

    fields.secret = _kpBuildModalField({
      id: 'kp_conn_secret',
      label: 'API token',
      type: 'password',
      value: '',
      placeholder: isEdit ? 'Leave empty to keep current' : '',
      required: !isEdit,
    });
    form.appendChild(fields.secret.wrap);

    const syncUsernameVisibility = () => {
      const auth = String(fields.auth_type.input.value || 'token').toLowerCase().trim();
      const show = auth === 'basic';
      fields.username.wrap.style.display = show ? '' : 'none';
      fields.username.input.disabled = !show;
      if (!show) fields.username.input.value = '';
    };

    fields.auth_type.input.addEventListener('change', syncUsernameVisibility);
    syncUsernameVisibility();
  } else if (connectorType === 'slack') {
    fields.secret = _kpBuildModalField({
      id: 'kp_conn_secret',
      label: 'Slack bot token',
      type: 'password',
      value: '',
      placeholder: isEdit ? 'Leave empty to keep current' : 'xoxb-...',
      required: !isEdit,
    });
    form.appendChild(fields.secret.wrap);
  } else if (connectorType === 'file_server') {
    const smbFromExtra = existingExtra && typeof existingExtra === 'object' ? existingExtra : null;
    const smbParsed = _kpParseSmbBaseUrl(currentBaseUrl);
    const hostValue = (smbFromExtra && smbFromExtra.host) ? String(smbFromExtra.host) : smbParsed.host;
    const shareValue = (smbFromExtra && smbFromExtra.share) ? String(smbFromExtra.share) : smbParsed.share;
    const basePathValue = (smbFromExtra && smbFromExtra.base_path) ? String(smbFromExtra.base_path) : '\\';
    fields.host = _kpBuildModalField({
      id: 'kp_conn_smb_host',
      label: 'SMB host',
      type: 'text',
      value: hostValue,
      placeholder: 'fileserver.local',
      required: false,
      help: 'Leave empty to use server default (SMB_HOST) if configured.',
    });
    form.appendChild(fields.host.wrap);

    fields.share = _kpBuildModalField({
      id: 'kp_conn_smb_share',
      label: 'SMB share',
      type: 'text',
      value: shareValue,
      placeholder: 'ShareName',
      required: false,
      help: 'Leave empty to use server default (SMB_SHARE) if configured.',
    });
    form.appendChild(fields.share.wrap);

    fields.base_path = _kpBuildModalField({
      id: 'kp_conn_smb_base_path',
      label: 'Base path',
      type: 'text',
      value: basePathValue,
      placeholder: '\\\\ or folder',
      required: false,
      help: 'Default is \\\\ .',
    });
    form.appendChild(fields.base_path.wrap);

    fields.username = _kpBuildModalField({
      id: 'kp_conn_username',
      label: 'SMB username',
      type: 'text',
      value: currentUsername,
      placeholder: 'Username',
      required: !isEdit,
    });
    form.appendChild(fields.username.wrap);

    fields.secret = _kpBuildModalField({
      id: 'kp_conn_secret',
      label: 'SMB password',
      type: 'password',
      value: '',
      placeholder: isEdit ? 'Leave empty to keep current' : '',
      required: !isEdit,
    });
    form.appendChild(fields.secret.wrap);
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const okBtn = document.getElementById('kpModalOkBtn');
    if (okBtn) okBtn.click();
  });

  const title = isEdit ? 'Edit connector' : 'Add connector';
  const subtitle = connectorType ? String(connectorType).toUpperCase() : '';

  const result = await kpOpenModal({
    title,
    subtitle,
    content: body,
    okText: isEdit ? 'Save' : 'Create',
    cancelText: 'Cancel',
    okClass: 'primary-btn',
    onOk: () => {
      const name = String(fields.name?.input?.value || '').trim();
      if (!name) return { error: 'Name is required.' };

      if (connectorType === 'confluence' || connectorType === 'jira') {
        const base_url = String(fields.base_url.input.value || '').trim();
        const auth_type = String(fields.auth_type.input.value || 'token').toLowerCase().trim();
        const username = auth_type === 'basic' ? String(fields.username.input.value || '').trim() : '';
        const secret = String(fields.secret.input.value || '').trim();

        if (!base_url) return { error: 'Base URL is required.' };
        if (auth_type !== 'token' && auth_type !== 'basic') return { error: 'Auth type must be token or basic.' };
        if (auth_type === 'basic' && !username) return { error: 'Username is required for basic auth.' };
        if (!isEdit && !secret) return { error: 'API token is required.' };

        const payload = { name, base_url, auth_type, username };
        if (secret) payload.secret = secret;
        return payload;
      }

      if (connectorType === 'slack') {
        const secret = String(fields.secret.input.value || '').trim();
        if (!isEdit && !secret) return { error: 'Slack bot token is required.' };
        const payload = { name };
        if (secret) payload.secret = secret;
        return payload;
      }

      if (connectorType === 'file_server') {
        const host = String(fields.host.input.value || '').trim();
        const share = String(fields.share.input.value || '').trim();
        const base_path = String(fields.base_path.input.value || '').trim();
        const username = String(fields.username.input.value || '').trim();
        const secret = String(fields.secret.input.value || '').trim();

        if (!isEdit && !username) return { error: 'SMB username is required.' };
        if (!isEdit && !secret) return { error: 'SMB password is required.' };

        const prev = (existingExtra && typeof existingExtra === 'object') ? existingExtra : {};
        const finalHost = host || String(prev.host || '').trim() || '';
        const finalShare = share || String(prev.share || '').trim() || '';
        const finalBasePath = base_path || String(prev.base_path || '').trim() || '\\';
        const finalUsername = username || (isEdit ? currentUsername : '') || '';

        const base_url = (finalHost && finalShare) ? `\\\\${finalHost}\\${finalShare}` : (currentBaseUrl || '');
        const payload = {
          name,
          base_url,
          auth_type: 'basic',
          username: finalUsername,
          extra: { host: finalHost, share: finalShare, base_path: finalBasePath },
        };
        if (secret) payload.secret = secret;
        return payload;
      }

      return { name };
    },
  });

  if (!result) return null;

  // kpOpenModal returns `true` when no onOk, but here it always returns payload object.
  if (typeof result !== 'object') return null;

  if (!isEdit) {
    // Create expects full shape for API even if some optional fields omitted.
    return {
      name: result.name,
      base_url: result.base_url ?? null,
      auth_type: result.auth_type ?? 'token',
      username: result.username ?? null,
      secret: result.secret ?? null,
      extra: result.extra ?? null,
    };
  }

  return result;
}

async function syncCurrentConnectorTab() {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const tab = String(connectorActiveTab || 'confluence');
  const button = document.getElementById('syncTabConnectorsBtn');
  if (button) {
    button.disabled = true;
    button.textContent = 'Starting...';
  }

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(tab)}/sync-all`, { method: 'POST' });
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const started = data.started || [];
    const skipped = data.skipped || [];
    showToast(
      started.length
        ? `Started ${started.length} sync(s) for ${tab}.`
        : `No connector started for ${tab}. ${skipped.length ? 'All were skipped.' : ''}`,
      started.length ? 'success' : 'error'
    );
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || `Cannot sync ${tab}.`, 'error');
  } finally {
    if (button) {
      button.disabled = !AUTH.user.is_admin;
      button.textContent = `Sync ${tab.toUpperCase()}`;
    }
  }
}

async function clearCurrentConnectorTab() {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const tab = String(connectorActiveTab || 'confluence');
  const ok = await kpConfirm({
    title: 'Clear connector data',
    message: `Clear ALL synced data from ${tab} (Postgres + Qdrant) for demo? This cannot be undone.`,
    okText: 'Clear',
    cancelText: 'Cancel',
    danger: true,
  });
  if (!ok) return;

  const btn = document.getElementById('clearTabDataBtn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Clearing...';
  }

  try {
    const response = await authFetch(`${API}/connectors/${encodeURIComponent(tab)}/clear`, { method: 'POST' });
    if (!response.ok) throw new Error(await readApiError(response));
    showToast(`Cleared ${tab} demo data.`);
    connectorDiagnostics = {};
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Clear failed.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = `Clear ${tab.toUpperCase()}`;
    }
  }
}

async function clearAllKnowledgeBase() {
  if (!AUTH.user?.is_admin) {
    showToast('Admin access required.', 'error');
    return;
  }
  const ok = await kpConfirm({
    title: 'Clear ALL data',
    message: 'Clear ALL synced data (Postgres + Qdrant)? This cannot be undone.',
    okText: 'Clear ALL',
    cancelText: 'Cancel',
    danger: true,
  });
  if (!ok) return;

  const btn = document.getElementById('clearAllDataBtn');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Clearing...';
  }

  try {
    const response = await authFetch(`${API}/connectors/clear`, { method: 'POST' });
    if (!response.ok) throw new Error(await readApiError(response));
    connectorDiagnostics = {};
    showToast('Cleared ALL demo data.', 'success');
    await loadConnectorStats(true);
  } catch (error) {
    showToast(error.message || 'Clear failed.', 'error');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Clear ALL';
    }
  }
}

async function loadConnectorStats(force = false) {
  if (!AUTH.token) return;
  if (!force && document.getElementById('page-connectors') && !document.getElementById('page-connectors').classList.contains('active')) {
    // Keep catalog warm in background, but skip expensive rerenders if the page is not active.
  }

  try {
    const response = await authFetch(`${API}/connectors`);
    if (!response.ok) {
      throw new Error(await readApiError(response));
    }
    connectorDirectory = await response.json();

    // Build fast lookup for actions (test/sync/discover/config) by connector id (connector_key).
    connectorIndex = {};
    (connectorDirectory.tabs || []).forEach(tab => {
      (tab.instances || []).forEach(conn => {
        if (conn && conn.id) connectorIndex[String(conn.id)] = conn;
      });
    });
    if (!(connectorDirectory.tabs || []).some(t => String(t.type) === String(connectorActiveTab))) {
      connectorActiveTab = ((connectorDirectory.tabs || [])[0] || {}).type || 'confluence';
      localStorage.setItem('kp_connector_tab', connectorActiveTab);
    }
    renderConnectorDashboard();
  } catch (error) {
    console.warn('Cannot load connector stats:', error);
    const grid = document.getElementById('connectorsGrid');
    if (grid && document.getElementById('page-connectors')?.classList.contains('active')) {
      grid.innerHTML = `<div class="connectors-empty" style="color:var(--danger)">Failed to load connectors: ${escapeHtml(error.message || 'API error')}</div>`;
    }
  }
}

setInterval(loadTasksCount, 30000);

// ── Knowledge Health + Graph Visualization (Admin) ─────────────────────────────
let graphViz = {
  canvas: null,
  ctx: null,
  nodes: [],
  edges: [],
  nodeById: new Map(),
  layers: { detail: null, super: null },
  activeLayer: 'detail',
  highlightNodes: new Set(),
  highlightEdges: new Set(),
  running: false,
  q: '',
  transform: { x: 0, y: 0, k: 1 },
  drag: { mode: null, node: null, ox: 0, oy: 0 },
};

function _graphScreenToWorld(x, y) {
  const t = graphViz.transform;
  return { x: (x - t.x) / t.k, y: (y - t.y) / t.k };
}

function _graphWorldToScreen(x, y) {
  const t = graphViz.transform;
  return { x: x * t.k + t.x, y: y * t.k + t.y };
}

function resetGraphView() {
  const c = graphViz.canvas;
  const cx = c ? (c.width / 2) : 0;
  const cy = c ? (c.height / 2) : 0;
  // Start slightly zoomed out so the clustered (super) graph is readable by default.
  graphViz.transform = { x: cx, y: cy, k: 0.62 };
}

function graphSearchChanged() {
  graphViz.q = String(document.getElementById('graphSearchInput')?.value || '').trim().toLowerCase();
}

async function loadGraphDashboard(force = false) {
  if (!AUTH.user.is_admin) return;

  const healthGrid = document.getElementById('graphHealthGrid');
  const canvas = document.getElementById('graphCanvas');
  if (healthGrid && force) {
    healthGrid.innerHTML = `<div class="connector-summary-card"><span>Loading health...</span><strong>—</strong><small>Please wait</small></div>`;
  }

  try {
    const [hResp, gResp] = await Promise.all([
      authFetch(`${API}/graph/health`),
      authFetch(`${API}/graph/view?since_days=30&per_source=45&semantic_k=3&semantic_min_weight=3`),
    ]);
    if (!hResp.ok) throw new Error(await readApiError(hResp));
    if (!gResp.ok) throw new Error(await readApiError(gResp));

    const health = await hResp.json();
    const view = await gResp.json();

    renderGraphHealth(health);
    initGraphCanvas(canvas, view);
    renderGraphInsights(view.insights || []);
  } catch (error) {
    if (healthGrid) {
      healthGrid.innerHTML = `<div class="connector-summary-card"><span style="color:var(--danger)">Graph API error</span><strong>—</strong><small>${escapeHtml(error.message || 'Failed')}</small></div>`;
    }
  }
}

function renderGraphHealth(health) {
  const grid = document.getElementById('graphHealthGrid');
  if (!grid) return;

  const docs = health.documents_by_source || [];
  const stale = health.stale_sources_30d || [];
  const missing = health.missing_sources || [];

  const docsCards = docs.slice(0, 8).map(d => `
    <div class="connector-summary-card">
      <span>${escapeHtml(d.source || 'source')}</span>
      <strong>${Number(d.count || 0).toLocaleString('vi-VN')}</strong>
      <small>Documents</small>
    </div>
  `).join('');

  const coreCards = `
    <div class="connector-summary-card">
      <span>Entities</span>
      <strong>${Number(health.entities || 0).toLocaleString('vi-VN')}</strong>
      <small>Total entities extracted</small>
    </div>
    <div class="connector-summary-card">
      <span>Relations</span>
      <strong>${Number(health.relations || 0).toLocaleString('vi-VN')}</strong>
      <small>Total edges</small>
    </div>
    <div class="connector-summary-card">
      <span>Doc links</span>
      <strong>${Number(health.document_links || 0).toLocaleString('vi-VN')}</strong>
      <small>Explicit: ${Number(health.explicit_links || 0).toLocaleString('vi-VN')}</small>
    </div>
    <div class="connector-summary-card">
      <span>Orphans</span>
      <strong>${Number(health.orphan_entities || 0).toLocaleString('vi-VN')}</strong>
      <small>Entities without relations</small>
    </div>
    <div class="connector-summary-card ${stale.length ? 'warn' : ''}">
      <span>Stale sources</span>
      <strong>${stale.length}</strong>
      <small>${stale.length ? `>= 30d: ${escapeHtml(stale.map(s => s.source).slice(0, 3).join(', '))}` : 'No stale sources'}</small>
    </div>
    <div class="connector-summary-card ${missing.length ? 'danger' : ''}">
      <span>Missing sources</span>
      <strong>${missing.length}</strong>
      <small>${missing.length ? escapeHtml(missing.slice(0, 4).join(', ')) : 'All sources have data'}</small>
    </div>
  `;

  grid.innerHTML = coreCards + docsCards;
}

function renderGraphInsights(insights) {
  const wrap = document.getElementById('graphInsights');
  if (!wrap) return;
  const list = Array.isArray(insights) ? insights : [];
  if (!list.length) {
    wrap.style.display = 'none';
    wrap.innerHTML = '';
    return;
  }
  wrap.style.display = '';
  wrap.innerHTML = list.slice(0, 6).map(it => `
    <div class="graph-insight-card ${String(it.severity || '').toLowerCase() === 'warning' ? 'warn' : ''}">
      <div class="graph-insight-title">${escapeHtml(it.title || it.type || 'Insight')}</div>
      <div class="graph-insight-detail">${escapeHtml(it.detail || '')}</div>
    </div>
  `).join('');
}

function initGraphCanvas(canvas, view) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  function buildLayer(graph, fallbackColor) {
    const rawNodes = (graph && graph.nodes) ? graph.nodes : [];
    const nodes = rawNodes.map((n, i) => ({
      id: String(n.id || i),
      label: String(n.label || n.id || 'node'),
      kind: String(n.kind || 'node'),
      source: String(n.source || ''),
      subkind: String(n.subkind || ''),
      type: String(n.subkind || n.kind || 'node'),
      mentions: Number((n.meta && n.meta.mentions) || 0),
      color: String(n.color || fallbackColor || 'rgba(148,163,184,0.85)'),
      icon: String(n.icon || ''),
      url: String(n.url || ''),
      meta: (n.meta && typeof n.meta === 'object') ? n.meta : {},
      size: Number(n.size || 11.5),
      x: (Math.random() - 0.5) * 860,
      y: (Math.random() - 0.5) * 520,
      vx: 0,
      vy: 0,
      pinned: false,
    }));
    const nodeById = new Map(nodes.map(n => [n.id, n]));
    const rawEdges = (graph && graph.edges) ? graph.edges : [];
    const edges = rawEdges
      .map(e => ({
        source: String(e.source || ''),
        target: String(e.target || ''),
        kind: String(e.kind || 'edge'),
        relation: String(e.relation || ''),
        weight: Number(e.weight || 1),
        meta: (e.meta && typeof e.meta === 'object') ? e.meta : {},
      }))
      .filter(e => nodeById.has(e.source) && nodeById.has(e.target));
    return { nodes, edges, nodeById };
  }

  const detail = buildLayer(view.detail || {}, 'rgba(194,65,12,0.75)');
  const superLayer = buildLayer(view.super || {}, 'rgba(15,118,110,0.85)');

  // Place super nodes near the centroid of their member docs (if present).
  try {
    const members = (view.super && view.super.members) ? view.super.members : {};
    for (const s of superLayer.nodes) {
      const mids = members[String(s.id)] || [];
      if (!mids.length) continue;
      let sx = 0, sy = 0, c = 0;
      for (const mid of mids) {
        const dn = detail.nodeById.get(String(mid));
        if (!dn) continue;
        sx += dn.x; sy += dn.y; c++;
      }
      if (c) {
        s.x = sx / c; s.y = sy / c;
      }
    }
  } catch {}

  graphViz.canvas = canvas;
  graphViz.ctx = ctx;
  graphViz.layers = { detail, super: superLayer };
  graphViz.activeLayer = (graphViz.transform.k < 0.65) ? 'super' : 'detail';
  graphViz.nodes = graphViz.layers[graphViz.activeLayer].nodes;
  graphViz.edges = graphViz.layers[graphViz.activeLayer].edges;
  graphViz.nodeById = graphViz.layers[graphViz.activeLayer].nodeById;
  graphViz.highlightNodes = new Set();
  graphViz.highlightEdges = new Set();
  graphViz.running = true;

  // Resize to container if possible.
  try {
    const parent = canvas.parentElement;
    if (parent) {
      const r = parent.getBoundingClientRect();
      canvas.width = Math.max(720, Math.floor(r.width));
      canvas.height = Math.max(420, 520);
    }
  } catch {}

  resetGraphView();
  _graphSelectLayer();

  // Bind events once.
  if (!canvas.__graphBound) {
    canvas.__graphBound = true;

    canvas.addEventListener('mousedown', (ev) => {
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const p = _graphScreenToWorld(sx, sy);

      const hit = _graphPickNode(p.x, p.y);
      if (hit) {
        graphViz.drag.mode = 'node';
        graphViz.drag.node = hit;
        hit.pinned = true;
      } else {
        graphViz.drag.mode = 'pan';
        graphViz.drag.ox = ev.clientX;
        graphViz.drag.oy = ev.clientY;
      }
    });

    window.addEventListener('mouseup', () => {
      graphViz.drag.mode = null;
      graphViz.drag.node = null;
    });

    window.addEventListener('mousemove', (ev) => {
      if (!graphViz.running) return;
      if (!graphViz.drag.mode) return;
      if (graphViz.drag.mode === 'pan') {
        const dx = ev.clientX - graphViz.drag.ox;
        const dy = ev.clientY - graphViz.drag.oy;
        graphViz.drag.ox = ev.clientX;
        graphViz.drag.oy = ev.clientY;
        graphViz.transform.x += dx;
        graphViz.transform.y += dy;
      }
      if (graphViz.drag.mode === 'node' && graphViz.drag.node) {
        const rect = canvas.getBoundingClientRect();
        const sx = ev.clientX - rect.left;
        const sy = ev.clientY - rect.top;
        const p = _graphScreenToWorld(sx, sy);
        graphViz.drag.node.x = p.x;
        graphViz.drag.node.y = p.y;
        graphViz.drag.node.vx = 0;
        graphViz.drag.node.vy = 0;
      }
    });

    canvas.addEventListener('dblclick', (ev) => {
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const p = _graphScreenToWorld(sx, sy);
      const hit = _graphPickNode(p.x, p.y);
      if (!hit) return;
      renderGraphNodeDetail(hit);
    });

    canvas.addEventListener('wheel', (ev) => {
      ev.preventDefault();
      const rect = canvas.getBoundingClientRect();
      const sx = ev.clientX - rect.left;
      const sy = ev.clientY - rect.top;
      const before = _graphScreenToWorld(sx, sy);
      const zoom = ev.deltaY < 0 ? 1.08 : 1 / 1.08;
      graphViz.transform.k = Math.max(0.35, Math.min(2.8, graphViz.transform.k * zoom));
      const after = _graphWorldToScreen(before.x, before.y);
      graphViz.transform.x += (sx - after.x);
      graphViz.transform.y += (sy - after.y);
    }, { passive: false });
  }

  _graphLoop();
}

function _graphPickNode(x, y) {
  const nodes = graphViz.nodes || [];
  for (let i = nodes.length - 1; i >= 0; i--) {
    const n = nodes[i];
    const r = Math.max(8, Number(n.size || 12));
    const dx = n.x - x;
    const dy = n.y - y;
    if ((dx * dx + dy * dy) <= (r * r)) return n;
  }
  return null;
}

function renderGraphNodeDetail(node) {
  const panel = document.getElementById('graphNodeDetail');
  if (!panel) return;
  panel.style.display = 'block';
  panel.innerHTML = `
    <div class="graph-detail-title">${escapeHtml(node.label)}</div>
    <div class="graph-detail-meta">Type: ${escapeHtml(node.type)} · Mentions: ${Number(node.mentions || 0).toLocaleString('vi-VN')}</div>
    <div class="graph-detail-actions">
      <button class="secondary-btn mini" onclick="closeGraphDetail()">Close</button>
      <button class="secondary-btn mini" onclick="unpinGraphNode('${escapeHtml(node.id)}')">Unpin</button>
      <button class="secondary-btn mini" onclick="graphFocusNode('${escapeHtml(node.id)}')">Focus</button>
      <button class="secondary-btn mini" onclick="graphOpenNode('${escapeHtml(node.id)}')">Open</button>
      <button class="secondary-btn mini" onclick="graphTraceNode('${escapeHtml(node.id)}')">Trace</button>
      <button class="secondary-btn mini" onclick="graphImpactNode('${escapeHtml(node.id)}')">Impact</button>
      <button class="secondary-btn mini" onclick="graphClearHighlight()">Clear</button>
    </div>
  `;
}

function closeGraphDetail() {
  const panel = document.getElementById('graphNodeDetail');
  if (panel) panel.style.display = 'none';
}

function unpinGraphNode(nodeId) {
  const n = graphViz.nodeById.get(String(nodeId || ''));
  if (n) n.pinned = false;
}

function graphClearHighlight() {
  graphViz.highlightNodes = new Set();
  graphViz.highlightEdges = new Set();
}

function _graphEdgeKey(e) {
  return `${String(e.source || '')}|${String(e.target || '')}|${String(e.kind || '')}|${String(e.relation || '')}`;
}

function graphOpenNode(nodeId) {
  const n = graphViz.nodeById.get(String(nodeId || ''));
  const url = n && n.url ? String(n.url) : '';
  if (!url) return showToast('No URL for this node.', 'info');
  try { window.open(url, '_blank'); } catch {}
}

async function graphFocusNode(nodeId) {
  try {
    const r = await authFetch(`${API}/graph/focus?node_id=${encodeURIComponent(String(nodeId || ''))}&depth=2&max_docs=260`);
    if (!r.ok) throw new Error(await readApiError(r));
    const payload = await r.json();
    initGraphCanvas(document.getElementById('graphCanvas'), { detail: payload.detail, super: payload.super });
    renderGraphInsights(payload.insights || []);
    graphClearHighlight();
  } catch (e) {
    showToast(`Graph focus failed: ${e.message || 'API error'}`, 'error');
  }
}

async function graphTraceNode(nodeId) {
  const id = String(nodeId || '');
  const docId = id.startsWith('doc:') ? id.split(':', 2)[1] : '';
  if (!docId) return showToast('Trace is available for document nodes only.', 'info');
  try {
    const r = await authFetch(`${API}/graph/trace?doc_id=${encodeURIComponent(docId)}&depth=4`);
    if (!r.ok) throw new Error(await readApiError(r));
    const d = await r.json();
    if (d.detail && d.super) {
      initGraphCanvas(document.getElementById('graphCanvas'), { detail: d.detail, super: d.super });
      renderGraphInsights(d.insights || []);
    }
    graphViz.highlightNodes = new Set(d.highlight_nodes || []);
    graphViz.highlightEdges = new Set(d.highlight_edges || []);
  } catch (e) {
    showToast(`Trace failed: ${e.message || 'API error'}`, 'error');
  }
}

async function graphImpactNode(nodeId) {
  const id = String(nodeId || '');
  const docId = id.startsWith('doc:') ? id.split(':', 2)[1] : '';
  if (!docId) return showToast('Impact is available for document nodes only.', 'info');
  try {
    const r = await authFetch(`${API}/graph/impact?doc_id=${encodeURIComponent(docId)}&depth=3`);
    if (!r.ok) throw new Error(await readApiError(r));
    const d = await r.json();
    if (d.detail && d.super) {
      initGraphCanvas(document.getElementById('graphCanvas'), { detail: d.detail, super: d.super });
      renderGraphInsights(d.insights || []);
    }
    graphViz.highlightNodes = new Set(d.highlight_nodes || []);
    graphViz.highlightEdges = new Set(d.highlight_edges || []);
  } catch (e) {
    showToast(`Impact failed: ${e.message || 'API error'}`, 'error');
  }
}

function _graphSelectLayer() {
  const want = (graphViz.transform.k < 0.65) ? 'super' : 'detail';
  if (!graphViz.layers || !graphViz.layers[want]) return;
  if (graphViz.activeLayer === want) return;
  graphViz.activeLayer = want;
  graphViz.nodes = graphViz.layers[want].nodes;
  graphViz.edges = graphViz.layers[want].edges;
  graphViz.nodeById = graphViz.layers[want].nodeById;
}

function _graphLoop() {
  if (!graphViz.running || !graphViz.canvas || !graphViz.ctx) return;
  const active = !!document.getElementById('page-graph')?.classList.contains('active');
  if (active) {
    _graphSelectLayer();
    _graphStep();
    _graphDraw();
  }
  requestAnimationFrame(_graphLoop);
}

function _graphStep() {
  const nodes = graphViz.nodes;
  const edges = graphViz.edges;
  if (!nodes || !edges) return;

  const repulsion = 4200;
  const springK = 0.012;
  const targetLen = 92;
  const damping = 0.88;

  // Repulsion: exact for small graphs, sampled for large graphs (keeps UI responsive).
  const N = nodes.length;
  if (N <= 240) {
    for (let i = 0; i < N; i++) {
      for (let j = i + 1; j < N; j++) {
        const a = nodes[i], b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01;
        const f = repulsion / d2;
        const fx = (dx / Math.sqrt(d2)) * f;
        const fy = (dy / Math.sqrt(d2)) * f;
        if (!a.pinned) { a.vx += fx; a.vy += fy; }
        if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
      }
    }
  } else {
    const samples = Math.min(34, N - 1);
    for (let i = 0; i < N; i++) {
      const a = nodes[i];
      for (let s = 0; s < samples; s++) {
        const j = (i * 31 + s * 97) % N;
        if (j === i) continue;
        const b = nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = dx * dx + dy * dy + 0.01;
        const f = repulsion / d2;
        const fx = (dx / Math.sqrt(d2)) * f;
        const fy = (dy / Math.sqrt(d2)) * f;
        if (!a.pinned) { a.vx += fx; a.vy += fy; }
      }
    }
  }

  // Springs along edges
  for (const e of edges) {
    const a = graphViz.nodeById.get(e.source);
    const b = graphViz.nodeById.get(e.target);
    if (!a || !b) continue;
    const dx = b.x - a.x;
    const dy = b.y - a.y;
    const d = Math.sqrt(dx * dx + dy * dy) + 0.01;
    const diff = d - targetLen;
    const f = springK * diff;
    const fx = (dx / d) * f;
    const fy = (dy / d) * f;
    if (!a.pinned) { a.vx += fx; a.vy += fy; }
    if (!b.pinned) { b.vx -= fx; b.vy -= fy; }
  }

  // Integrate
  for (const n of nodes) {
    if (n.pinned) continue;
    n.vx *= damping;
    n.vy *= damping;
    n.x += n.vx * 0.016;
    n.y += n.vy * 0.016;
  }
}

function _graphDraw() {
  const canvas = graphViz.canvas;
  const ctx = graphViz.ctx;
  if (!canvas || !ctx) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.save();

  // Background
  ctx.fillStyle = 'rgba(255,255,255,0.35)';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  ctx.translate(graphViz.transform.x, graphViz.transform.y);
  ctx.scale(graphViz.transform.k, graphViz.transform.k);

  // Edges
  const hlNodes = graphViz.highlightNodes || new Set();
  const hlEdges = graphViz.highlightEdges || new Set();

  function edgeHighlighted(e) {
    const k1 = _graphEdgeKey(e);
    const k2 = `${String(e.target || '')}|${String(e.source || '')}|${String(e.kind || '')}|${String(e.relation || '')}`;
    return hlEdges.has(k1) || hlEdges.has(k2);
  }

  for (const e of graphViz.edges) {
    const a = graphViz.nodeById.get(e.source);
    const b = graphViz.nodeById.get(e.target);
    if (!a || !b) continue;

    const kind = String(e.kind || '');
    const isHL = edgeHighlighted(e);

    ctx.setLineDash([]);
    ctx.lineWidth = (isHL ? 2.2 : 1) / graphViz.transform.k;

    if (kind === 'semantic') {
      ctx.strokeStyle = isHL ? 'rgba(15,118,110,0.85)' : 'rgba(15,118,110,0.20)';
      ctx.setLineDash([6 / graphViz.transform.k, 4 / graphViz.transform.k]);
    } else if (kind === 'explicit') {
      ctx.strokeStyle = isHL ? 'rgba(29,78,216,0.85)' : 'rgba(69,47,26,0.22)';
    } else if (kind === 'membership') {
      ctx.strokeStyle = 'rgba(100,116,139,0.10)';
    } else if (kind === 'actor') {
      ctx.strokeStyle = 'rgba(100,116,139,0.16)';
    } else {
      ctx.strokeStyle = 'rgba(69,47,26,0.16)';
    }

    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  // Nodes
  const q = (graphViz.q || '').toLowerCase();
  for (const n of graphViz.nodes) {
    const label = String(n.label || '');
    const match = q && label.toLowerCase().includes(q);
    const isHL = hlNodes.has(String(n.id || ''));
    const r = Math.max(8, Number(n.size || 11.5));

    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
    ctx.fillStyle = String(n.color || 'rgba(148,163,184,0.85)');
    ctx.fill();

    if (match || isHL || n.pinned) {
      ctx.strokeStyle = isHL ? 'rgba(15,118,110,0.95)' : (match ? 'rgba(15,118,110,0.75)' : 'rgba(15,118,110,0.55)');
      ctx.lineWidth = (isHL ? 2.4 : 2) / graphViz.transform.k;
      ctx.stroke();
    }
  }

  // Simple "icon" letters for quick recognition when zoomed in.
  if (graphViz.transform.k > 0.95 && (graphViz.nodes || []).length < 260) {
    ctx.font = `${10 / graphViz.transform.k}px DM Sans`;
    ctx.fillStyle = 'rgba(255,255,255,0.92)';
    for (const n of graphViz.nodes) {
      const kind = String(n.kind || '');
      let t = '';
      if (kind === 'jira') t = 'J';
      else if (kind === 'confluence') t = 'C';
      else if (kind === 'slack') t = 'S';
      else if (kind === 'file') t = 'F';
      else if (kind === 'user') t = 'U';
      else if (kind === 'super') t = '◎';
      if (!t) continue;
      ctx.fillText(t, n.x - (3.5 / graphViz.transform.k), n.y + (3.5 / graphViz.transform.k));
    }
  }

  // Labels for matches
  if (q || (hlNodes && hlNodes.size)) {
    ctx.font = `${12 / graphViz.transform.k}px DM Sans`;
    ctx.fillStyle = 'rgba(32,21,13,0.9)';
    for (const n of graphViz.nodes) {
      const label = String(n.label || '');
      const match = q && label.toLowerCase().includes(q);
      const isHL = hlNodes.has(String(n.id || ''));
      if (!match && !isHL) continue;
      ctx.fillText(label.slice(0, 28), n.x + 10, n.y - 10);
    }
  }

  ctx.restore();
}
