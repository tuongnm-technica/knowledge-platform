import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { escapeHtml } from './ui';

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
    try {
        const raw = marked.parse(md) as string;
        return DOMPurify.sanitize(raw);
    } catch (e) {
        return escapeHtml(md);
    }
}