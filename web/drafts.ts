import { API, authFetch } from './client';
import { Draft } from './models';
import { showToast, formatDateTime, kpConfirm, updateBadge, escapeHtml } from './ui';
import { AIEditor } from './editor';

export class DraftsModule {
    private drafts: Draft[] = [];
    private isLoading = false;
    private filterType = '';
    private currentDraftId: string | null = null;
    private currentDraft: Draft | null = null;
    private editorInstance: AIEditor | null = null;
    private isEventsBound = false;
    private pollingInterval: any = null;

    constructor() {
        document.addEventListener('kp-refresh-drafts', () => {
            this.loadDraftsPage(true);
        });
    }

    public async init() {
        await this.loadDraftsPage();
        this.bindGlobalActions();
    }

    public async loadDraftsPage(refresh = false) {
        if (!refresh) this.isLoading = true;
        this.render();
        try {
            const docType = this.filterType ? `&doc_type=${this.filterType}` : '';
            const response = await authFetch(`${API}/docs/drafts?limit=50${docType}`);
            if (!response.ok) throw new Error((window as any).$t('drafts.err_load_list'));
            const data = await response.json() as { drafts: Draft[] };
            this.drafts = data.drafts || [];
            this.checkPolling();
        } catch (err) {
            console.error(err);
            showToast((window as any).$t('drafts.err_load_list'), 'error');
        } finally {
            this.isLoading = false;
            this.render();
            updateBadge('drafts', this.drafts.length);
        }
    }

    private bindGlobalActions() {
        if (this.isEventsBound) return;
        this.isEventsBound = true;

        document.querySelector('#drafts-refresh-btn')?.addEventListener('click', () => this.loadDraftsPage(true));
        document.querySelector('#drafts-filter')?.addEventListener('change', (e) => {
            this.filterType = (e.currentTarget as HTMLSelectElement).value;
            this.loadDraftsPage();
        });
        document.querySelector('#drafts-close-editor')?.addEventListener('click', () => this.closeDraftEditor());
        document.querySelector('#drafts-save-btn')?.addEventListener('click', () => this.saveDraft());
        document.querySelector('#drafts-open-basket')?.addEventListener('click', () => {
             document.dispatchEvent(new CustomEvent('kp-open-basket'));
        });
    }

    public async openDocDraftEditor(draftId: string) {
        this.currentDraftId = draftId;
        this.isLoading = true;
        this.render();
        try {
            const res = await authFetch(`${API}/docs/drafts/${draftId}`);
            if (!res.ok) throw new Error((window as any).$t('drafts.err_load_draft'));
            const data = await res.json() as { draft: Draft };
            this.currentDraft = data.draft;

            this.isLoading = false;
            this.render();

            setTimeout(() => {
                const editorEl = document.getElementById('draftTipTapEditor');
                if (!editorEl) {
                    console.error('Editor element not found');
                    return;
                }
                if (this.editorInstance) this.editorInstance.destroy();
                this.editorInstance = new AIEditor('draftTipTapEditor', (content) => {
                    if (this.currentDraft) this.currentDraft.content = content;
                });
                this.editorInstance.setDraftId(this.currentDraftId!);
                this.editorInstance.setContent(this.currentDraft?.content || '');
            }, 100);
        } catch (err) {
            showToast((err as Error).message, 'error');
            this.closeDraftEditor();
        } finally {
            this.isLoading = false;
            this.render();
        }
    }

    public closeDraftEditor() {
        if (this.editorInstance) {
            this.editorInstance.destroy();
            this.editorInstance = null;
        }
        this.currentDraftId = null;
        this.currentDraft = null;
        this.render();
        this.loadDraftsPage();
    }

