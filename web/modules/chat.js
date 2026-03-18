// Chat Module — AI chat, search, history
import { authFetch, API } from '../api/client.js';
import { showToast, escapeHtml, kpOpenModal } from '../utils/ui.js';

let _callbacks = {};
let _isSending = false;  // Race condition prevention
const TEXTAREA_MAX_HEIGHT = 180;
const MAX_QUESTION_LENGTH = 1000;

export function setChatCallbacks(callbacks) {
  _callbacks = callbacks || {};
}

// ─── Resize textarea ────────────────────────────────────────────────────────

export function autoResize(el) {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, TEXTAREA_MAX_HEIGHT) + 'px';
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
  // Prevent race condition - only allow one message at a time
  if (_isSending) {
    console.warn('Message already sending, ignoring duplicate');
    return;
  }

  const input   = document.getElementById('chatInput');
  const sendBtn = document.getElementById('sendBtn');
  if (!input) return;

  const question = input.value.trim();
  if (!question) return;
  if (question.length < 3) {
    showToast('Câu hỏi phải có ít nhất 3 ký tự', 'warning');
    return;
  }
  if (question.length > MAX_QUESTION_LENGTH) {
    showToast(`Câu hỏi quá dài (tối đa ${MAX_QUESTION_LENGTH} ký tự)`, 'warning');
    return;
  }

  // Set flag BEFORE any async operation
  _isSending = true;

  try {
    // Clear UI
    input.value = '';
    autoResize(input);

    const emptyState = document.getElementById('emptyState');
    if (emptyState) emptyState.style.display = 'none';

    // Append user bubble
    const userBubble = document.createElement('div');
    userBubble.textContent = question;
    appendBubble('user', userBubble);

    // Show thinking indicator
    const thinkId = 'think-' + Date.now();
    appendThinking(thinkId);

    if (sendBtn) sendBtn.disabled = true;

    // Handle different HTTP status codes
    const resp = await authFetch(`${API}/ask`, {
      method: 'POST',
      body: JSON.stringify({ question }),
    });

    removeThinking(thinkId);

    // Determine action based on status
    if (resp.status === 504) {
      // Gateway timeout - LLM is slow
      showToast('LLM service slow, retrying in 5s...', 'warning');
      setTimeout(() => {
        _isSending = false;
        sendMessage();
      }, 5000);
      return;
    }

    if (resp.status === 503) {
      // Service unavailable
      showToast('LLM service unavailable, try again in 10 minutes', 'error');
      const errDiv = document.createElement('div');
      errDiv.textContent = '⛔ Dịch vụ LLM tạm thời không khả dụng. Vui lòng thử lại sau.';
      appendBubble('ai', errDiv);
      scrollChatBottom();
      return;
    }

    if (!resp.ok) {
      const errData = await resp.json().catch(() => ({}));
      let msg = errData.detail || `Lỗi hệ thống (${resp.status})`;
      if (Array.isArray(msg)) {
        msg = msg.map(m => (typeof m === 'string' ? m : (m.msg || JSON.stringify(m)))).join(', ');
      } else if (typeof msg === 'object') {
        msg = msg.message || JSON.stringify(msg);
      }
      throw new Error(String(msg));
    }

    const data = await resp.json();
    const answerHtml = formatAnswer(data);
    appendBubble('ai', answerHtml, data);
    scrollChatBottom();
    input.focus();

  } catch (e) {
    console.error('Chat error:', e);
    let errorMsg = 'Unknown error';
    if (typeof e === 'string') {
      errorMsg = e;
    } else if (e instanceof Error) {
      errorMsg = e.message;
    } else {
      try {
        errorMsg = JSON.stringify(e);
      } catch (jsonErr) {
        errorMsg = String(e);
      }
    }
    if (errorMsg === '[object Object]') {
      errorMsg = 'Lỗi không xác định (hãy kiểm tra console)';
    }
    const errorDiv = document.createElement('div');
    errorDiv.className = 'chat-error';
    errorDiv.textContent = `⚠️ Lỗi: ${errorMsg}`;
    appendBubble('ai', errorDiv);
    scrollChatBottom();
  } finally {
    _isSending = false;
    if (sendBtn) sendBtn.disabled = false;
    input.focus();
  }
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function appendBubble(role, element, data) {
  const container = document.getElementById('chatMessages');
  if (!container) return;

  const wrap = document.createElement('div');
  wrap.className = `chat-message chat-message-${role}`;

  const bubble = document.createElement('div');
  bubble.className = `chat-bubble chat-bubble-${role}`;

  // Handle both string and DOM element
  if (typeof element === 'string') {
    // For backward compatibility with plain text
    bubble.textContent = element;
  } else if (element instanceof HTMLElement) {
    bubble.appendChild(element);
  }

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
  if (!data) return document.createElement('div');
  
  const container = document.createElement('div');
  
  // 1. Format answer text safely
  const answerDiv = document.createElement('div');
  answerDiv.className = 'chat-answer-text';
  
  try {
    // Check if marked.js is available for markdown parsing
    if (typeof marked !== 'undefined' && data.answer) {
      // Use marked.js for safe markdown parsing 
      const markdownHtml = marked.parse(data.answer, {
        breaks: true,
        gfm: true,
      });
      // Additional XSS protection: strip script tags and event handlers
      const sanitized = markdownHtml
        .replace(/<script[^>]*>.*?<\/script>/gi, '')
        .replace(/on\w+\s*=/gi, 'disabled_');
      answerDiv.innerHTML = sanitized;
    } else {
      // Fallback to plain text
      answerDiv.textContent = data.answer || '';
    }
  } catch (e) {
    console.warn('Markdown parsing failed, using plain text', e);
    answerDiv.textContent = data.answer || '';
  }
  
  container.appendChild(answerDiv);
  
  // 2. Format sources safely using DOM API (NO innerHTML!)
  const srcs = Array.isArray(data.sources) ? data.sources.slice(0, 6) : [];
  if (srcs.length > 0) {
    const sourcesDiv = document.createElement('div');
    sourcesDiv.className = 'chat-sources';
    
    srcs.forEach(s => {
      const chipWrapper = document.createElement('div');
      chipWrapper.className = 'chat-source-chip-wrapper';
      
      // Create link safely
      const link = document.createElement('a');
      link.className = 'chat-source-chip';
      link.target = '_blank';
      link.rel = 'noopener';
      
      // Validate URL before setting - prevent javascript: protocol
      let safeUrl = '#';
      const urlStr = s.url || '';
      try {
        const parsed = new URL(urlStr, window.location.href);
        if (['http:', 'https:'].includes(parsed.protocol)) {
          safeUrl = urlStr;
        }
      } catch (e) {
        // Invalid URL, keep default
      }
      link.href = safeUrl;
      
      // Add icon and title
      const icon = document.createElement('span');
      icon.className = 'chat-source-icon';
      icon.textContent = '📄';
      
      const title = document.createElement('span');
      title.className = 'chat-source-title';
      title.textContent = s.title || s.document_id || 'Source';
      
      link.appendChild(icon);
      link.appendChild(title);
      
      // Add score if available
      if (s.score != null) {
        const score = document.createElement('span');
        score.className = 'chat-source-score';
        score.textContent = Math.round(s.score * 100) + '%';
        link.appendChild(score);
      }
      
      // Create pin button with event listener (NOT onclick string!)
      const pinBtn = document.createElement('button');
      pinBtn.className = 'chat-source-pin';
      pinBtn.title = 'Ghim ngữ cảnh';
      pinBtn.textContent = '📌';
      const docId = s.document_id || s.source_id || '';
      const docTitle = s.title || 'Source';
      pinBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (typeof window.addToBasket === 'function') {
          window.addToBasket(docId, docTitle);
        } else {
          showToast('Tính năng giỏ tài liệu (Basket) chưa sẵn sàng', 'warning');
        }
      });
      
      chipWrapper.appendChild(link);
      chipWrapper.appendChild(pinBtn);
      sourcesDiv.appendChild(chipWrapper);
    });
    
    container.appendChild(sourcesDiv);
  }
  
  return container;
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

