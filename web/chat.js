import { API, authFetch } from '../api/client.js';
import { readApiError, escapeHtml, formatNumber, showToast, kpOpenModal, _kpBuildModalField } from '../utils/ui.js';
import { formatTime, safeHostname, parseThinking, getSourceIcon, getBadgeClass, formatRelevancePercent } from '../utils/format.js';
import { basketAddDocument } from './basket.js';
import { loadTasks, loadTasksCount } from './tasks.js';

export let chatHistory = [];
export let assistantMessageStore = {};

let _navigateCallback = null;
let _openDocDraftEditorCallback = null;

export function setChatCallbacks({ navigate, openDocDraftEditor }) {
  _navigateCallback = navigate;
  _openDocDraftEditorCallback = openDocDraftEditor;
}

export function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 120) + 'px';
}

export function handleKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
}

export function useSuggestion(el) {
  document.getElementById('chatInput').value = el.textContent;
  const empty = document.getElementById('emptyState');
  if (empty) empty.style.display = 'none';
  sendMessage();
}

export function buildAgentStepsHTML(steps, usedTools, plan) {
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

export function renderAnswer(text) {
  text = text.replace(/\[Source[s]?:?[^\]]*\]/gi, '').trim();
  return text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code style="background:var(--bg3);padding:1px 5px;border-radius:4px;font-size:12px">$1</code>')
    .replace(/\n/g, '<br>');
}

