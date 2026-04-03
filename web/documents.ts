import { API, authFetch } from './client';
import { escapeHtml, showToast, formatDateTime, kpConfirm, kpOpenModal } from './ui';
import { renderMarkdown } from './format';

export class DocumentsModule {
    private currentPage = 1;
    private totalPages = 1;
    private searchQuery = '';
    private sourceFilter = '';

    public async loadDocumentsPage(page: number = 1, query: string = '', source: string = ''): Promise<void> {
        this.currentPage = page;
        this.searchQuery = query;
        this.sourceFilter = source;

        const container = document.getElementById('page-documents');
        if (container) {
            const list = container.querySelector('#documentsList');
            if (list) list.innerHTML = `<div style="padding:40px; text-align:center;">${(window as any).$t('docs.loading')}</div>`;
        }

        try {
            const url = new URL(`${API}/documents`, window.location.origin);
            url.searchParams.set('limit', '50');
            url.searchParams.set('page', page.toString());
            if (query) url.searchParams.set('q', query);
            if (source) url.searchParams.set('source', source);

            const res = await authFetch(url.toString());
            if (!res.ok) throw new Error((window as any).$t('docs.err_load_list'));
            const data = await res.json() as { documents: any[], total: number, page: number, pages: number };
            
            this.totalPages = data.pages || 1;
            
            // Update manual count badge (Pure TS Refactor)
            const countEl = document.getElementById('doc-total-count');
            if (countEl) countEl.textContent = String(data.total || 0);

            this.renderDocuments(data.documents || []);
            this.updatePaginationUI();
        } catch (err) {
            const error = err as Error;
            showToast(error.message, 'error');
        }
    }

    private updatePaginationUI(): void {
        const pageInfo = document.getElementById('docPageInfo');
        if (pageInfo) pageInfo.textContent = `${(window as any).$t('docs.page')} ${this.currentPage} / ${this.totalPages}`;
        
        const prevBtn = document.getElementById('prevDocsBtn') as HTMLButtonElement;
        const nextBtn = document.getElementById('nextDocsBtn') as HTMLButtonElement;
        
        if (prevBtn) prevBtn.disabled = this.currentPage <= 1;
        if (nextBtn) nextBtn.disabled = this.currentPage >= this.totalPages;
    }

    private renderDocuments(docs: any[]): void {
        const list = document.getElementById('documentsList');
        if (!list) return;

        if (!docs || docs.length === 0) {
            list.innerHTML = `<div class="search-empty">${(window as any).$t('docs.empty_hint')}</div>`;
            return;
        }

        list.innerHTML = `
            <table class="admin-table" style="table-layout: fixed;">
                <thead>
                    <tr>
                        <th style="width: 40px"><input type="checkbox" id="selectAllDocs"></th>
                        <th>${(window as any).$t('docs.col_title')}</th>
                        <th style="width: 130px">${(window as any).$t('docs.col_source')}</th>
                        <th style="width: 180px">${(window as any).$t('docs.col_updated')}</th>
                        <th style="width: 180px; text-align:right">${(window as any).$t('docs.col_actions')}</th>
                    </tr>
                </thead>
                <tbody id="documentsTableBody">
                    ${docs.map(doc => `
                        <tr data-id="${doc.id}" style="cursor:context-menu">
                            <td><input type="checkbox" class="doc-checkbox" value="${doc.id}" data-title="${escapeHtml(doc.title)}"></td>
                            <td style="overflow: hidden;">
                                <div style="font-weight:600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; border:none" title="${escapeHtml(doc.title || '')}">${escapeHtml(doc.title || (window as any).$t('docs.untitled'))}</div>
                                <div style="font-size:11px; color:var(--text-dim); white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${escapeHtml(doc.url || '')}">${escapeHtml(doc.url || '')}</div>
                            </td>
                            <td><span class="connector-status-badge info" style="font-size:10px">${escapeHtml(doc.source)}</span></td>
                            <td style="font-size:12px">${formatDateTime(doc.updated_at)}</td>
                            <td class="admin-actions-cell" style="text-align:right">
                                <div style="display:flex; gap:8px; justify-content:flex-end">
                                    <button class="secondary-btn mini view-doc-btn" data-id="${doc.id}" title="${(window as any).$t('docs.btn_view')}">👁️</button>
                                    <button class="secondary-btn mini add-basket-btn" data-id="${doc.id}" data-title="${escapeHtml(doc.title)}" title="${(window as any).$t('docs.btn_add_basket')}">📌</button>
                                    <button class="secondary-btn mini view-source-btn" data-url="${doc.url}" title="${(window as any).$t('docs.btn_view_source')}">🔗</button>
                                    <button class="danger-btn mini delete-doc-btn" data-id="${doc.id}" title="${(window as any).$t('docs.btn_delete')}">🗑</button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        // Tool area events (hooked only once or re-hooked)
        this.setupToolbarEvents();

        // Row Events
        const selectAll = list.querySelector('#selectAllDocs') as HTMLInputElement;
        if (selectAll) {
            selectAll.addEventListener('change', (e) => {
                const checked = (e.target as HTMLInputElement).checked;
                list.querySelectorAll('.doc-checkbox').forEach(cb => (cb as HTMLInputElement).checked = checked);
            });
        }

        list.querySelectorAll('.view-doc-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.viewDocument((e.currentTarget as HTMLElement).getAttribute('data-id')!));
        });