// Note: markdownToHtml is deprecated, use marked.js in formatAnswer() instead
// This is kept for backward compatibility if needed
function markdownToHtml(md) {
  console.warn('markdownToHtml is deprecated, use marked.js in formatAnswer');
  if (!md) return '';
  // Escape first to prevent XSS
  let html = escapeHtml(md);
  // Simple safe markdown: just preserve basic formatting
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // line breaks
  html = html.replace(/\n/g, '<br>');
  return html;
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
      const docTitle = result.title || result.filename || 'Untitled Document';
      
      // Clean snippet from technical markers like [[IMAGE_URL:...]] or mermaid tags
      let snippet = (result.content || result.snippet || '').substring(0, 300);
      snippet = snippet.replace(/\[\[IMAGE_URL:[^\]]+\]\]/g, '[Image]')
                        .replace(/```mermaid[\s\S]*?```/g, '[Diagram]')
                        .trim();

      const safeDocId = escapeHtml(docId).replace(/'/g, "\\'");
      const safeDocTitle = escapeHtml(docTitle).replace(/'/g, "\\'");
      const docAuthor = result.author ? `Bởi: ${escapeHtml(result.author)}` : '';

      item.innerHTML = `
        <div class="kp-result-header">
          <span class="kp-result-title">${escapeHtml(docTitle)}</span>
          <div class="kp-result-actions">
            ${score != null ? `<span class="kp-result-score">${score}%</span>` : ''}
            <button class="kp-pin-btn" onclick="if(window.addToBasket) window.addToBasket('${safeDocId}', '${safeDocTitle}')" title="Thêm vào giỏ">📌</button>
          </div>
        </div>
        <div class="kp-result-snippet">${escapeHtml(snippet)}</div>
        <div class="kp-result-meta">
          <span class="kp-result-badge">${escapeHtml(result.source || result.source_type || 'Internal source')}</span>
          ${docAuthor ? `<span style="font-size: 11px; color: var(--text-dim); margin-right: auto;">${docAuthor}</span>` : ''}
          <button class="secondary-btn mini" onclick="window.viewDocument('${safeDocId}')">📄 Chi tiết</button>
          ${result.url ? `<a class="kp-result-url" style="margin-left:8px;" href="${escapeHtml(result.url)}" target="_blank" rel="noopener">Mở ↗</a>` : ''}
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

// ─── Document Details Modal ──────────────────────────────────────────────────

window.viewDocument = async function(docId) {
  try {
    const res = await authFetch(`${API}/search/${docId}`);
    if (!res.ok) throw new Error('Không thể tải nội dung tài liệu (hoặc bạn không có quyền truy cập).');
    const doc = await res.json();

    let htmlContent = '';
    if (typeof marked !== 'undefined') {
      htmlContent = marked.parse(doc.content || '');
    } else {
      htmlContent = escapeHtml(doc.content || '').replace(/\n/g, '<br>');
    }

    const body = document.createElement('div');
    body.innerHTML = `
      <div style="margin-bottom: 16px; font-size: 13px; color: var(--text-dim); display: flex; gap: 12px; flex-wrap: wrap;">
        <span class="kp-result-badge">${escapeHtml(doc.source || 'N/A')}</span>
        ${doc.author ? `<span>👤 ${escapeHtml(doc.author)}</span>` : ''}
        ${doc.url ? `<a href="${escapeHtml(doc.url)}" target="_blank" style="color: var(--accent);">Mở URL gốc ↗</a>` : ''}
      </div>
      <div style="max-height: 60vh; overflow-y: auto; line-height: 1.6; color: var(--text); padding-right: 8px;">
        ${htmlContent}
      </div>
    `;

    kpOpenModal({
      title: doc.title || 'Chi tiết tài liệu',
      content: body,
      okText: 'Đóng',
      cancelText: null
    });
  } catch (e) {
    showToast(e.message, 'error');
  }
};

// ─── History (stub) ──────────────────────────────────────────────────────────

export function renderHistory() {
  const c = document.getElementById('chatMessages');
  if (!c) return;
  showToast('Lịch sử chat đang được phát triển', 'info');
}
