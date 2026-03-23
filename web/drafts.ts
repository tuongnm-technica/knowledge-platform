import { API, authFetch } from './client';
import { Draft } from './models';
import { showToast, formatDateTime, kpConfirm } from './ui';
import { AIEditor } from './editor';

export class DraftsModule {
    private drafts: Draft[] = [];
    private isLoading = false;
    private filterType = '';
    private currentDraftId: string | null = null;
    private currentDraft: Draft | null = null;
    private editorInstance: AIEditor | null = null;

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
            if (!response.ok) throw new Error('Failed to load drafts');
            const data = await response.json() as { drafts: Draft[] };
            this.drafts = data.drafts || [];
        } catch (err) {
            console.error(err);
            showToast('Không tải được danh sách drafts', 'error');
        } finally {
            this.isLoading = false;
            this.render();
            // Sync badges count
            const alpine = (window as any).Alpine;
            if (alpine?.store('badges')) {
                alpine.store('badges').drafts = this.drafts.length;
            }
        }
    }

    private bindGlobalActions() {
        document.querySelector('#drafts-refresh-btn')?.addEventListener('click', () => this.loadDraftsPage(true));
        document.querySelector('#drafts-filter')?.addEventListener('change', (e) => {
            this.filterType = (e.currentTarget as HTMLSelectElement).value;
            this.loadDraftsPage();
        });
        document.querySelector('#drafts-close-editor')?.addEventListener('click', () => this.closeDraftEditor());
        document.querySelector('#drafts-save-btn')?.addEventListener('click', () => this.saveDraft());
    }

    public async openDocDraftEditor(draftId: string) {
        this.currentDraftId = draftId;
        this.isLoading = true;
        this.render();
        try {
            const res = await authFetch(`${API}/docs/drafts/${draftId}`);
            if (!res.ok) throw new Error('Không tải được draft');
            const data = await res.json() as { draft: Draft };
            this.currentDraft = data.draft;
            
            this.isLoading = false;
            this.render(); // Render editor container first

            // Khởi tạo AI Editor sau khi render
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
            if (!res.ok) throw new Error('Lưu thất bại');
            showToast('Đã lưu bản nháp', 'success');
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    public async deleteDraft(draftId: string) {
        if (!await kpConfirm({ 
            title: 'Xóa bản nháp', 
            message: 'Bạn có chắc chắn muốn xóa bản nháp này?', 
            danger: true 
        })) return;
        try {
            const res = await authFetch(`${API}/docs/drafts/${draftId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Xóa thất bại');
            showToast('Đã xóa bản nháp', 'success');
            await this.loadDraftsPage(true);
        } catch (err) {
            showToast((err as Error).message, 'error');
        }
    }

    private escapeHtml(unsafe: string) {
        if (!unsafe) return '';
        return String(unsafe).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#039;");
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
                    grid.innerHTML = '<div class="empty-state">Chưa có bản nháp nào. Hãy chạy skill để tạo nháp.</div>';
                } else {
                    grid.innerHTML = this.drafts.map(d => `
                        <div class="draft-card" data-id="${d.id}">
                            <div class="draft-card-header">
                                <span class="draft-type-tag">${(d.doc_type || 'doc').toUpperCase()}</span>
                                <span class="draft-date">${formatDateTime(d.created_at)}</span>
                            </div>
                            <div class="draft-card-title">${this.escapeHtml(d.title || d.id)}</div>
                            <div class="draft-card-footer">
                                <button class="secondary-btn mini edit-btn" data-id="${d.id}">✏️ Sửa</button>
                                <button class="danger-btn mini ghost-btn delete-btn" data-id="${d.id}">🗑 Xóa</button>
                            </div>
                        </div>
                    `).join('');

                    // Bind events
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
}