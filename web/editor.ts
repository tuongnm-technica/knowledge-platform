import { Editor, Extension } from '@tiptap/core';
import StarterKit from '@tiptap/starter-kit';
import { Markdown } from 'tiptap-markdown';
import Suggestion from '@tiptap/suggestion';
import tippy, { Instance as TippyInstance } from 'tippy.js';
import 'tippy.js/dist/tippy.css';
import { PromptSkill } from './models';
import { authFetch, API } from './client';
import { showToast } from './ui';

interface SuggestionProps {
    query: string;
    range: any;
    editor: Editor;
    clientRect: () => DOMRect;
}

// Lớp quản lý TipTap Editor + Slash Command
export class AIEditor {
    public editor!: Editor;
    private container: HTMLElement;
    private onUpdate: (content: string) => void;
    private skills: PromptSkill[] = [];

    // Popup Menu State
    private popupInstance: TippyInstance | null = null;
    private popupListEl: HTMLDivElement | null = null;
    private selectedIndex = 0;
    private currentProps: SuggestionProps | null = null;
    private currentDraftId: string | null = null;

    constructor(containerId: string, onUpdate: (content: string) => void) {
        this.container = document.getElementById(containerId) as HTMLElement;
        this.onUpdate = onUpdate;
        
        if (!this.container) throw new Error(`Container ${containerId} not found`);

        this.initEditor();
        this.loadSkills();
    }

    public setDraftId(id: string | null) {
        this.currentDraftId = id;
    }

    private async loadSkills() {
        try {
            const res = await authFetch(`${API}/docs/skills`);
            if (res.ok) {
                const data = await res.json() as { agents?: Array<{ doc_type?: string, label?: string, description?: string }> };
                const agents = data.agents || [];
                this.skills = agents.map((agent) => ({
                    id: agent.doc_type || agent.label || '',
                    name: agent.label || agent.doc_type || 'Untitled Skill',
                    description: agent.description || '',
                    template: agent.doc_type || '',
                    doc_type: agent.doc_type || '',
                    type: 'agent',
                }));
            }
        } catch (err) {
            console.error('Failed to load skills for editor slash menu', err);
        }
    }

    private initEditor() {
        this.container.innerHTML = '';
        const self = this;

        // Định nghĩa Plugin cho Slash Command
        const SlashCommand = Extension.create({
            name: 'slashCommand',
            addProseMirrorPlugins() {
                return [
                    Suggestion({
                        editor: this.editor,
                        char: '/',
                        command: ({ editor, range, props }) => {
                            const skill = props as PromptSkill;
                            // Xóa dấu '/' và query khỏi editor
                            editor.chain().focus().deleteRange(range).run();
                            self.executeSkill(skill);
                        },
                        items: ({ query }) => {
                            return self.skills
                                .filter(s => s.name.toLowerCase().includes(query.toLowerCase()) || 
                                             s.description.toLowerCase().includes(query.toLowerCase()))
                                .slice(0, 10);
                        },
                        render: () => {
                            return {
                                onStart: (props: any) => {
                                    self.currentProps = props;
                                    self.selectedIndex = 0;
                                    self.renderPopup(props);
                                },
                                onUpdate: (props: any) => {
                                    self.currentProps = props;
                                    self.selectedIndex = 0;
                                    self.updatePopup(props);
                                },
                                onKeyDown: (props: any) => {
                                    if (props.event.key === 'ArrowUp') {
                                        self.selectedIndex = (self.selectedIndex + self.popupListEl!.children.length - 1) % self.popupListEl!.children.length;
                                        self.highlightSelected();
                                        return true;
                                    }
                                    if (props.event.key === 'ArrowDown') {
                                        self.selectedIndex = (self.selectedIndex + 1) % self.popupListEl!.children.length;
                                        self.highlightSelected();
                                        return true;
                                    }
                                    if (props.event.key === 'Enter') {
                                        const items = self.getFilteredSkills(self.currentProps?.query || '');
                                        if (items.length > 0) {
                                            const item = items[self.selectedIndex];
                                            self.currentProps!.editor.chain().focus().deleteRange(self.currentProps!.range).run();
                                            self.executeSkill(item);
                                        }
                                        return true;
                                    }
                                    return false;
                                },
                                onExit: () => {
                                    self.popupInstance?.destroy();
                                    self.popupListEl = null;
                                }
                            }
                        }
                    })
                ];
            }
        });

        this.editor = new Editor({
            element: this.container,
            extensions: [
                StarterKit,
                Markdown,
                SlashCommand
            ],
            editorProps: {
                attributes: {
                    class: 'ai-editor-prosemirror',
                },
            },
            onUpdate: ({ editor }) => {
                // Return markdown or HTML based on what BE stores. Currently Drafts store Markdown.
                // Note: TipTap natively uses HTML or JSON. We need an extension for Markdown if we strictly want Markdown.
                // But for now, we can extract text or HTML. TipTap StarterKit has no native markdown export, 
                // but we can just use HTML, or install `tiptap-markdown`. 
                // Let's use HTML for Draft content if we change Drafts to support HTML, OR we can install 'tiptap-markdown'.
                // Actually, let's just emit HTML and see if it works, or we can use DOM purifiy.
                // But Drafts explicitly says "Markdown". Let's install `tiptap-markdown` or just use standard TipTap HTML!
                
                // For simplicity, we can emit HTML and render HTML directly.
                this.onUpdate((editor.storage as any).markdown.getMarkdown());
            },
        });
    }

