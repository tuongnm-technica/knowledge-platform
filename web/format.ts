export function formatTime(dateStr: string | number | Date | null | undefined): string {
    if (!dateStr) return 'N/A';
    try {
        return new Date(dateStr).toLocaleString('vi-VN', { 
            day: '2-digit', month: '2-digit', year: 'numeric', 
            hour: '2-digit', minute: '2-digit' 
        });
    } catch {
        return String(dateStr);
    }
}

export function safeHostname(urlStr: string): string {
    if (!urlStr) return '';
    try {
        const url = new URL(urlStr);
        return url.hostname;
    } catch {
        return urlStr;
    }
}

export interface Thought {
    thought?: string;
}

export function parseThinking(thoughts: Thought[]): string {
    if (!thoughts || thoughts.length === 0) return '';
    return thoughts.map(t => t.thought || '').join('\n');
}

export function getSourceIcon(sourceType: string): string {
    const map: Record<string, string> = { 
        confluence: '📘', jira: '🎫', slack: '💬', 
        github: '🐙', notion: '📝', file_server: '📁' 
    };
    return map[sourceType?.toLowerCase()] || '🔗';
}

export function getBadgeClass(status: string): string {
    if (!status) return 'neutral';
    const s = status.toLowerCase();
    if (['active', 'ok', 'success', 'completed'].includes(s)) return 'success';
    if (['error', 'failed', 'rejected'].includes(s)) return 'danger';
    if (['syncing', 'processing', 'pending'].includes(s)) return 'warning';
    return 'neutral';
}

export function formatRelevancePercent(score: number | null | undefined): string {
    if (score == null) return '';
    return `${Math.round(score * 100)}%`;
}

export function renderMarkdown(md: string): string {
    if (!md) return '';
    
    // 1. Dấu block code để không bị xử lý thẻ <br> hay <li>
    const codes: string[] = [];
    let text = md.replace(/```([\s\S]*?)```/g, (_, code) => {
        codes.push(code);
        return `__CODE_BLOCK_${codes.length - 1}__`;
    });

    // 2. Render các định dạng cơ bản
    text = text
        .replace(/### (.*)/g, '<h3>$1</h3>')
        .replace(/## (.*)/g, '<h2>$1</h2>')
        .replace(/# (.*)/g, '<h1>$1</h1>')
        .replace(/\*\*(.*)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*)\*/g, '<em>$1</em>')
        .replace(/^\- (.*)/gm, '<li>$1</li>')
        .replace(/\n\n/g, '<br><br>')
        .replace(/\n/g, '<br>');

    // 3. Trả lại code block
    codes.forEach((code, i) => {
        text = text.replace(`__CODE_BLOCK_${i}__`, `<pre><code class="code-block">${escapeHtml(code)}</code></pre>`);
    });

    return text;
}

function escapeHtml(str: string): string {
    return str.replace(/[&<>"']/g, m => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[m] || m));
}