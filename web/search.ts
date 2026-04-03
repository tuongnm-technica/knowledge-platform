import { API, authFetch } from './client';
import { SearchResult } from './models';
import { kpOpenModal, showToast, escapeHtml } from './ui';
import { renderMarkdown } from './format';

export class SearchModule {
    private searchPending = false;
    private currentSearchQuery = '';
    private currentSearchPage = 0;
    private readonly resultsPerPage = 10;

    private searchInput: HTMLInputElement | null;
    private searchBtn: HTMLButtonElement | null;
    private resultsContainer: HTMLElement | null;
    private initialized: boolean = false;

    public init(): void {
        if (!this.initialized) {
            this.initEvents();
            this.initialized = true;
        }
    }

    constructor(inputId: string, btnId: string, resultsContainerId: string) {
        this.searchInput = document.getElementById(inputId) as HTMLInputElement | null;
        this.searchBtn = document.getElementById(btnId) as HTMLButtonElement | null;
        this.resultsContainer = document.getElementById(resultsContainerId);
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
            showToast((window as any).$t('search.err_no_query'), 'info');
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
            this.searchBtn.innerHTML = `<span class="spin">🔄</span> ${(window as any).$t('search.searching')}`;
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
            
            if (!response.ok) throw new Error((window as any).$t('search.err_failed'));
            
            const data = await response.json();
            const results: SearchResult[] = Array.isArray(data) ? data : (data.results || []);
            this.renderSearchResults(results);
        } catch (err) {
            const error = err as Error;
            showToast(`${(window as any).$t('common.error')}: ${error.message}`, 'error');
        } finally {
            this.searchPending = false;
            if (this.searchBtn) {
                this.searchBtn.disabled = false;
                this.searchBtn.textContent = (window as any).$t('search.btn_search');
            }
        }
    }

    private renderSearchResults(results: SearchResult[]): void {
        if (!this.resultsContainer) return;
        this.resultsContainer.innerHTML = '';

        if (!results || results.length === 0) {
            if (this.currentSearchPage > 0) {
                this.resultsContainer.innerHTML = `
                    <div class="search-empty">${(window as any).$t('search.no_more_results')}</div>
                    <div class="search-pagination">
                        <button class="pager-btn" id="kpPrevPageBtn">← ${(window as any).$t('search.prev_page')}</button>
                    </div>
                `;
                document.getElementById('kpPrevPageBtn')?.addEventListener('click', () => this.doSearch(this.currentSearchPage - 1));
            } else {
                this.resultsContainer.innerHTML = `
                    <div class="search-empty" style="padding-top: 60px; display: flex; flex-direction: column; align-items: center;">
                        <div style="font-size: 40px; margin-bottom: 12px; opacity: 0.5;">📭</div>
                        <div style="color: var(--text); font-weight: 500;">${(window as any).$t('search.no_results_found')}</div>
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
            const docTitle = result.title || (window as any).$t('search.untitled_doc');
            
            let snippet = (result.content || '').substring(0, 300);
            snippet = snippet.replace(/\[\[IMAGE_URL:[^\]]+\]\]/g, '[Image]')
                             .replace(/```mermaid[\s\S]*?```/g, '[Diagram]')
                             .trim();

            const docAuthor = result.author ? `👤 ${escapeHtml(result.author)}` : '';
            const sourceBadge = (result.source || 'internal').toLowerCase();
            const dateStr = result.updated_at ? new Date(result.updated_at).toLocaleDateString('vi-VN') : '';

            item.innerHTML = `
                <div class="kp-result-header">
                    <span class="kp-result-title">${escapeHtml(docTitle)}</span>
                    <div class="kp-result-actions">
                        ${score != null ? `
                            <div class="kp-result-score-wrap" title="${this.formatScoreBreakdown(result.score_breakdown)}">
                                <span class="kp-result-score">${score}% ${(window as any).$t('search.match')}</span>
                            </div>
                        ` : ''}
                        <button class="secondary-btn mini kp-pin-btn" title="${(window as any).$t('search.pin_draft')}" data-doc-id="${escapeHtml(docId)}" data-doc-title="${escapeHtml(docTitle)}">📌</button>
                    </div>
                </div>
                <div class="kp-result-snippet">${escapeHtml(snippet)}...</div>
                <div class="kp-result-meta">
                    <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                        <span class="kp-result-badge source-${sourceBadge}">${escapeHtml(result.source || 'N/A')}</span>
                        ${docAuthor ? `<span class="kp-result-author">${docAuthor}</span>` : ''}
                        ${dateStr ? `<span style="font-size: 11px; color: var(--text-muted);">🕒 ${dateStr}</span>` : ''}
                    </div>
                    <div class="kp-result-footer-actions">
                        <button class="secondary-btn mini view-doc-btn" data-doc-id="${escapeHtml(docId)}">📄 ${(window as any).$t('search.view_details')}</button>
                        ${result.url ? `<a class="kp-result-url" href="${escapeHtml(result.url)}" target="_blank" rel="noopener">${(window as any).$t('search.original_link')} ↗</a>` : ''}
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
        prevBtn.textContent = `← ${(window as any).$t('search.prev_page')}`;
        prevBtn.disabled = this.currentSearchPage === 0;
        prevBtn.addEventListener('click', () => this.doSearch(this.currentSearchPage - 1));
        
        const pageInfo = document.createElement('span');
        pageInfo.className = 'pager-info';
        pageInfo.textContent = `${(window as any).$t('search.page')} ${this.currentSearchPage + 1}`;
        
        const nextBtn = document.createElement('button');
        nextBtn.className = 'secondary-btn';
        nextBtn.textContent = `${(window as any).$t('search.next_page')} →`;
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
            if (!res.ok) throw new Error((window as any).$t('search.err_load_content'));
            const doc = await res.json() as SearchResult;

            let htmlContent = renderMarkdown(doc.content || (window as any).$t('search.no_content'));

            const body = document.createElement('div');
            body.innerHTML = `
                <div style="margin-bottom: 16px; font-size: 13px; color: var(--text-dim); display: flex; gap: 12px; flex-wrap: wrap; align-items: center;">
                    <span class="kp-result-badge">${escapeHtml(doc.source || 'N/A')}</span>
                    ${doc.author ? `<span>👤 ${escapeHtml(doc.author)}</span>` : ''}
                    ${doc.score_breakdown ? `<span style="color: var(--success); font-weight: 600;">🎯 ${this.formatScoreBreakdown(doc.score_breakdown)}</span>` : ''}
                    ${doc.url ? `<a href="${escapeHtml(doc.url)}" target="_blank" style="color: var(--accent);">${(window as any).$t('search.open_original')} ↗</a>` : ''}
                </div>
                <div style="max-height: 60vh; overflow-y: auto; line-height: 1.6; color: var(--text); padding-right: 8px;">
                    ${htmlContent}
                </div>
            `;

            kpOpenModal({
                title: doc.title || (window as any).$t('search.doc_details'),
                content: body,
                okText: (window as any).$t('common.close'),
                cancelText: null
            });
        } catch (err) {
            const error = err as Error;
            showToast(error.message, 'error');
        }
    }

    private formatScoreBreakdown(breakdown: any): string {
        if (!breakdown || typeof breakdown !== 'object') return '';
        const parts: string[] = [];
        if (breakdown.vector_score != null) parts.push(`${(window as any).$t('search.vector_label')}: ${Math.round(breakdown.vector_score * 100)}%`);
        if (breakdown.keyword_score != null) parts.push(`${(window as any).$t('search.keywords')}: ${Math.round(breakdown.keyword_score * 100)}%`);
        if (breakdown.rerank_score != null) parts.push(`${(window as any).$t('search.rerank_label')}: ${Math.round(breakdown.rerank_score * 100)}%`);
        return parts.length > 0 ? parts.join(' | ') : '';
    }

}