    public async saveDraft() {
        if (!this.currentDraftId || !this.currentDraft) return;
        try {
            const content = this.editorInstance ? this.editorInstance.getContent() : this.currentDraft.content;
            const res = await authFetch(`${API}/docs/drafts/${this.currentDraftId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    title: this.currentDraft.title,
                    content: content,
                    status: this.currentDraft.status
                }),
            });
            if (!res.ok) throw new Error((window as any).$t('drafts.err_save_failed'));
            showToast((window as any).$t('drafts.save_success'), 'success');
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    public async deleteDraft(draftId: string) {
        if (!await kpConfirm({
            title: (window as any).$t('drafts.confirm_delete_title'),
            message: (window as any).$t('drafts.confirm_delete_msg'),
            danger: true
        })) return;
        try {
            const res = await authFetch(`${API}/docs/drafts/${draftId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error((window as any).$t('drafts.err_delete_failed'));
            showToast((window as any).$t('drafts.delete_success'), 'success');
            await this.loadDraftsPage(true);
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    private render() {
        const listContainer = document.querySelector('#drafts-list-view') as HTMLElement;
        const editorContainer = document.querySelector('#drafts-editor-view') as HTMLElement;
        const loadingDiv = document.querySelector('#drafts-loading') as HTMLElement;

        if (!listContainer || !editorContainer || !loadingDiv) return;

        loadingDiv.style.display = this.isLoading ? 'block' : 'none';

        if (this.currentDraftId) {
            listContainer.style.display = 'none';
            editorContainer.style.display = 'block';

            const titleEl = editorContainer.querySelector('#draft-editor-title') as HTMLInputElement;
            if (titleEl && this.currentDraft) titleEl.value = this.currentDraft.title || '';
        } else {
            listContainer.style.display = 'block';
            editorContainer.style.display = 'none';

            const grid = listContainer.querySelector('.drafts-grid');
            if (grid) {
                if (this.drafts.length === 0 && !this.isLoading) {
                    grid.innerHTML = `<div class="empty-state">${(window as any).$t('drafts.empty_hint_long')}</div>`;
                } else {
                    grid.innerHTML = this.drafts.map(d => {
                        const isProcessing = d.status === 'processing';
                        return `
                        <div class="draft-card ${isProcessing ? 'processing' : ''}" data-id="${d.id}">
                            <div class="draft-card-header">
                                <span class="draft-type-tag">${(d.doc_type || 'doc').toUpperCase()}</span>
                                <span class="draft-date">${formatDateTime(d.created_at)}</span>
                            </div>
                            <div class="draft-card-title">
                                ${isProcessing ? '<span class="loading-spinner mini"></span> ' : ''}
                                ${escapeHtml(d.title || d.id)}
                            </div>
                            <div class="draft-card-footer">
                                ${isProcessing 
                                    ? `<span class="status-tag processing">${(window as any).$t('drafts.status_processing')}</span>` 
                                    : `<button class="secondary-btn mini edit-btn" data-id="${d.id}">✏️ ${(window as any).$t('drafts.edit_btn')}</button>`
                                }
                                <button class="danger-btn mini ghost-btn delete-btn" data-id="${d.id}">🗑 ${(window as any).$t('drafts.delete_btn')}</button>
                            </div>
                        </div>
                    `}).join('');

                    grid.querySelectorAll('.edit-btn').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            this.openDocDraftEditor(btn.getAttribute('data-id')!);
                        });
                    });
                    grid.querySelectorAll('.delete-btn').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            e.stopPropagation();
                            this.deleteDraft(btn.getAttribute('data-id')!);
                        });
                    });
                    grid.querySelectorAll('.draft-card').forEach(card => {
                        card.addEventListener('click', () => {
                            this.openDocDraftEditor(card.getAttribute('data-id')!);
                        });
                    });
                }
            }
        }
    }

    private checkPolling() {
        const hasProcessing = this.drafts.some(d => d.status === 'processing');
        if (hasProcessing && !this.pollingInterval) {
            console.log('Starting drafts polling...');
            this.pollingInterval = setInterval(() => {
                // Only poll if we are NOT in the editor
                if (!this.currentDraftId) {
                    this.loadDraftsPage(true);
                }
            }, 5000);
        } else if (!hasProcessing && this.pollingInterval) {
            console.log('Stopping drafts polling.');
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
        }
    }
}