export function appendMessage(role, content, sources = [], agentSteps = [], usedTools = [], agentPlan = [], meta = {}) {
  const empty = document.getElementById('emptyState');
  if (empty) empty.remove();

  const wrap = document.getElementById('chatMessages');
  const div  = document.createElement('div');
  div.className = `message ${role}`;

  const userAv = document.getElementById('sidebarAvatar') ? document.getElementById('sidebarAvatar').textContent : 'U';
  const avatarHTML = role === 'user'
    ? `<div class="msg-avatar user-av">${userAv}</div>`
    : `<div class="msg-avatar ai-av">🤖</div>`;

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

  const msgId = 'msg-' + Date.now();

  if (role === 'assistant' && meta && meta.question) {
    assistantMessageStore[msgId] = {
      question: String(meta.question || ''),
      answer: String(displayContent || ''),
      sources: (sources || []).slice(0, 12),
    };
  }

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

  const sourcesBtn = (role === 'assistant' && validSources.length > 0)
    ? `<button class="sources-toggle-btn" onclick="toggleSources('sp-${msgId}', this)">📎 ${validSources.length} nguồn</button>`
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

export function toggleSources(id, btn) {
  const panel = document.getElementById(id);
  if (!panel) return;
  const isOpen = panel.style.display !== 'none';
  panel.style.display = isOpen ? 'none' : 'block';
  btn.classList.toggle('active', !isOpen);
}

let _citationPeekEl = null;
let _citationPeekHideTimer = null;

export function _ensureCitationPeek() {
  if (_citationPeekEl) return _citationPeekEl;
  const el = document.createElement('div');
  el.className = 'citation-peek';
  el.style.display = 'none';
  document.body.appendChild(el);
  _citationPeekEl = el;
  return el;
}

export function showCitationPeek(ev) {
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

export function hideCitationPeek() {
  if (!_citationPeekEl) return;
  if (_citationPeekHideTimer) clearTimeout(_citationPeekHideTimer);
  _citationPeekHideTimer = setTimeout(() => {
    if (_citationPeekEl) _citationPeekEl.style.display = 'none';
  }, 60);
}

export function toggleThinking(el) {
  const content = el.nextElementSibling;
  const chevron = el.querySelector('.thinking-chevron');
  const isOpen  = content.style.display !== 'none';
  content.style.display = isOpen ? 'none' : 'block';
  chevron.textContent   = isOpen ? '▸' : '▾';
}

export function appendTyping() {
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

export async function sendMessage() {
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

export async function doSearch() {
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
    if (!response.ok) throw new Error(await readApiError(response));

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

export function renderHistory() {
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

export function loadHistory(i) {
  const h = chatHistory[i];
  if (_navigateCallback) _navigateCallback('chat', document.querySelectorAll('.nav-item')[0]);
  setTimeout(() => {
    appendMessage('user', h.question);
    appendMessage('assistant', h.answer, h.sources);
  }, 100);
}

export async function createTaskFromAnswer(msgId) {
  const payload = assistantMessageStore[msgId];
  if (!payload) {
    showToast('Không tìm thấy message context.', 'error');
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
    if (_navigateCallback) _navigateCallback('tasks', document.getElementById('nav-tasks'));
    await loadTasks();
  } catch (error) {
    showToast(error.message || 'Cannot create task draft.', 'error');
  }
}

function _docDraftLabel(key) {
  const k = String(key || '').trim().toLowerCase();
  const labels = {
    srs: 'SRS', brd: 'BRD', api_spec: 'API Spec', use_cases: 'Use Cases',
    validation_rules: 'Validation Rules', user_stories: 'User Stories',
    requirements_intake: 'Requirements Intake', requirement_review: 'Requirement Review',
    solution_design: 'Solution Design', fe_spec: 'FE Spec', qa_test_spec: 'QA Test Spec',
    deployment_spec: 'Deployment Spec', change_request: 'Change Request',
    release_notes: 'Release Notes', function_list: 'Function List', risk_log: 'Risk Log',
  };
  return labels[k] || k.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase()) || 'Draft';
}

export async function generateDocFromAnswer(msgId, presetDocType = '') {
  const payload = assistantMessageStore[msgId];
  if (!payload) {
    showToast('Không tìm thấy message context.', 'error');
    return;
  }

  let docType = String(presetDocType || '').trim().toLowerCase();
  let title = '';

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
    
    const supportedTypes = ['srs', 'brd', 'api_spec', 'use_cases', 'validation_rules', 'user_stories', 'requirements_intake', 'requirement_review', 'solution_design', 'fe_spec', 'qa_test_spec', 'deployment_spec', 'change_request', 'release_notes', 'function_list', 'risk_log'];
    supportedTypes.forEach(k => {
      const opt = document.createElement('option');
      opt.value = k;
      opt.textContent = _docDraftLabel(k);
      typeSelect.appendChild(opt);
    });
    typeSelect.value = 'srs';
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

    const help = document.createElement('div');
    help.className = 'kp-modal-help';
    help.textContent = 'Hệ thống sẽ dùng các sources (Confluence/Jira/Slack/File) trong câu trả lời này để tạo bản nháp (Markdown).';

    form.appendChild(typeWrap);
    form.appendChild(titleWrap);
    form.appendChild(help);
    body.appendChild(form);

    const cfg = await kpOpenModal({
      title: 'Tạo bản nháp',
      subtitle: 'Chọn loại tài liệu cần tạo',
      content: body,
      okText: 'Tạo',
      cancelText: 'Hủy',
      onOk: async () => {
        const t = String(typeSelect.value || '').trim().toLowerCase();
        if (!t) return { error: 'Vui lòng chọn loại tài liệu.' };
        return { docType: t, title: String(titleInput.value || '').trim() };
      }
    });
    if (!cfg) return;
    docType = String(cfg.docType || '').trim().toLowerCase();
    title = String(cfg.title || '').trim();
  }

  try {
    const response = await authFetch(`${API}/docs/drafts/from-answer`, {
      method: 'POST',
      body: JSON.stringify({
        doc_type: docType || 'srs',
        title: title || '',
        question: payload.question,
        answer: payload.answer,
        sources: payload.sources || [],
      }),
    });
    if (!response.ok) throw new Error(await readApiError(response));
    const data = await response.json();
    const draft = data && data.draft ? data.draft : null;
    if (!draft || !draft.id) throw new Error('Invalid draft response.');
    showToast(`Đã tạo bản nháp ${_docDraftLabel(docType)}.`, 'success');
    if (_openDocDraftEditorCallback) _openDocDraftEditorCallback(draft.id);
  } catch (error) {
    showToast(error.message || 'Không thể tạo draft.', 'error');
  }
}