    private getFilteredSkills(query: string) {
        return this.skills.filter(s => s.name.toLowerCase().includes(query.toLowerCase()) || 
                                       s.description.toLowerCase().includes(query.toLowerCase())).slice(0, 10);
    }

    private renderPopup(props: SuggestionProps) {
        const items = this.getFilteredSkills(props.query);
        if (items.length === 0) return;

        this.popupListEl = document.createElement('div');
        this.popupListEl.className = 'slash-popup-list';
        
        this.updatePopupContent(items);

        this.popupInstance = tippy('body', {
            getReferenceClientRect: props.clientRect,
            appendTo: () => document.body,
            content: this.popupListEl,
            showOnCreate: true,
            interactive: true,
            trigger: 'manual',
            placement: 'bottom-start',
            theme: 'light-border',
            animation: 'fade',
        })[0];
    }

    private updatePopup(props: SuggestionProps) {
        const items = this.getFilteredSkills(props.query);
        if (items.length === 0) {
            this.popupInstance?.hide();
            return;
        }
        
        this.updatePopupContent(items);
        this.popupInstance?.setContent(this.popupListEl!);
        if (!this.popupInstance?.state.isVisible) {
            this.popupInstance?.show();
        }
    }

    private updatePopupContent(items: PromptSkill[]) {
        if (!this.popupListEl) return;
        this.popupListEl.innerHTML = '';
        
        const header = document.createElement('div');
        header.className = 'slash-popup-header';
        header.innerText = '✨ AI Skills';
        this.popupListEl.appendChild(header);

        items.forEach((item, index) => {
            const btn = document.createElement('button');
            btn.className = `slash-popup-item ${index === this.selectedIndex ? 'selected' : ''}`;
            btn.innerHTML = `
                <div class="slash-item-name">${item.name}</div>
                <div class="slash-item-desc">${item.description}</div>
            `;
            btn.onclick = () => {
                const props = this.currentProps!;
                props.editor.chain().focus().deleteRange(props.range).run();
                this.executeSkill(item);
                this.popupInstance?.hide();
            };
            this.popupListEl!.appendChild(btn);
        });
    }

    private highlightSelected() {
        if (!this.popupListEl) return;
        const items = this.popupListEl.querySelectorAll('.slash-popup-item');
        items.forEach((item, index) => {
            if (index === this.selectedIndex) item.classList.add('selected');
            else item.classList.remove('selected');
        });
    }

    private async executeSkill(skill: PromptSkill) {
        // Lấy đoạn văn bản đang bôi đen hoặc toàn bộ văn bản để làm ngữ cảnh
        // Nếu editor đang chọn 1 đoạn, lấy đoạn đó, nếu không lấy text xung quanh con trỏ
        const { state } = this.editor;
        const { from, to } = state.selection;
        let selectedText = '';
        
        if (from !== to) {
            selectedText = state.doc.textBetween(from, to, ' ');
        } else {
            // Rất tiếc, nếu không chọn, lấy text của block hiện tại
            const rootPos = state.selection.$from;
            selectedText = rootPos.parent.textContent;
        }

        if (!selectedText.trim()) {
            showToast((window as any).$t('editor.err_no_selection', { defaultValue: 'Vui lòng bôi đen một số chữ/đoạn văn để AI xử lý.' }), 'warning');
            return;
        }

        // Tạo context giả lập
        let instruction = `Áp dụng skill: ${skill.name}. Mẫu: ${skill.template}`;

        if (!this.currentDraftId) {
            showToast((window as any).$t('editor.err_no_draft_id', { defaultValue: 'Chưa có Draft ID. Hãy lưu bài nháp trước.' }), 'error');
            return;
        }

        showToast((window as any).$t('editor.processing', { skill: skill.name, defaultValue: `AI đang xử lý: ${skill.name}...` }), 'info');
        
        // Cập nhật giao diện: thay thế văn bản đang chọn bằng khối Loading
        // (Đây là phiên bản đơn giản: ta sẽ ghi đè lên text sau khi có kết quả)

        try {
            const res = await authFetch(`${API}/docs/drafts/${this.currentDraftId}/refine`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    selected_text: selectedText, 
                    instruction: instruction 
                }),
            });
            if (!res.ok) throw new Error('AI xử lý thất bại');
            const data = await res.json() as { refined_text?: string };
            
            if (data.refined_text) {
                // Ghi đè AI result vào editor
                this.editor.chain().focus().insertContentAt({ from, to }, data.refined_text).run();
                showToast((window as any).$t('editor.success', { defaultValue: 'AI đã hoàn thành!' }), 'success');
            }
        } catch (err) {
            console.error(err);
            showToast((window as any).$t('editor.error', { defaultValue: 'AI gặp lỗi khi xử lý.' }), 'error');
        }
    }

    public setContent(content: string) {
        if (this.editor) {
            this.editor.commands.setContent(content);
        }
    }

    public getContent(): string {
        return this.editor ? (this.editor.storage as any).markdown.getMarkdown() : '';
    }

    public destroy() {
        if (this.editor) {
            this.editor.destroy();
        }
        if (this.popupInstance) {
            this.popupInstance.destroy();
        }
    }
}