        list.querySelectorAll('.add-basket-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const el = e.currentTarget as HTMLElement;
                this.addToBasket(el.getAttribute('data-id')!, el.getAttribute('data-title')!);
            });
        });

        list.querySelectorAll('.delete-doc-btn').forEach(btn => {
            btn.addEventListener('click', (e) => this.deleteDocument((e.currentTarget as HTMLElement).getAttribute('data-id')!));
        });

        list.querySelectorAll('.view-source-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const url = (e.currentTarget as HTMLElement).getAttribute('data-url');
                if (url) window.open(url, '_blank');
            });
        });

        // Right-click to add to basket
        list.querySelectorAll('tbody tr').forEach(tr => {
            tr.addEventListener('contextmenu', (e) => {
                e.preventDefault();
                const id = (e.currentTarget as HTMLElement).getAttribute('data-id')!;
                const title = (e.currentTarget as HTMLElement).querySelector('.doc-checkbox')?.getAttribute('data-title') || (window as any).$t('docs.fallback_title');
                this.addToBasket(id, title);
            });
        });
    }

    private setupToolbarEvents(): void {
        const searchBtn = document.getElementById('docSearchBtn');
        const searchInput = document.getElementById('docSearchInput') as HTMLInputElement;
        const sourceFilter = document.getElementById('docSourceFilter') as HTMLSelectElement;
        const prevBtn = document.getElementById('prevDocsBtn');
        const nextBtn = document.getElementById('nextDocsBtn');
        const batchBasketBtn = document.getElementById('batchAddToBasketBtn');
        const batchDeleteBtn = document.getElementById('batchDeleteDocsBtn');

        if (searchBtn && !searchBtn.hasAttribute('data-hooked')) {
            searchBtn.setAttribute('data-hooked', 'true');
            
            const triggerLoad = () => this.loadDocumentsPage(1, searchInput.value.trim(), sourceFilter ? sourceFilter.value : '');
            
            searchBtn.addEventListener('click', triggerLoad);
            searchInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') triggerLoad(); });
            if (sourceFilter) {
                sourceFilter.addEventListener('change', triggerLoad);
            }
            
            prevBtn?.addEventListener('click', () => { if (this.currentPage > 1) this.loadDocumentsPage(this.currentPage - 1, this.searchQuery, this.sourceFilter); });
            nextBtn?.addEventListener('click', () => { if (this.currentPage < this.totalPages) this.loadDocumentsPage(this.currentPage + 1, this.searchQuery, this.sourceFilter); });
            
            if (batchBasketBtn) batchBasketBtn.addEventListener('click', () => this.batchAddToBasket());
            if (batchDeleteBtn) batchDeleteBtn.addEventListener('click', () => this.batchDelete());
        }
    }

    private async viewDocument(docId: string): Promise<void> {
        try {
            const res = await authFetch(`${API}/documents/${docId}`);
            if (!res.ok) throw new Error((window as any).$t('docs.err_load_content'));
            const data = await res.json() as { document: any };
            const doc = data.document;

            const body = document.createElement('div');
            body.className = 'doc-view-modal';
            body.innerHTML = `
                <div style="margin-bottom:16px; padding-bottom:16px; border-bottom:1px solid var(--border)">
                    <div style="font-size:12px; color:var(--text-dim); margin-bottom:4px;">${escapeHtml(doc.source)} • ${formatDateTime(doc.updated_at)}</div>
                    <div style="font-weight:700; font-size:18px;">${escapeHtml(doc.title)}</div>
                    <div style="font-size:12px; color:var(--accent); word-break:break-all">${escapeHtml(doc.url)}</div>
                </div>
                <div class="markdown-body" style="max-height:60vh; overflow-y:auto; line-height:1.6; font-size:14px;">
                    ${this.renderEnrichedContent(doc.content)}
                </div>
            `;

            kpOpenModal({
                title: '📄 ' + (window as any).$t('docs.modal_title'),
                content: body,
                okText: (window as any).$t('common.close'),
                onOk: () => true
            });
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    private addToBasket(id: string, title: string): void {
        document.dispatchEvent(new CustomEvent('kp-add-to-basket', {
            detail: { id, title, options: { openDrawer: true } }
        }));
    }

    private batchAddToBasket(): void {
        const checkboxes = document.querySelectorAll('.doc-checkbox:checked') as NodeListOf<HTMLInputElement>;
        if (checkboxes.length === 0) {
            showToast((window as any).$t('docs.err_at_least_one'), 'warning');
            return;
        }
        checkboxes.forEach(cb => this.addToBasket(cb.value, cb.getAttribute('data-title') || (window as any).$t('docs.fallback_title')));
        showToast((window as any).$t('docs.batch_add_success', { count: checkboxes.length }), 'success');
    }

    private async deleteDocument(docId: string): Promise<void> {
        const confirmed = await kpConfirm({
            title: (window as any).$t('docs.confirm_delete_title'),
            message: (window as any).$t('docs.confirm_delete_msg'),
            danger: true
        });
        if (!confirmed) return;

        try {
            const res = await authFetch(`${API}/documents/batch`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids: [docId] })
            });
            if (!res.ok) throw new Error((window as any).$t('docs.err_delete_failed'));
            showToast((window as any).$t('docs.delete_success'), 'success');
            this.loadDocumentsPage(this.currentPage, this.searchQuery);
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    public async batchDelete(): Promise<void> {
        const checkboxes = document.querySelectorAll('.doc-checkbox:checked') as NodeListOf<HTMLInputElement>;
        const ids = Array.from(checkboxes).map(cb => cb.value);
        if (ids.length === 0) {
            showToast((window as any).$t('docs.err_at_least_one'), 'warning');
            return;
        }

        const confirmed = await kpConfirm({
            title: (window as any).$t('docs.confirm_batch_delete_title'),
            message: (window as any).$t('docs.confirm_batch_delete_msg', { count: ids.length }),
            danger: true
        });
        if (!confirmed) return;

        try {
            const res = await authFetch(`${API}/documents/batch`, {
                method: 'DELETE',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ids })
            });
            if (!res.ok) throw new Error((window as any).$t('docs.err_batch_delete_failed'));
            showToast((window as any).$t('docs.batch_delete_success', { count: ids.length }), 'success');
            this.loadDocumentsPage(1, this.searchQuery);
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }
    private renderEnrichedContent(content: string): string {
        if (!content) return (window as any).$t('docs.empty_content');
        
        let processedContent = content;
        let summaryHtml = '';

        // Extract [SUMMARY]...[/SUMMARY]
        const summaryMatch = processedContent.match(/\[SUMMARY\]([\s\S]*?)\[\/SUMMARY\]/);
        if (summaryMatch) {
            const summaryText = summaryMatch[1].trim();
            summaryHtml = `
                <div class="doc-summary-box" style="background: var(--glow); border-left: 4px solid var(--accent); padding: 20px; border-radius: 12px; margin-bottom: 24px; box-shadow: var(--shadow-soft);">
                    <div style="font-weight: 800; font-size: 11px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--accent); margin-bottom: 10px; display: flex; align-items: center; gap: 8px;">
                        <span style="font-size: 16px;">✨</span> ${(window as any).$t('docs.summary_label', { defaultValue: 'AI Summary' })}
                    </div>
                    <div style="font-size: 14.5px; color: var(--text); line-height: 1.6; font-style: italic; opacity: 0.95;">
                        ${renderMarkdown(summaryText)}
                    </div>
                </div>
            `;
            // Remove summary block from content to avoid double rendering
            processedContent = processedContent.replace(summaryMatch[0], '').trim();
        }
        
        return summaryHtml + renderMarkdown(processedContent);
    }
}
