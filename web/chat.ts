import { API, authFetch } from './client';
import { Config } from './config';
import { ChatMessage, AskJobResponse, JobStatusResponse, AskResponse } from './models';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { escapeHtml } from './ui';

export class ChatModule {
    private container: HTMLElement | null;
    private input: HTMLInputElement | HTMLTextAreaElement | null;
    private sendBtn: HTMLButtonElement | null;
    private modelSelector: HTMLSelectElement | null = null;
    private currentSessionId: string | null = null;
    private initialized: boolean = false;

    public init(): void {
        // Re-bind elements in case of page transition (Navigo doesn't destroy the container usually)
        this.container = document.getElementById('chatMessages');
        this.input = document.getElementById('chatInput') as HTMLInputElement | HTMLTextAreaElement | null;
        this.sendBtn = document.getElementById('sendBtn') as HTMLButtonElement | null;
        this.modelSelector = document.getElementById('modelSelector') as HTMLSelectElement | null;

        if (!this.initialized) {
            this.initEvents();
            this.initialized = true;
        }
        
        this.loadModels();
    }

    constructor(containerId: string, inputId: string, sendBtnId: string) {
        this.container = document.getElementById(containerId);
        this.input = document.getElementById(inputId) as HTMLInputElement | HTMLTextAreaElement | null;
        this.sendBtn = document.getElementById(sendBtnId) as HTMLButtonElement | null;
        this.modelSelector = document.getElementById('modelSelector') as HTMLSelectElement | null;

        // Note: Global initApp will call init() via router immediately if we are on /chat
        // No need to call initEvents here.
    }

