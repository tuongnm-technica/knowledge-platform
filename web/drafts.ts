import { API, authFetch } from './client';
import { Draft } from './models';
import { kpPrompt } from './ui';

export class DraftsModule {
    private currentDraftId: string | null = null;

    constructor() {
        this.initStaticEvents();
    }

    private initStaticEvents(): void {
        document.getElementById('draftsTypeFilter')?.addEventListener('change', () => this.loadDraftsPage(true));
        document.getElementById('refreshDraftsBtn')?.addEventListener('click', () => this.loadDraftsPage(true));
    }

    public async loadDraftsPage(refresh = false): Promise<void> {
        const container = document.getElementById('draftsList');
        if (container && !refresh) container.innerHTML = '<div class="drafts-loading">Đang tải...</div>';

        try {
            const filterEl = document.getElementById('draftsTypeFilter') as HTMLSelectElement | null;
            const docType = filterEl?.value ? `&doc_type=${filterEl.value}` : '';
            const response = await authFetch(`${API}/docs/drafts?limit=50${docType}`);
            
            if (!response.ok) throw new Error('Failed to load drafts');
            const data = await response.json();
            this.renderDraftsList(data.drafts || []);
        } catch (e: any) {
            console.error('Error loading drafts page:', e);
            this.showToast('Không tải được danh sách drafts', 'error');
        }
    }

    private renderDraftsList(drafts: Draft[]): void {
        const container = document.getElementById('draftsList');
        if (!container) return;

        container.innerHTML = '';
        if (!drafts || drafts.length === 0) {
            container.innerHTML = '<div class="drafts-empty">Chưa có bản nháp nào. Tạo draft từ Chat để bắt đầu.</div>';
            return;
        }

        const grid = document.createElement('div');
        grid.className = 'drafts-list';

        drafts.forEach(draft => {
            const card = document.createElement('div');
            card.className = 'draft-card';
            const docType = String(draft.doc_type || 'srs').toUpperCase();
            const statusColor = draft.status === 'approved' ? '#10b981'
                              : draft.status === 'rejected'  ? '#ef4444'
                              : draft.status === 'published' ? '#3b82f6'
                              : '#8b5cf6';
            
            // Render HTML không chứa onclick inline
            card.innerHTML = `
                <div class="draft-header">
                    <div style="display:flex; justify-content:space-between; width:100%; align-items:center;">
                        <div class="draft-type">${this.escapeHtml(docType)}</div>
                        <div style="font-size:10px;padding:4px 10px;border-radius:20px;background:${statusColor}15;color:${statusColor};font-weight:700;text-transform:uppercase;border:1px solid ${statusColor}30">
                            ${this.escapeHtml(draft.status || 'draft')}
                        </div>
                    </div>
                    <div class="draft-title">${this.escapeHtml(draft.title || 'Untitled')}</div>
                </div>
                <div class="draft-meta">
                    <p>${this.escapeHtml((draft.content || '').substring(0, 150))}${(draft.content?.length || 0) > 150 ? '...' : ''}</p>
                    <span>Cập nhật: ${this.formatDate(draft.updated_at || draft.created_at)}</span>
                </div>
                <div class="draft-actions">
                    <button class="primary-btn mini btn-open-draft" style="flex:1; justify-content:center">📄 Mở Editor</button>
                    <button class="secondary-btn mini btn-delete-draft" title="Xóa">🗑</button>
                </div>
            `;
            
            // Gắn event listener an toàn
            card.querySelector('.btn-open-draft')?.addEventListener('click', () => this.openDocDraftEditor(draft.id));
            card.querySelector('.btn-delete-draft')?.addEventListener('click', () => this.deleteDraft(draft.id));

            grid.appendChild(card);
        });

        container.appendChild(grid);
    }

    public async openDocDraftEditor(draftId: string): Promise<void> {
        this.currentDraftId = draftId;
        const container = document.getElementById('draftsList');
        if (container) container.innerHTML = '<div class="drafts-loading">Đang tải bản nháp...</div>';

        try {
            const res = await authFetch(`${API}/docs/drafts/${draftId}`);
            if (!res.ok) throw new Error('Không tải được draft');
            const data = await res.json();
            this.renderDraftEditor(data.draft);
        } catch (e: any) {
            this.showToast(e.message, 'error');
            this.loadDraftsPage();
        }
    }

