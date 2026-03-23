import { API, authFetch } from './client';
import { SearchResult } from './models';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { kpOpenModal } from './ui';

export class SearchModule {
    private searchPending = false;
    private currentSearchQuery = '';
    private currentSearchPage = 0;
    private readonly resultsPerPage = 10;

    private searchInput: HTMLInputElement | null;
    private searchBtn: HTMLButtonElement | null;
    private resultsContainer: HTMLElement | null;

    constructor(inputId: string, btnId: string, resultsContainerId: string) {
        this.searchInput = document.getElementById(inputId) as HTMLInputElement | null;
        this.searchBtn = document.getElementById(btnId) as HTMLButtonElement | null;
        this.resultsContainer = document.getElementById(resultsContainerId);

        this.initEvents();
    }

    private initEvents(): void {
        if (this.searchBtn) {
            this.searchBtn.addEventListener('click', () => this.doSearch(0));
        }
        if (this.searchInput) {
            this.searchInput.addEventListener('keypress', (e: KeyboardEvent) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    this.doSearch(0);
                }
            });
        }
        document.addEventListener('kp-view-document', (e: Event) => {
            const detail = (e as CustomEvent).detail;
            this.viewDocument(detail.id);
        });
    }

    public async doSearch(page: number = 0): Promise<void> {
        if (this.searchPending || !this.searchInput) return;

        const query = this.searchInput.value.trim();
        if (!query) {
            this.showToast('Vui lòng nhập từ khóa', 'info');
            return;
        }

        if (query !== this.currentSearchQuery) {
            this.currentSearchQuery = query;
            this.currentSearchPage = 0;
        } else {
            this.currentSearchPage = page;
        }

        this.searchPending = true;
        if (this.searchBtn) {
            this.searchBtn.disabled = true;
            this.searchBtn.innerHTML = '<span class="spin">🔄</span> Đang tìm...';
        }
        if (this.resultsContainer && this.currentSearchPage === 0) {
            this.resultsContainer.innerHTML = `
                <div class="search-results-grid skeleton">
                    ${[1, 2, 3].map(() => `
                        <div class="kp-result-card skeleton-card">
                            <div class="skeleton-title"></div>
                            <div class="skeleton-text"></div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        try {
            const response = await authFetch(`${API}/search`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    query: this.currentSearchQuery, 
                    limit: this.resultsPerPage,
                    offset: this.currentSearchPage * this.resultsPerPage
                }),
            });
            
            if (!response.ok) throw new Error('Tìm kiếm thất bại');
            
            const data = await response.json();
            const results: SearchResult[] = Array.isArray(data) ? data : (data.results || []);
            this.renderSearchResults(results);
        } catch (err) {
            const error = err as Error;
            this.showToast(`Lỗi: ${error.message}`, 'error');
        } finally {
            this.searchPending = false;
            if (this.searchBtn) {
                this.searchBtn.disabled = false;
                this.searchBtn.textContent = 'Tìm kiếm';
            }
        }
    }

    private renderSearchResults(results: SearchResult[]): void {
        if (!this.resultsContainer) return;
        this.resultsContainer.innerHTML = '';

        if (!results || results.length === 0) {
            if (this.currentSearchPage > 0) {
                this.resultsContainer.innerHTML = `
                    <div class="search-empty">Không còn kết quả nào khác</div>
                    <div class="search-pagination">
                        <button class="pager-btn" id="kpPrevPageBtn">← Trang trước</button>
                    </div>
                `;
                document.getElementById('kpPrevPageBtn')?.addEventListener('click', () => this.doSearch(this.currentSearchPage - 1));
            } else {
                this.resultsContainer.innerHTML = `
                    <div class="search-empty" style="padding-top: 60px; display: flex; flex-direction: column; align-items: center;">
                        <div style="font-size: 40px; margin-bottom: 12px; opacity: 0.5;">📭</div>
                        <div style="color: var(--text); font-weight: 500;">Không tìm thấy kết quả nào.</div>
                    </div>`;
            }
            return;
        }

        const grid = document.createElement('div');
        grid.className = 'search-results-grid';
        
        results.forEach(result => {
            const item = document.createElement('div');
            item.className = 'kp-result-card';
            
            const score = result.score != null ? Math.round(result.score * 100) : null;
            const docId = result.document_id || '';
            const docTitle = result.title || 'Untitled Document';
            
            let snippet = (result.content || '').substring(0, 300);
            snippet = snippet.replace(/\[\[IMAGE_URL:[^\]]+\]\]/g, '[Image]')
                             .replace(/```mermaid[\s\S]*?```/g, '[Diagram]')
                             .trim();

            const docAuthor = result.author ? `👤 ${this.escapeHtml(result.author)}` : '';
            const sourceBadge = (result.source || 'internal').toLowerCase();
            const dateStr = result.updated_at ? new Date(result.updated_at).toLocaleDateString('vi-VN') : '';

            item.innerHTML = `
                <div class="kp-result-header">
                    <span class="kp-result-title">${this.escapeHtml(docTitle)}</span>
                    <div class="kp-result-actions">
                        ${score != null ? `
                            <div class="kp-result-score-wrap" title="${this.formatScoreBreakdown(result.score_breakdown)}">
                                <span class="kp-result-score">${score}% match</span>
                            </div>
                        ` : ''}
                        <button class="secondary-btn mini kp-pin-btn" title="Ghim nháp" data-doc-id="${this.escapeHtml(docId)}" data-doc-title="${this.escapeHtml(docTitle)}">📌</button>
                    </div>
                </div>
                <div class="kp-result-snippet">${this.escapeHtml(snippet)}...</div>
                <div class="kp-result-meta">
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                        <span class="kp-result-badge source-${sourceBadge}">${this.escapeHtml(result.source || 'N/A')}</span>
                        ${docAuthor ? `<span class="kp-result-author">${docAuthor}</span>` : ''}
                        ${dateStr ? `<span style="font-size: 11px; color: var(--text-muted);">🕒 ${dateStr}</span>` : ''}
                    </div>
                    <div class="kp-result-footer-actions">
                        <button class="secondary-btn mini view-doc-btn" data-doc-id="${this.escapeHtml(docId)}">📄 Xem chi tiết</button>
                        ${result.url ? `<a class="kp-result-url" href="${this.escapeHtml(result.url)}" target="_blank" rel="noopener">Link gốc ↗</a>` : ''}
                    </div>
                </div>
            `;

            item.querySelector('.kp-pin-btn')?.addEventListener('click', (e) => {
                const target = e.currentTarget as HTMLElement;
                const id = target.getAttribute('data-doc-id');
                const title = target.getAttribute('data-doc-title');
                if (id && title) {
                    document.dispatchEvent(new CustomEvent('kp-add-to-basket', { detail: { id, title } }));
                }
            });

            item.querySelector('.view-doc-btn')?.addEventListener('click', (e) => {
                const target = e.currentTarget as HTMLElement;
                const id = target.getAttribute('data-doc-id');
                if (id) this.viewDocument(id);
            });

            grid.appendChild(item);
        });

        this.resultsContainer.appendChild(grid);

        // Pagination UI
        const pager = document.createElement('div');
        pager.className = 'search-pagination';
        
        const prevBtn = document.createElement('button');
        prevBtn.className = 'secondary-btn';
        prevBtn.textContent = '← Trang trước';
        prevBtn.disabled = this.currentSearchPage === 0;
        prevBtn.addEventListener('click', () => this.doSearch(this.currentSearchPage - 1));
        
        const pageInfo = document.createElement('span');
        pageInfo.className = 'pager-info';
        pageInfo.textContent = `Trang ${this.currentSearchPage + 1}`;
        
        const nextBtn = document.createElement('button');
        nextBtn.className = 'secondary-btn';
        nextBtn.textContent = 'Trang sau →';
        nextBtn.disabled = results.length < this.resultsPerPage;
        nextBtn.addEventListener('click', () => this.doSearch(this.currentSearchPage + 1));
        
        pager.appendChild(prevBtn);
        pager.appendChild(pageInfo);
        pager.appendChild(nextBtn);
        
        this.resultsContainer.appendChild(pager);
    }

    public async viewDocument(docId: string): Promise<void> {
        try {
            const res = await authFetch(`${API}/search/${docId}`);
            if (!res.ok) throw new Error('Không thể tải nội dung tài liệu (hoặc bạn không có quyền truy cập).');
            const doc = await res.json() as SearchResult;

            let htmlContent = '';
            try {
                const rawHtml = marked.parse(doc.content || '') as string;
                htmlContent = DOMPurify.sanitize(rawHtml);
            } catch (e) {
                htmlContent = this.escapeHtml(doc.content || '').replace(/\n/g, '<br>');
            }

            const body = document.createElement('div');
            body.innerHTML = `
                <div style="margin-bottom: 16px; font-size: 13px; color: var(--text-dim); display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
                    <span class="kp-result-badge">${this.escapeHtml(doc.source || 'N/A')}</span>
                    ${doc.author ? `<span>👤 ${this.escapeHtml(doc.author)}</span>` : ''}
                    ${doc.score_breakdown ? `<span style="color: var(--success); font-weight: 600;">🎯 ${this.formatScoreBreakdown(doc.score_breakdown)}</span>` : ''}
                    ${doc.url ? `<a href="${this.escapeHtml(doc.url)}" target="_blank" style="color: var(--accent);">Mở URL gốc ↗</a>` : ''}
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
        } catch (err) {
            const error = err as Error;
            this.showToast(error.message, 'error');
        }
    }

    // --- Helpers ---
    private showToast(message: string, type: 'success' | 'error' | 'warning' | 'info'): void {
        const win = window as any;
        if (typeof win.showToast === 'function') {
            win.showToast(message, type);
        } else {
            console.warn(`[${type.toUpperCase()}] ${message}`);
        }
    }

    private formatScoreBreakdown(breakdown: any): string {
        if (!breakdown || typeof breakdown !== 'object') return '';
        const parts: string[] = [];
        if (breakdown.vector_score != null) parts.push(`Vector: ${Math.round(breakdown.vector_score * 100)}%`);
        if (breakdown.keyword_score != null) parts.push(`Từ khóa: ${Math.round(breakdown.keyword_score * 100)}%`);
        if (breakdown.rerank_score != null) parts.push(`Rerank: ${Math.round(breakdown.rerank_score * 100)}%`);
        return parts.length > 0 ? parts.join(' | ') : '';
    }

    private escapeHtml(unsafe: string): string {
        return unsafe
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }
}