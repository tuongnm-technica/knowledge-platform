import { API, authFetch } from './client';
import { Draft } from './models';
import { kpPrompt, showToast, formatDateTime } from './ui';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

export function DraftsAlpine() {
    return {
        drafts: [] as Draft[],
        isLoading: false,
        filterType: '',
        currentDraftId: null as string | null,
        currentDraft: null as Draft | null,

        init() {
            document.addEventListener('kp-refresh-drafts', () => {
                this.loadDraftsPage(true);
            });
            
            // Tự động render Markdown Preview mỗi khi nội dung Editor thay đổi
            const self = this as any;
            if (self.$watch) {
                self.$watch('currentDraft.content', (val: string) => {
                    this.updatePreview(val);
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
                setTimeout(() => this.updatePreview(this.currentDraft?.content || ''), 50);
            } catch (err) {
                const error = err as Error;
                showToast(error.message, 'error');
                this.closeDraftEditor();
            } finally {
                this.isLoading = false;
            }
        },

        closeDraftEditor() {
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
                        title: this.currentDraft.title, 
                        content: this.currentDraft.content, 
                        status: this.currentDraft.status 
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
            if (!confirm('Xóa bản nháp này?')) return;
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
        
        async refineSelectedText() {
            if (!this.currentDraftId || !this.currentDraft) return;
            const editor = document.getElementById('draftContentEditor') as HTMLTextAreaElement | null;
            if (!editor) return;

            const start = editor.selectionStart;
            const end = editor.selectionEnd;
            const selectedText = editor.value.substring(start, end);

            if (!selectedText || selectedText.trim().length === 0) {
                showToast('Vui lòng bôi đen một đoạn văn bản cần viết lại.', 'warning');
                return;
            }

            const instruction = await kpPrompt({
                title: '✨ AI Rewrite',
                message: 'Bạn muốn AI viết lại đoạn văn bản này như thế nào?',
                placeholder: 'VD: Dịch sang tiếng Anh, viết ngắn gọn hơn...'
            });

            if (!instruction || typeof instruction !== 'string') return;
            showToast('AI đang phân tích và viết lại...', 'info');

            try {
                const res = await authFetch(`${API}/docs/drafts/${this.currentDraftId}/refine`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ selected_text: selectedText, instruction }),
                });
                if (!res.ok) throw new Error('Lỗi khi gọi AI Rewrite');
                const data = await res.json() as { refined_text?: string };
                
                if (this.currentDraft) {
                    this.currentDraft.content = editor.value.substring(0, start) + (data.refined_text || '') + editor.value.substring(end);
                }
                showToast('Đã viết lại thành công!', 'success');
            } catch (err) { 
                const error = err as Error;
                showToast(error.message, 'error'); 
            }
        }
    };
}