    private renderDraftEditor(draft: Draft): void {
        const container = document.getElementById('draftsList');
        if (!container) return;

        container.innerHTML = `
            <div class="draft-editor-wrap" style="height: calc(100vh - 160px);">
                <div class="draft-editor">
                    <div class="draft-editor-header" style="display:flex;align-items:center;gap:12px;margin-bottom:12px;flex-wrap:wrap;">
                        <button class="secondary-btn mini btn-back">← Quay lại</button>
                        <span class="draft-type" style="font-size:11px;padding:6px 12px;border-radius:8px">${this.escapeHtml((draft.doc_type || 'srs').toUpperCase())}</span>
                        <input id="draftTitleInput" type="text" value="${this.escapeHtml(draft.title || '')}"
                               style="flex:1;min-width:200px;font-size:18px;font-weight:800;border:none;background:transparent;outline:none;color:var(--text)" placeholder="Tiêu đề...">
                        
                        <div style="display:flex;align-items:center;gap:8px">
                            <select id="draftStatusSelect" class="time-input" style="font-size:12px;padding:6px 10px;border-radius:10px">
                                <option value="draft" ${draft.status === 'draft' ? 'selected' : ''}>Draft</option>
                                <option value="review" ${draft.status === 'review' ? 'selected' : ''}>Đang review</option>
                                <option value="approved" ${draft.status === 'approved' ? 'selected' : ''}>Approved</option>
                                <option value="published" ${draft.status === 'published' ? 'selected' : ''}>Published</option>
                                <option value="rejected" ${draft.status === 'rejected' ? 'selected' : ''}>Rejected</option>
                            </select>
                            <button class="secondary-btn ai-rewrite-btn" id="btnRewrite">✨ AI Rewrite</button>
                            <button class="primary-btn btn-save-draft">💾 Lưu</button>
                        </div>
                    </div>
                    <div class="draft-split-view">
                        <textarea id="draftContentEditor" class="draft-textarea" spellcheck="false" placeholder="Nhập nội dung Markdown tại đây...">${this.escapeHtml(draft.content || '')}</textarea>
                        <div id="draftContentPreview" class="draft-preview"></div>
                    </div>
                </div>
            </div>
        `;

        container.querySelector('.btn-back')?.addEventListener('click', () => this.closeDraftEditor());
        container.querySelector('.btn-save-draft')?.addEventListener('click', () => this.saveDraft());
        container.querySelector('#btnRewrite')?.addEventListener('click', () => this.refineSelectedText());

        const editor = document.getElementById('draftContentEditor') as HTMLTextAreaElement | null;
        const preview = document.getElementById('draftContentPreview');
        
        const updatePreview = () => {
            if (editor && preview && typeof (window as any).marked !== 'undefined') {
                            const rawHtml = (window as any).marked.parse(editor.value, { breaks: true, gfm: true });
                            preview.innerHTML = DOMPurify.sanitize(rawHtml);
            }
        };

        if (editor) {
            editor.addEventListener('input', updatePreview);
            updatePreview();
        }
    }

    public async refineSelectedText(): Promise<void> {
        if (!this.currentDraftId) return;
        const editor = document.getElementById('draftContentEditor') as HTMLTextAreaElement | null;
        if (!editor) return;

        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        const selectedText = editor.value.substring(start, end);

        if (!selectedText || selectedText.trim().length === 0) {
            this.showToast('Vui lòng bôi đen một đoạn văn bản cần viết lại.', 'warning');
            return;
        }

        const instruction = await kpPrompt({
            title: '✨ AI Rewrite',
            message: 'Bạn muốn AI viết lại đoạn văn bản này như thế nào?',
            placeholder: 'VD: Dịch sang tiếng Anh, viết ngắn gọn hơn...'
        });

        if (!instruction) return;
        this.showToast('AI đang phân tích và viết lại...', 'info');

        try {
            const res = await authFetch(`${API}/docs/drafts/${this.currentDraftId}/refine`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ selected_text: selectedText, instruction }),
            });
            if (!res.ok) throw new Error('Lỗi khi gọi AI Rewrite');
            const data = await res.json();
            editor.value = editor.value.substring(0, start) + (data.refined_text || '') + editor.value.substring(end);
            this.showToast('Đã viết lại thành công!', 'success');
        } catch (e: any) { this.showToast(e.message, 'error'); }
    }

    public async saveDraft(): Promise<void> {
        if (!this.currentDraftId) return;
        const title   = (document.getElementById('draftTitleInput') as HTMLInputElement)?.value.trim();
        const content = (document.getElementById('draftContentEditor') as HTMLTextAreaElement)?.value;
        const status  = (document.getElementById('draftStatusSelect') as HTMLSelectElement)?.value;

        try {
            const res = await authFetch(`${API}/docs/drafts/${this.currentDraftId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, content, status }),
            });
            if (!res.ok) throw new Error('Lưu thất bại');
            this.showToast('Đã lưu bản nháp', 'success');
        } catch (e: any) {
            this.showToast(e.message, 'error');
        }
    }

    public closeDraftEditor(): void {
        this.currentDraftId = null;
        this.loadDraftsPage();
    }

    public async deleteDraft(draftId: string): Promise<void> {
        if (!confirm('Xóa bản nháp này?')) return;
        try {
            const res = await authFetch(`${API}/docs/drafts/${draftId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Xóa thất bại');
            this.showToast('Đã xóa bản nháp', 'success');
            this.loadDraftsPage(true);
        } catch (e: any) {
            this.showToast(e.message, 'error');
        }
    }

    // --- Utils (Giống TasksModule) ---
    // ... formatDate, escapeHtml, showToast
}