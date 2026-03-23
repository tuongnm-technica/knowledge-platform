import { API, authFetch } from './client';
import { Draft } from './models';
import { showToast, formatDateTime, kpConfirm } from './ui';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { AIEditor } from './editor';

export function DraftsAlpine() {
    return {
        drafts: [] as Draft[],
        isLoading: false,
        filterType: '',
        currentDraftId: null as string | null,
        currentDraft: null as Draft | null,
        editorInstance: null as AIEditor | null,

        init() {
            document.addEventListener('kp-refresh-drafts', () => {
                this.loadDraftsPage(true);
            });
            
            // Auto render logic is moved to AIEditor, so we don't need updatePreview if using TipTap
            // But we keep it in case we need it elsewhere.
            const self = this as any;
            if (self.$watch) {
                self.$watch('currentDraft.content', () => {
                    // Cập nhật preview nếu cần
                });
            }
        },

        async loadDraftsPage(refresh = false) {
            if (!refresh) this.isLoading = true;
            try {
                const docType = this.filterType ? `&doc_type=${this.filterType}` : '';
                const response = await authFetch(`${API}/docs/drafts?limit=50${docType}`);
                if (!response.ok) throw new Error('Failed to load drafts');
                const data = await response.json() as { drafts: Draft[] };
                this.drafts = data.drafts || [];
            } catch (err) {
                const error = err as Error;
                console.error(error);
                showToast('Không tải được danh sách drafts', 'error');
            } finally {
                this.isLoading = false;
            }
        },

        getStatusColor(status: string) {
            if (status === 'approved') return '#10b981';
            if (status === 'rejected') return '#ef4444';
            if (status === 'published') return '#3b82f6';
            return '#8b5cf6';
        },

        formatDate(val: string | Date | null) {
            if (!val) return 'N/A';
            return formatDateTime(val);
        },

        async openDocDraftEditor(draftId: string) {
            this.currentDraftId = draftId;
            this.isLoading = true;
            try {
                const res = await authFetch(`${API}/docs/drafts/${draftId}`);
                if (!res.ok) throw new Error('Không tải được draft');
                const data = await res.json() as { draft: Draft };
                this.currentDraft = data.draft;
                
                // Khởi tạo AI Editor sau khi render
                setTimeout(() => {
                    if (this.editorInstance) {
                        this.editorInstance.destroy();
                    }
                    this.editorInstance = new AIEditor('draftTipTapEditor', (content) => {
                        if (this.currentDraft) {
                            this.currentDraft.content = content;
                        }
                    });
                    this.editorInstance?.setDraftId(this.currentDraftId!);
                    this.editorInstance?.setContent(this.currentDraft?.content || '');
                }, 100);
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
                this.closeDraftEditor();
            } finally {
                this.isLoading = false;
            }
        },

        closeDraftEditor() {
            if (this.editorInstance) {
                this.editorInstance.destroy();
                this.editorInstance = null;
            }
            this.currentDraftId = null;
            this.currentDraft = null;
            this.loadDraftsPage();
        },

        async saveDraft() {
            if (!this.currentDraftId || !this.currentDraft) return;
            try {
                const res = await authFetch(`${API}/docs/drafts/${this.currentDraftId}`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        title: this.currentDraft!.title, 
                        content: this.editorInstance ? this.editorInstance.getContent() : this.currentDraft!.content, 
                        status: this.currentDraft!.status 
                    }),
                });
                if (!res.ok) throw new Error('Lưu thất bại');
                showToast('Đã lưu bản nháp', 'success');
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            }
        },

        async deleteDraft(draftId: string) {
            if (!await kpConfirm({ 
                title: 'Xóa bản nháp', 
                message: 'Bạn có chắc chắn muốn xóa bản nháp này?', 
                danger: true 
            })) return;
            try {
                const res = await authFetch(`${API}/docs/drafts/${draftId}`, { method: 'DELETE' });
                if (!res.ok) throw new Error('Xóa thất bại');
                showToast('Đã xóa bản nháp', 'success');
                this.loadDraftsPage(true);
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
            }
        },

        updatePreview(content: string) {
            const preview = document.getElementById('draftContentPreview');
            if (preview) {
                const rawHtml = marked.parse(content || '', { breaks: true, gfm: true }) as string;
                preview.innerHTML = DOMPurify.sanitize(rawHtml);
            }
        },
        
        // remove refineSelectedText since it is now natively in AIEditor via Slash Commands
        refineSelectedText() {
            // Deprecated
        }
    };
}