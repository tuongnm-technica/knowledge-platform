import { API, authFetch } from './client';
import { ChatMessage } from './models';
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
        document.querySelectorAll('#chatSuggestions .suggestion-chip').forEach(chip => {
            chip.addEventListener('click', (e) => this.useSuggestion(e.currentTarget as HTMLElement));
        });
        if (this.input) {
            this.input.addEventListener('input', () => this.autoResize());
            this.input.addEventListener('keypress', (e: KeyboardEvent) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
        }
        
        document.addEventListener('kp-switch-chat-session', (e: any) => {
            this.currentSessionId = e.detail;
            if (this.container) this.container.innerHTML = '';
            this.appendMessage({ id: 'sys', role: 'system', content: `Đã chuyển sang hội thoại: ${e.detail}. Tính năng tải tin nhắn cũ đang được backend hỗ trợ.`, created_at: new Date().toISOString() });
            const emptyState = document.getElementById('emptyState');
            if (emptyState) emptyState.style.display = 'none';
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
            Array.from(this.container.querySelectorAll('.chat-message')).forEach(msg => msg.remove());
        }
        const emptyState = document.getElementById('emptyState');
        if (emptyState) {
            emptyState.style.display = 'flex';
            const titleEl = emptyState.querySelector('.empty-title') as HTMLElement;
            if (titleEl) {
                titleEl.style.animation = 'none';
                void titleEl.offsetWidth; 
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
            const jobData = await response.json();
            if (jobData.session_id) this.currentSessionId = jobData.session_id;

            await this.pollJobStatus(jobData.job_id, thinkId);

        } catch (error: any) {
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
        const pollInterval = 1500; // 1.5 giây
        let attempts = 0;
        const maxAttempts = 120; // 3 phút

        while (attempts < maxAttempts) {
            try {
                const resp = await authFetch(`${API}/ask/status/${jobId}`);
                if (!resp.ok) throw new Error('Lỗi lấy trạng thái');
                const data = await resp.json();
                
                this.updateThinkingStatus(thinkId, data.thoughts);

                if (data.status === 'completed') {
                    this.removeThinking(thinkId);
                    const ans = typeof data.result === 'string' ? data.result : (data.result?.answer || '');
                    this.appendMessage({
                        id: data.job_id || Date.now().toString(),
                        role: 'assistant',
                        content: ans,
                        created_at: new Date().toISOString()
                    });
                    // Bắn event để main.ts hoặc History module tự hứng lấy
                    document.dispatchEvent(new CustomEvent('kp-refresh-history'));
                    return;
                }
                if (data.status === 'failed') {
                    this.removeThinking(thinkId);
                    throw new Error(data.error || 'Worker xử lý AI thất bại');
                }
            } catch (e) {
                console.error('Polling error:', e);
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
        div.innerHTML = `<div class="message-content"><span class="thinking-text" style="font-style:italic; opacity:0.7;">Đang suy nghĩ...</span></div>`;
        this.container.appendChild(div);
        this.container.scrollTop = this.container.scrollHeight;
    }
    private removeThinking(id: string): void { document.getElementById(id)?.remove(); }
    private updateThinkingStatus(id: string, thoughts: any[]): void {
        const el = document.getElementById(id);
        if (!el || !thoughts || !thoughts.length) return;
        const label = el.querySelector('.thinking-text');
        if (label) label.textContent = thoughts[thoughts.length - 1].thought || "Đang xử lý...";
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
        msgEl.className = `chat-message ${msg.role}`; // style via CSS based on role
        
        let safeContent = '';
        if (msg.role === 'assistant') {
            safeContent = this.formatAnswer(msg.content);
        } else {
            safeContent = this.escapeHtml(msg.content);
        }
        
        msgEl.innerHTML = `<div class="message-content">${safeContent}</div>`;
        
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

    private showToast(message: string, type: string): void {
        document.dispatchEvent(new CustomEvent('kp-show-toast', { 
            detail: { message, type } 
        }));
    }
}