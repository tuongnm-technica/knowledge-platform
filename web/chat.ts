import { API, authFetch } from './client';
import { ChatMessage, AskJobResponse, JobStatusResponse, AskResponse } from './models';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

export class ChatModule {
    private container: HTMLElement | null;
    private input: HTMLInputElement | HTMLTextAreaElement | null;
    private sendBtn: HTMLButtonElement | null;
    private currentSessionId: string | null = null;

    constructor(containerId: string, inputId: string, sendBtnId: string) {
        this.container = document.getElementById(containerId);
        this.input = document.getElementById(inputId) as HTMLInputElement | HTMLTextAreaElement | null;
        this.sendBtn = document.getElementById(sendBtnId) as HTMLButtonElement | null;

        this.initEvents();
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
            let response = await authFetch(`${API}/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ question: text, session_id: this.currentSessionId })
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
        const pollInterval = 1000; // Giảm xuống 1s để mượt hơn
        let attempts = 0;
        const maxAttempts = 600; 

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
            <div class="message-content">
                <div class="thinking-stepper" style="margin-bottom: 8px; font-size: 0.85em; opacity: 0.8;"></div>
                <div class="partial-answer markdown-body" style="opacity: 0.9;"></div>
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
                            <div class="step-reason">${this.escapeHtml(p.reason)}</div>
                            <div class="step-query">${this.escapeHtml(p.query)}</div>
                        </div>
                    </li>
                `).join('');
                
                const expandedQuery = result.rewritten_query ? `
                    <div class="rewritten-query-box">
                        <span class="rewritten-query-label">Expanded Query (AI):</span>
                        <span class="rewritten-query-text">"${this.escapeHtml(result.rewritten_query)}"</span>
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
                        <div class="step ${isLast ? 'active' : 'done'}" style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px;">
                            <span class="step-icon" style="width: 16px; height: 16px; display: inline-flex; align-items: center; justify-content: center; border-radius: 50%; border: 1px solid currentColor; font-size: 10px;">
                                ${isLast ? '⚙️' : '✓'}
                            </span>
                            <span style="font-size: 12px;">${this.escapeHtml(text)}</span>
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
            // Chỉ render lại nếu nội dung thực sự thay đổi chiều dài
            if (answerDiv.dataset.lastLen !== partialAnswer.length.toString()) {
                answerDiv.innerHTML = this.formatAnswer(partialAnswer);
                answerDiv.dataset.lastLen = partialAnswer.length.toString();
                // Cuộn xuống nếu có nội dung mới
                if (this.container) this.container.scrollTop = this.container.scrollHeight;
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
                const score = s.score ? Math.round(s.score * 100) : 0;
                return `
                    <a href="${s.url || '#'}" target="_blank" class="source-card">
                        <div class="source-header">
                            <span class="source-type-tag">${sourceName}</span>
                            ${score > 0 ? `<span class="source-score-badge">${score}% Match</span>` : ''}
                        </div>
                        <div class="source-title">${this.escapeHtml(s.title || 'Untitled Document')}</div>
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
            return this.escapeHtml(content);
        }
    }

    private appendMessage(msg: ChatMessage): void {
        if (!this.container) return;

        const msgEl = document.createElement('div');
        msgEl.className = `chat-message ${msg.role}`;
        
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
                            <div class="step-reason">${this.escapeHtml(p.reason)}</div>
                            <div class="step-query">${this.escapeHtml(p.query)}</div>
                        </div>
                    </li>
                `).join('');

                const expandedQuery = msg.rewritten_query ? `
                    <div class="rewritten-query-box">
                        <span class="rewritten-query-label">Expanded Query (AI):</span>
                        <span class="rewritten-query-text">"${this.escapeHtml(msg.rewritten_query)}"</span>
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
                    const score = s.score ? Math.round(s.score * 100) : 0;
                    
                    return `
                        <a href="${s.url || '#'}" target="_blank" class="source-card">
                            <div class="source-header">
                                <span class="source-type-tag">${sourceName}</span>
                                ${score > 0 ? `<span class="source-score-badge">${score}% Match</span>` : ''}
                            </div>
                            <div class="source-title">${this.escapeHtml(s.title || 'Untitled Document')}</div>
                            <div class="source-footer">
                                <span>📄 ${this.escapeHtml(s.author || 'System')}</span>
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
                <div class="chat-bubble chat-bubble-ai">
                    <div class="message-content">
                        ${planHtml}
                        <div class="chat-answer-text">${safeContent}</div>
                        ${sourcesHtml}
                    </div>
                </div>
            `;
        } else {
            const safeContent = this.escapeHtml(msg.content);
            html = `
                <div class="chat-bubble chat-bubble-user">
                    <div class="message-content">${safeContent}</div>
                </div>
            `;
        }
        
        msgEl.innerHTML = html;
        this.container.appendChild(msgEl);
        this.container.scrollTop = this.container.scrollHeight;
    }

    private setLoading(isLoading: boolean): void {
        if (this.sendBtn) this.sendBtn.disabled = isLoading;
        if (this.input) this.input.disabled = isLoading;
    }

    private escapeHtml(unsafe: string): string {
        return unsafe.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }
}