    private initEvents(): void {
        if (this.sendBtn) {
            this.sendBtn.addEventListener('click', () => this.sendMessage());
        }
        document.getElementById('newChatBtn')?.addEventListener('click', () => this.startNewChat());
        
        // Use event delegation for suggestions since they might be in a partial
        document.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            if (target.classList.contains('suggestion-chip')) {
                this.useSuggestion(target);
            }
            
            // Feedback Buttons
            const feedbackBtn = target.closest('.chat-feedback-btn');
            if (feedbackBtn) {
                const queryId = (feedbackBtn as HTMLElement).dataset.queryId;
                const isPositive = (feedbackBtn as HTMLElement).dataset.type === 'positive';
                if (queryId) {
                    this.sendFeedback(feedbackBtn as HTMLElement, queryId, isPositive);
                }
            }
        });

        if (this.input) {
            this.input.addEventListener('input', () => this.autoResize());
            this.input.addEventListener('keypress', (e: Event) => {
                if ((e as KeyboardEvent).key === 'Enter' && !(e as KeyboardEvent).shiftKey) {
                    (e as KeyboardEvent).preventDefault();
                    this.sendMessage();
                }
            });
        }
        
        document.addEventListener('kp-switch-chat-session', async (e: Event) => {
            const detail = (e as CustomEvent).detail;
            this.currentSessionId = detail;
            if (this.container) this.container.innerHTML = '';
            
            const emptyState = document.getElementById('emptyState');
            if (emptyState) emptyState.style.display = 'none';
            
            this.setLoading(true);
            try {
                const res = await authFetch(`${API}/history/sessions/${detail}`);
                if (!res.ok) throw new Error('Failed to fetch session history');
                const data = await res.json();
                
                if (data.messages && data.messages.length > 0) {
                    data.messages.forEach((m: any) => this.appendMessage(m));
                } else {
                    this.appendMessage({ id: 'sys', role: 'system', content: `Đã kết nối lại hội thoại. Không có tin nhắn nào.`, created_at: new Date().toISOString() });
                }
            } catch (err) {
                this.appendMessage({ id: 'sys', role: 'system', content: `⚠️ Lỗi khi tải lịch sử hội thoại.`, created_at: new Date().toISOString() });
            } finally {
                this.setLoading(false);
            }
        });
    }

    private autoResize(): void {
        if (!this.input) return;
        this.input.style.height = 'auto';
        this.input.style.height = Math.min(this.input.scrollHeight, 180) + 'px';
        if (this.container) this.container.scrollTop = this.container.scrollHeight;
    }

    private useSuggestion(el: HTMLElement): void {
        if (!this.input || !el) return;
        this.input.value = el.textContent?.trim() || '';
        this.autoResize();
        this.input.focus();
        this.sendMessage();
    }

    private async loadModels(): Promise<void> {
        if (!this.modelSelector) return;
        
        try {
            const res = await authFetch(`${API}/models`);
            if (!res.ok) throw new Error('Failed to fetch models');
            const models = await res.json();
            
            this.modelSelector.innerHTML = '';
            
            // Add a "Auto" option or Default indicator
            models.forEach((m: any) => {
                const opt = document.createElement('option');
                opt.value = m.id;
                opt.textContent = `${m.name} (${m.provider})`;
                if (m.is_default) {
                    opt.selected = true;
                    opt.textContent += ' - Default';
                }
                this.modelSelector!.appendChild(opt);
            });
            
            if (models.length === 0) {
                this.modelSelector.innerHTML = '<option value="">No models available</option>';
            }
        } catch (err) {
            console.error('Error loading models:', err);
            if (this.modelSelector) {
                this.modelSelector.innerHTML = '<option value="">Lỗi tải models</option>';
            }
        }
    }

    private startNewChat(): void {
        this.currentSessionId = null;
        if (this.container) {
            this.container.innerHTML = '';
        }
        const emptyState = document.getElementById('emptyState');
        if (emptyState) {
            emptyState.style.display = 'flex';
            const titleEl = emptyState.querySelector('.empty-title') as HTMLElement;
            if (titleEl) {
                titleEl.style.animation = 'none';
                void (titleEl as any).offsetWidth; 
                titleEl.style.animation = 'fadeUp 0.5s cubic-bezier(0.16, 1, 0.3, 1) forwards';
            }
        }
        if (this.input) {
            this.input.value = '';
            this.autoResize();
            this.input.focus();
        }
    }

    public async sendMessage(content?: string): Promise<void> {
        const text = content || this.input?.value.trim();
        if (!text) return;

        if (this.input) this.input.value = '';
        
        // Render tin nhắn của User
        this.appendMessage({
            id: Date.now().toString(),
            role: 'user',
            content: text,
            created_at: new Date().toISOString()
        });

        this.setLoading(true);

        const thinkId = 'think-' + Date.now();
        this.appendThinking(thinkId);

        try {
            const modelId = this.modelSelector?.value || undefined;
            
            let response = await authFetch(`${API}/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    question: text, 
                    session_id: this.currentSessionId,
                    llm_model_id: modelId
                })
            });

            // Tự động retry nếu session_id hết hạn trên backend
            if (response.status === 404) {
                this.currentSessionId = null;
                response = await authFetch(`${API}/ask`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ question: text, session_id: null })
                });
            }

            if (!response.ok) throw new Error(`Lỗi HTTP ${response.status}`);
            const jobData = await response.json() as AskJobResponse;
            if (jobData.session_id) this.currentSessionId = jobData.session_id;

            await this.pollJobStatus(jobData.job_id, thinkId);

        } catch (err) {
            const error = err as Error;
            this.removeThinking(thinkId);
            this.appendMessage({
                id: Date.now().toString(),
                role: 'system',
                content: `⚠️ Lỗi: ${error.message}`,
                created_at: new Date().toISOString()
            });
        } finally {
            this.setLoading(false);
        }
    }

    private async pollJobStatus(jobId: string, thinkId: string): Promise<void> {
        const pollInterval = Config.CHAT_POLLING_INTERVAL_MS; // Giảm xuống 1s để mượt hơn
        let attempts = 0;
        const maxAttempts = Config.MAX_POLL_ATTEMPTS; 

        while (attempts < maxAttempts) {
            try {
                const resp = await authFetch(`${API}/ask/status/${jobId}`);
                if (!resp.ok) throw new Error('Lỗi lấy trạng thái');
                const data = await resp.json() as JobStatusResponse;
                
                const result = data.result as any;
                const partialAnswer = result?.answer || '';
                this.updateThinkingStatus(thinkId, data.thoughts || [], partialAnswer, result);

                if (data.status === 'completed') {
                    this.removeThinking(thinkId);
                    const result = data.result as AskResponse;
                    const ans = typeof result === 'string' ? result : (result?.answer || '');
                    this.appendMessage({
                        id: data.job_id || Date.now().toString(),
                        role: 'assistant',
                        content: ans,
                        agent_plan: result?.agent_plan,
                        sources: result?.sources,
                        rewritten_query: result?.rewritten_query,
                        created_at: new Date().toISOString()
                    });
                    document.dispatchEvent(new CustomEvent('kp-refresh-history'));
                    return;
                }
                if (data.status === 'failed') {
                    this.removeThinking(thinkId);
                    throw new Error(data.error || 'Worker xử lý AI thất bại');
                }
            } catch (err) {
                console.error('Polling error:', err);
            }
            await new Promise(r => setTimeout(r, pollInterval));
            attempts++;
        }
        this.removeThinking(thinkId);
        throw new Error('Hết thời gian chờ phản hồi (Timeout)');
    }

    private appendThinking(id: string): void {
        if (!this.container) return;
        const div = document.createElement('div');
        div.className = 'chat-message assistant';
        div.id = id;
        div.innerHTML = `
            <div class="chat-avatar chat-avatar-ai">K</div>
            <div style="flex:1">
                <div class="chat-bubble chat-bubble-ai">
                    <div class="message-content">
                        <div class="chat-thinking" style="display:flex;align-items:center;gap:8px;padding:4px 0">
                            <span class="thinking-dot"></span>
                            <span class="thinking-dot"></span>
                            <span class="thinking-dot"></span>
                            <span class="thinking-text">Đang suy nghĩ...</span>
                        </div>
                        <div class="thinking-stepper" style="margin-top:8px; font-size:0.85em;"></div>
                        <div class="partial-answer markdown-body" style="opacity:0.9;"></div>
                    </div>
                </div>
            </div>
        `;
        this.container.appendChild(div);
        this.container.scrollTop = this.container.scrollHeight;
    }

    private removeThinking(id: string): void { document.getElementById(id)?.remove(); }

    private updateThinkingStatus(id: string, thoughts: any[], partialAnswer: string = '', result?: any): void {
        const el = document.getElementById(id);
        if (!el) return;
        
        const stepper = el.querySelector('.thinking-stepper');
        if (stepper) {
            let planHtml = '';
            if (result?.agent_plan && result.agent_plan.length > 0) {
                const steps = result.agent_plan.map((p: any) => `
                    <li class="thinking-step">
                        <div class="step-number">${p.step}</div>
                        <div class="step-body">
                            <div class="step-reason">${escapeHtml(p.reason)}</div>
                            <div class="step-query">${escapeHtml(p.query)}</div>
                        </div>
                    </li>
                `).join('');
                
                const expandedQuery = result.rewritten_query ? `
                    <div class="rewritten-query-box">
                        <span class="rewritten-query-label">Expanded Query (AI):</span>
                        <span class="rewritten-query-text">"${escapeHtml(result.rewritten_query)}"</span>
                    </div>
                ` : '';

                planHtml = `
                    <div class="chat-thinking-plan" style="margin-top: 10px; opacity: 1; pointer-events: auto;">
                        <div class="thinking-content">
                            ${expandedQuery}
                            <ul class="thinking-steps">${steps}</ul>
                        </div>
                    </div>
                `;
            }

            let thoughtsHtml = '';
            if (thoughts.length > 0) {
                thoughts.forEach((t, i) => {
                    const text = (typeof t === 'string' ? t : t.thought) || '';
                    const isLast = i === thoughts.length - 1 && !partialAnswer;
                    thoughtsHtml += `
                        <div class="thinking-step-live ${isLast ? 'active' : 'done'}">
                            <span class="thinking-step-icon">${isLast ? '⚙️' : '✓'}</span>
                            <span>${escapeHtml(text)}</span>
                        </div>
                    `;
                });
            }
            
            stepper.innerHTML = `
                ${planHtml}
                <div style="margin-top: 12px; border-top: 1px solid var(--border); padding-top: 8px;">
                    <div style="font-size: 10px; color: var(--text-dim); margin-bottom: 6px; text-transform: uppercase; font-weight: 800;">Real-time Log:</div>
                    ${thoughtsHtml}
                </div>
            `;
        }

        const answerDiv = el.querySelector('.partial-answer') as HTMLElement;
        if (answerDiv && partialAnswer) {
            const currentLen = partialAnswer.length;
            const lastLen = parseInt(answerDiv.dataset.lastLen || '0');
            
            // Chỉ render lại nếu nội dung tăng thêm đáng kể hoặc là lần đầu
            if (currentLen > lastLen || lastLen === 0) {
                answerDiv.innerHTML = this.formatAnswer(partialAnswer);
                answerDiv.dataset.lastLen = currentLen.toString();
                // Cuộn xuống nhẹ nhàng
                if (this.container) {
                    const isAtBottom = (this.container.scrollHeight - this.container.scrollTop - this.container.clientHeight) < 100;
                    if (isAtBottom) {
                        this.container.scrollTop = this.container.scrollHeight;
                    }
                }
            }
        }

        // Show sources if available even during partial answer
        if (result?.sources && result.sources.length > 0) {
            let sourcesContainer = el.querySelector('.chat-sources-container');
            if (!sourcesContainer) {
                sourcesContainer = document.createElement('div');
                sourcesContainer.className = 'chat-sources-container';
                el.querySelector('.message-content')?.appendChild(sourcesContainer);
            }
            
            const cards = result.sources.map((s: any) => {
                const sourceName = (s.source || 'document').toLowerCase();
                let score = s.score ? Math.round(s.score * 100) : 0;
                if (score > 100) score = 100;
                return `
                    <a href="${s.url || '#'}" target="_blank" class="source-card">
                        <div class="source-header">
                            <span class="source-type-tag">${sourceName}</span>
                            ${score > 0 ? `<span class="source-score-badge">${score}% Match</span>` : ''}
                        </div>
                        <div class="source-title">${escapeHtml(s.title || 'Untitled Document')}</div>
                    </a>
                `;
            }).join('');

            sourcesContainer.innerHTML = `
                <div class="sources-label">📚 Related Sources</div>
                <div class="sources-grid">${cards}</div>
            `;
        }
    }

    private formatAnswer(content: string): string {
        try {
            const rawHtml = marked.parse(content) as string;
            return DOMPurify.sanitize(rawHtml);
        } catch (e) {
            return escapeHtml(content);
        }
    }

    private appendMessage(msg: ChatMessage): void {
        if (!this.container) return;

        const msgEl = document.createElement('div');
        msgEl.className = `chat-message ${msg.role}`;
        
        const timeStr = msg.created_at ? new Date(msg.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' }) : '';
        
        let html = '';
        if (msg.role === 'assistant') {
            const safeContent = this.formatAnswer(msg.content);

            // 1. Thinking Plan (if available)
            let planHtml = '';
            if (msg.agent_plan && msg.agent_plan.length > 0) {
                const steps = msg.agent_plan.map(p => `
                    <li class="thinking-step">
                        <div class="step-number">${p.step}</div>
                        <div class="step-body">
                            <div class="step-reason">${escapeHtml(p.reason)}</div>
                            <div class="step-query">${escapeHtml(p.query)}</div>
                        </div>
                    </li>
                `).join('');

                const expandedQuery = msg.rewritten_query ? `
                    <div class="rewritten-query-box">
                        <span class="rewritten-query-label">Expanded Query (AI):</span>
                        <span class="rewritten-query-text">"${escapeHtml(msg.rewritten_query)}"</span>
                    </div>
                ` : '';
                
                planHtml = `
                    <details class="chat-thinking-plan">
                        <summary>View Thinking Process (${msg.agent_plan.length} steps)</summary>
                        <div class="thinking-content">
                            ${expandedQuery}
                            <ul class="thinking-steps">${steps}</ul>
                        </div>
                    </details>
                `;
            }

            // 2. Sources (if available)
            let sourcesHtml = '';
            if (msg.sources && msg.sources.length > 0) {
                const cards = msg.sources.map(s => {
                    const sourceName = (s.source || 'document').toLowerCase();
                    let score = s.score ? Math.round(s.score * 100) : 0;
                    if (score > 100) score = 100; // Cap at 100% for cleaner UI
                    
                    return `
                        <a href="${s.url || '#'}" target="_blank" class="source-card">
                            <div class="source-header">
                                <span class="source-type-tag">${sourceName}</span>
                                ${score > 0 ? `<span class="source-score-badge">${score}% Match</span>` : ''}
                            </div>
                            <div class="source-title">${escapeHtml(s.title || 'Untitled Document')}</div>
                            <div class="source-footer">
                                <span>📄 ${escapeHtml(s.author || 'System')}</span>
                            </div>
                        </a>
                    `;
                }).join('');

                sourcesHtml = `
                    <div class="chat-sources-container">
                        <div class="sources-label">📚 Related Sources</div>
                        <div class="sources-grid">${cards}</div>
                    </div>
                `;
            }

            html = `
                <div class="chat-avatar chat-avatar-ai">K</div>
                <div style="flex:1; min-width:0">
                    <div class="chat-bubble chat-bubble-ai">
                        <div class="message-content">
                            ${planHtml}
                            <div class="chat-answer-text">${safeContent}</div>
                            ${sourcesHtml}
                        </div>
                    </div>
                    <div class="chat-msg-footer">
                        <span class="chat-timestamp">${timeStr}</span>
                        <div class="chat-feedback-group" style="margin-left: auto; display: flex; gap: 4px;">
                            ${msg.query_id ? `
                                <button class="chat-feedback-btn" data-query-id="${msg.query_id}" data-type="positive" title="Hữu ích">👍</button>
                                <button class="chat-feedback-btn" data-query-id="${msg.query_id}" data-type="negative" title="Không hữu ích">👎</button>
                            ` : ''}
                        </div>
                        <button class="chat-copy-btn" title="Copy">📋 Copy</button>
                    </div>
                </div>
            `;
        } else if (msg.role === 'system') {
            html = `
                <div class="chat-bubble" style="background:var(--bg3);border:1px solid var(--border);font-size:13px;color:var(--text-muted)">
                    <div class="message-content">${escapeHtml(msg.content)}</div>
                </div>
            `;
        } else {
            const safeContent = escapeHtml(msg.content);
            html = `
                <div style="flex:1; min-width:0; display:flex; flex-direction:column; align-items:flex-end">
                    <div class="chat-bubble chat-bubble-user">
                        <div class="message-content">${safeContent}</div>
                    </div>
                    <div class="chat-msg-footer" style="justify-content:flex-end">
                        <span class="chat-timestamp">${timeStr}</span>
                    </div>
                </div>
                <div class="chat-avatar chat-avatar-user">👤</div>
            `;
        }
        
        msgEl.innerHTML = html;
        
        // Bind copy button
        const copyBtn = msgEl.querySelector('.chat-copy-btn');
        if (copyBtn) {
            copyBtn.addEventListener('click', () => {
                navigator.clipboard.writeText(msg.content).then(() => {
                    (copyBtn as HTMLElement).textContent = '✅ Copied!';
                    setTimeout(() => { (copyBtn as HTMLElement).textContent = '📋 Copy'; }, 1500);
                });
            });
        }
        
        this.container.appendChild(msgEl);
        this.container.scrollTop = this.container.scrollHeight;
    }

    private setLoading(isLoading: boolean): void {
        if (this.sendBtn) this.sendBtn.disabled = isLoading;
        if (this.input) this.input.disabled = isLoading;
    }
    private async sendFeedback(btn: HTMLElement, queryId: string, isPositive: boolean): Promise<void> {
        // Visual Feedback
        const group = btn.closest('.chat-feedback-group');
        if (group) {
            group.querySelectorAll('.chat-feedback-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            // Disable further clicks for this message
            (group as HTMLElement).style.pointerEvents = 'none';
        }

        try {
            const res = await authFetch(`${API}/feedback/${queryId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_positive: isPositive })
            });
            if (!res.ok) throw new Error('Feedback failed');
            
            // Show subtle success toast or similar if needed
            console.log('Feedback submitted successfully');
        } catch (err) {
            console.error('Error submitting feedback:', err);
            btn.classList.remove('active');
            if (group) (group as HTMLElement).style.pointerEvents = 'auto';
        }
    }
}