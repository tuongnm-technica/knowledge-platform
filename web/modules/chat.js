// Chat Module — AI chat, search, history
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml } from '../utils/ui.js';

let _callbacks = {};

export function setChatCallbacks(callbacks) {
  _callbacks = callbacks || {};
}

// ─── Resize textarea ────────────────────────────────────────────────────────

export function autoResize(el) {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 180) + 'px';
}

// ─── Keyboard handler ───────────────────────────────────────────────────────

export function handleKey(event) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault();
    sendMessage();
  }
}

// ─── Suggestion chip click ──────────────────────────────────────────────────

export function useSuggestion(el) {
  const input = document.getElementById('chatInput');
  if (!input || !el) return;
  input.value = el.textContent.trim();
  autoResize(input);
  input.focus();
  sendMessage();
}

// ─── Send message ────────────────────────────────────────────────────────────

export async function sendMessage() {
  const input   = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  if (!input) return;

  const question = input.value.trim();
  if (!question) return;

  // Clear input immediately
  input.value = '';
  autoResize(input);

  // Hide the empty state hero
  const emptyState = document.getElementById('emptyState');
  if (emptyState) emptyState.style.display = 'none';

  // Append user bubble
  appendBubble('user', escapeHtml(question));

  // Show thinking indicator
  const thinkId = 'think-' + Date.now();
  appendThinking(thinkId);

  if (sendBtn) sendBtn.disabled = true;

  try {
    const resp = await authFetch(`${API}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${resp.status}`);
    }
    const data = await resp.json();
    removeThinking(thinkId);
    appendBubble('ai', formatAnswer(data), data);
    scrollChatBottom();
  } catch (e) {
    removeThinking(thinkId);
    appendBubble('ai', `<span class="chat-error">⚠️ Lỗi: ${escapeHtml(e.message)}</span>`);
    scrollChatBottom();
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    input.focus();
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function appendBubble(role, html, data) {
  const container = document.getElementById('chatMessages');
  if (!container) return;

  const wrap = document.createElement('div');
  wrap.className = `chat-message chat-message-${role}`;

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble chat-bubble-${role}`;
  bubble.innerHTML = html;

  wrap.appendChild(bubble);

  // Action bar for AI answers
  if (role === 'ai' && data) {
    const actions = buildActionBar(data);
    if (actions) wrap.appendChild(actions);
  }

  container.appendChild(wrap);
  scrollChatBottom();
}

function appendThinking(id) {
  const container = document.getElementById('chatMessages');
  if (!container) return;
  const div = document.createElement('div');
  div.className = 'chat-message chat-message-ai';
  div.id = id;
  div.innerHTML = `
    <div class="chat-bubble chat-bubble-ai chat-thinking">
      <span class="thinking-dot"></span>
      <span class="thinking-dot"></span>
      <span class="thinking-dot"></span>
    </div>`;
  container.appendChild(div);
  scrollChatBottom();
}

function removeThinking(id) {
  document.getElementById(id)?.remove();
}

function scrollChatBottom() {
  const c = document.getElementById('chatMessages');
  if (c) c.scrollTop = c.scrollHeight;
}

function formatAnswer(data) {
  if (!data) return '';
  let html = `<div class="chat-answer-text">${markdownToHtml(data.answer || '')}</div>`;

  // Sources
  const srcs = Array.isArray(data.sources) ? data.sources.slice(0, 6) : [];
  if (srcs.length) {
    html += `<div class="chat-sources">`;
    srcs.forEach(s => {
      const title = escapeHtml(s.title || s.source_id || 'Source');
      const url   = s.url || '#';
      const score = s.score != null ? Math.round(s.score * 100) + '%' : '';
      const docId = s.source_id || '';
      html += `
        <div class="chat-source-chip-wrapper">
          <a class="chat-source-chip" href="${escapeHtml(url)}" target="_blank" rel="noopener">
            <span class="chat-source-icon">📄</span>
            <span class="chat-source-title">${title}</span>
            ${score ? `<span class="chat-source-score">${score}</span>` : ''}
          </a>
          <button class="chat-source-pin" onclick="addToBasket('${escapeHtml(docId)}', '${escapeHtml(title)}')" title="Ghim ngữ cảnh">📌</button>
        </div>`;
    });
    html += `</div>`;
  }

  return html;
}

function buildActionBar(data) {
  if (!data || !data.sources || !data.sources.length) return null;
  if (typeof _callbacks.navigate !== 'function') return null;

  const bar = document.createElement('div');
  bar.className = 'chat-action-bar';

  // Draft button
  const draftBtn = document.createElement('button');
  draftBtn.className = 'chat-action-btn';
  draftBtn.textContent = '📄 Tạo Draft';
  draftBtn.addEventListener('click', () => {
    if (_callbacks.navigate) _callbacks.navigate('basket');
  });
  bar.appendChild(draftBtn);

  return bar;
}

function markdownToHtml(md) {
  if (!md) return '';
  // Very simple markdown-to-html: bold, italic, code, headers, lists
  let html = escapeHtml(md);
  // code blocks
  html = html.replace(/```[\w]*\n?([\s\S]*?)```/g, (_, code) =>
    `<pre class="chat-code-block"><code>${code.trim()}</code></pre>`);
  // inline code
  html = html.replace(/`([^`]+)`/g, '<code class="chat-inline-code">$1</code>');
  // headers
  html = html.replace(/^### (.+)$/gm, '<h3 class="chat-h3">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="chat-h2">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="chat-h1">$1</h1>');
  // bold + italic
  html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  // unordered lists
  html = html.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
  html = html.replace(/(<li>.*<\/li>\n?)+/g, m => `<ul class="chat-list">${m}</ul>`);
  // ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');
  // line breaks
  html = html.replace(/\n\n/g, '</p><p class="chat-p">').replace(/\n/g, '<br>');
  return `<p class="chat-p">${html}</p>`;
}

// ─── Search ──────────────────────────────────────────────────────────────────

let _searchPending = false;
let _currentSearchQuery = '';
let _currentSearchPage = 0;
const _resultsPerPage = 10;

export async function doSearch(page = 0) {
  if (_searchPending) return;        // prevent double-call
  const searchInput = document.getElementById('searchInput');
  if (!searchInput) return;

  const query = searchInput.value.trim();
  if (!query) {
    showToast('Vui lòng nhập từ khóa', 'info');
    return;
  }

  // Reset page if query changed
  if (query !== _currentSearchQuery) {
    _currentSearchQuery = query;
    _currentSearchPage = 0;
  } else {
    _currentSearchPage = page;
  }

  _searchPending = true;
  const searchBtn = document.getElementById('searchBtn');
  if (searchBtn) searchBtn.disabled = true;

  try {
    const response = await authFetch(`${API}/search`, {
      method: 'POST',
      body: JSON.stringify({ 
        query: _currentSearchQuery, 
        limit: _resultsPerPage,
        offset: _currentSearchPage * _resultsPerPage
      }),
    });
    if (!response.ok) throw new Error('Tìm kiếm thất bại');
    const data = await response.json();
    renderSearchResults(Array.isArray(data) ? data : (data.results || []));
  } catch (e) {
    showToast(`Lỗi: ${e.message}`, 'error');
  } finally {
    _searchPending = false;
    if (searchBtn) searchBtn.disabled = false;
  }
}

function renderSearchResults(results) {
  const container = document.getElementById('searchResults');
  if (!container) return;

  container.innerHTML = '';
  if (!results || results.length === 0) {
    if (_currentSearchPage > 0) {
        container.innerHTML = `
            <div class="search-empty">Không còn kết quả nào khác</div>
            <div class="search-pagination">
                <button class="pager-btn" onclick="doSearch(${_currentSearchPage - 1})">← Trang trước</button>
            </div>
        `;
    } else {
        container.innerHTML = '<div class="search-empty">Không tìm thấy kết quả</div>';
    }
    return;
  }

  const grid = document.createElement('div');
  grid.className = 'search-results-grid';
  
  results.forEach(result => {
    const item = document.createElement('div');
    item.className = 'kp-result-card';
    const score = result.score != null ? Math.round(result.score * 100) : null;
    const docId = result.document_id || result.id || result.source_id || '';
    const docTitle = result.title || 'Untitled';

    item.innerHTML = `
      <div class="kp-result-header">
        <span class="kp-result-title">${escapeHtml(docTitle)}</span>
        <div class="kp-result-actions">
          ${score != null ? `<span class="kp-result-score">${score}%</span>` : ''}
          <button class="kp-pin-btn" onclick="addToBasket('${escapeHtml(docId)}', '${escapeHtml(docTitle)}')" title="Thêm vào giỏ">📌</button>
        </div>
      </div>
      <div class="kp-result-snippet">${escapeHtml((result.content || result.snippet || '').substring(0, 300))}</div>
      <div class="kp-result-meta">
        <span class="kp-result-badge">${escapeHtml(result.source || 'Unknown')}</span>
        ${result.url ? `<a class="kp-result-url" href="${escapeHtml(result.url)}" target="_blank" rel="noopener">Mở ↗</a>` : ''}
      </div>`;
    grid.appendChild(item);
  });
  
  container.appendChild(grid);

  // Pagination UI
  const pager = document.createElement('div');
  pager.className = 'search-pagination';
  
  const prevBtn = document.createElement('button');
  prevBtn.className = 'pager-btn';
  prevBtn.textContent = '← Trang trước';
  prevBtn.disabled = _currentSearchPage === 0;
  prevBtn.onclick = () => doSearch(_currentSearchPage - 1);
  
  const pageInfo = document.createElement('span');
  pageInfo.className = 'pager-info';
  pageInfo.textContent = `Trang ${_currentSearchPage + 1}`;
  
  const nextBtn = document.createElement('button');
  nextBtn.className = 'pager-btn';
  nextBtn.textContent = 'Trang sau →';
  nextBtn.disabled = results.length < _resultsPerPage;
  nextBtn.onclick = () => doSearch(_currentSearchPage + 1);
  
  pager.appendChild(prevBtn);
  pager.appendChild(pageInfo);
  pager.appendChild(nextBtn);
  
  container.appendChild(pager);
}

// ─── History (stub) ──────────────────────────────────────────────────────────

export function renderHistory() {
  const c = document.getElementById('chatMessages');
  if (!c) return;
  showToast('Lịch sử chat đang được phát triển', 'info');
}
