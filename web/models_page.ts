import { authFetch } from './client';
import { LLMModel, ModelBindings, TaskType } from './models';
import { kpConfirm, showToast } from './ui';

export class ModelsModule {
    private models: LLMModel[] = [];
    private bindings: ModelBindings = {
        chat: '',
        ingestion_llm: '',
        agent: '',
        embedding: '',
        skill: '',
        vision: '',
    };
    private initialized = false;

    public async init() {
        (window as any).modelsModule = this;

        if (!this.initialized) {
            this.bindEvents();
            this.initialized = true;
        }

        await this.refreshData();
    }

    private bindEvents() {
        const container = document.getElementById('page-models');
        if (!container) return;

        // Tab switching - scope selector to models page only
        const tabs = container.querySelectorAll('.nav-tab');
        tabs.forEach(tab => {
            (tab as HTMLElement).addEventListener('click', () => {
                const target = (tab as HTMLElement).dataset.target;
                if (!target) return;

                // Toggle active tab
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Toggle sections - scope selector to models page only
                container.querySelectorAll('.models-section').forEach(sec => {
                    (sec as HTMLElement).style.display = sec.id === target ? 'block' : 'none';
                });
            });
        });

        const addBtn = container.querySelector('#addModelBtn') as HTMLElement;
        if (addBtn) {
            addBtn.addEventListener('click', () => this.showModal());
        }

        const resetBtn = container.querySelector('#resetModelsBtn') as HTMLElement;
        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.handleResetToDefaults());
        }

        const modelForm = container.querySelector('#modelForm') as HTMLFormElement | null;
        if (modelForm) {
            modelForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.handleSaveModel();
            });
        }

        // Scope close buttons to this module's modal
        const closeModalBtns = container.querySelectorAll('.close-modal');
        closeModalBtns.forEach((btn) => {
            (btn as HTMLElement).addEventListener('click', () => this.hideModal());
        });

        const providerSelect = container.querySelector('#m-provider') as HTMLSelectElement | null;
        if (providerSelect) {
            providerSelect.addEventListener('change', () => this.toggleProviderFields());
        }
    }

    private async refreshData() {
        try {
            const [modelsRes, bindingsRes] = await Promise.all([
                authFetch('/api/models/admin'),
                authFetch('/api/models/bindings'),
            ]);

            if (!modelsRes.ok) {
                throw new Error(await this.readError(modelsRes, 'Không thể tải danh sách model'));
            }
            if (!bindingsRes.ok) {
                throw new Error(await this.readError(bindingsRes, 'Không thể tải cấu hình binding'));
            }

            this.models = await modelsRes.json();

            const bindingData = await bindingsRes.json();
            this.bindings = {
                chat: bindingData.chat || '',
                ingestion_llm: bindingData.ingestion_llm || '',
                agent: bindingData.agent || '',
                embedding: bindingData.embedding || '',
                skill: bindingData.skill || '',
                vision: bindingData.vision || '',
            };

            this.renderTasks();
            this.renderModels();
        } catch (err) {
            console.error('Failed to fetch models data', err);
            showToast((err as Error).message || 'Không thể tải dữ liệu models', 'error');
        }
    }

    private renderTasks() {
        const tbody = document.getElementById('bindingsTableBody');
        if (!tbody) return;

        const activeModels = this.models.filter((model) => model.is_active);
        const tasks: { type: TaskType; label: string; desc: string }[] = [
            { type: 'chat', label: 'Hội thoại (Chat AI)', desc: 'Dùng cho trao đổi trực tiếp, hỗ trợ chọn nhiều model.' },
            { type: 'ingestion_llm', label: 'Xử lý dữ liệu (RAG)', desc: 'Dùng để trích xuất thông tin, tóm tắt tài liệu.' },
            { type: 'agent', label: 'Suy luận Agent', desc: 'Dùng cho các tác vụ phức tạp cần lập kế hoạch.' },
            { type: 'embedding', label: 'Vector hóa', desc: 'Dùng để chuyển văn bản thành số học để tìm kiếm.' },
            { type: 'vision', label: 'Thị giác máy tính', desc: 'Dùng để mô tả hình ảnh và OCR.' },
            { type: 'skill', label: 'Skill chuyên môn', desc: 'Dùng cho các module kỹ năng riêng biệt.' },
        ];

        tbody.innerHTML = tasks
            .map((task) => {
                const currentId = this.bindings[task.type];
                
                // For chat, show more info about multi-select
                let infoText = '';
                if (task.type === 'chat') {
                    const chatEnabledCount = this.models.filter(m => m.is_chat_enabled && m.is_active).length;
                    infoText = `<span class="count-badge">${chatEnabledCount}</span> model khả dụng`;
                } else {
                    infoText = `<span style="color:var(--text-dim); font-size:11px;">Mặc định hệ thống</span>`;
                }

                return `
                <tr id="task-row-${task.type}">
                    <td>
                        <div style="font-weight:600; font-size:14px;">${task.label}</div>
                        <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">${task.desc}</div>
                    </td>
                    <td>
                        <select class="form-select task-binding-select" data-task="${task.type}" disabled style="width:100%; border-radius:8px;">
                            <option value="">-- Chọn Model mặc định --</option>
                            ${activeModels
                                .map(
                                    (model) =>
                                        `<option value="${model.id}" ${currentId === model.id ? 'selected' : ''}>${model.llm_model_name} - ${model.name} (${model.provider})</option>`
                                )
                                .join('')}
                        </select>
                    </td>
                    <td>
                        <div style="display:flex; align-items:center; justify-content:space-between; gap:10px;">
                            ${infoText}
                            <button class="btn-binding-toggle edit" onclick="window.modelsModule.toggleBindingEdit('${task.type}', this)">
                                ✏️ Sửa
                            </button>
                        </div>
                    </td>
                </tr>`;
            })
            .join('');
    }

    public async toggleBindingEdit(taskType: TaskType, buttonEl: HTMLElement) {
        const row = document.getElementById(`task-row-${taskType}`);
        const select = row?.querySelector('select') as HTMLSelectElement;
        if (!row || !select) return;

        const isEditing = row.classList.contains('is-editing');

        if (isEditing) {
            // SAVE MODE
            const modelId = select.value;
            if (!modelId) {
                showToast('Vui lòng chọn một model', 'warning');
                return;
            }

            const success = await this.updateBinding(taskType, modelId);
            if (success) {
                row.classList.remove('is-editing');
                select.disabled = true;
                buttonEl.innerHTML = '✏️ Sửa';
                buttonEl.classList.remove('save');
                buttonEl.classList.add('edit');
            }
        } else {
            // EDIT MODE
            row.classList.add('is-editing');
            select.disabled = false;
            buttonEl.innerHTML = '✅ Lưu';
            buttonEl.classList.remove('edit');
            buttonEl.classList.add('save');
            select.focus();
        }
    }

    public async updateBinding(taskType: TaskType, modelId: string): Promise<boolean> {
        try {
            const res = await authFetch(`/api/models/bindings/${taskType}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId }),
            });

            if (!res.ok) {
                throw new Error(await this.readError(res, 'Lỗi khi cập nhật binding'));
            }

            this.bindings[taskType] = modelId;
            showToast(`Đã gán model mặc định cho ${taskType}`, 'success');
            return true;
        } catch (err) {
            showToast((err as Error).message || 'Lỗi kết nối', 'error');
            return false;
        }
    }

    private renderModels() {
        const grid = document.getElementById('modelsGrid');
        if (!grid) return;

        if (this.models.length === 0) {
            grid.innerHTML =
                '<div style="grid-column: 1/-1; padding: 60px; text-align: center; color: var(--text-dim);"><h3>Registry trống</h3><p>Hãy thêm model đầu tiên của bạn.</p></div>';
            return;
        }

        grid.innerHTML = this.models
            .map((model) => {
                const statusClass = model.is_active ? 'active' : 'inactive';
                const statusLabel = model.is_active ? 'Online' : 'Offline';
                const isUsedInChat = model.is_chat_enabled && model.is_active;

                return `
            <div class="model-registry-card ${model.is_default ? 'is-default' : ''} ${!model.is_active ? 'is-inactive' : ''}">
                <div class="mc-header">
                    <div class="mc-title-group">
                        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:12px;">
                            <div style="display:flex; align-items:center; gap:8px;">
                                <span class="provider-icon">${this.getProviderIcon(model.provider)}</span>
                                <h3 style="font-size: 16px; margin: 0; font-weight: 800; color: var(--accent);">${model.llm_model_name}</h3>
                            </div>
                        </div>
                        <div class="mc-pill-row" style="margin-top:8px;">
                            <span class="status-pill ${statusClass}">${statusLabel}</span>
                            ${isUsedInChat ? '<span class="status-pill chat">In Chat</span>' : ''}
                            ${model.is_default ? '<span class="status-pill default">System Default</span>' : ''}
                        </div>
                    </div>
                </div>
                <div class="mc-body" style="flex:1;">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text); margin-bottom: 4px;">${model.name}</div>
                    <div class="mc-description">${model.description || 'Không có mô tả.'}</div>
                </div>
                <div class="mc-footer">
                    <button class="secondary-btn mini" onclick="window.modelsModule.showModal('${model.id}')">Thiết lập</button>
                    <button class="danger-btn mini" onclick="window.modelsModule.confirmDelete('${model.id}')">Gỡ bỏ</button>
                </div>
            </div>
        `;
            })
            .join('');
    }

    private getProviderIcon(provider: string) {
        switch (provider) {
            case 'ollama': return '🦙';
            case 'gemini': return '♊';
            case 'openai': return '🤖';
            default: return '☁️';
        }
    }

    public async handleResetToDefaults() {
        const confirmed = await kpConfirm({
            title: 'Khôi phục cấu hình gốc?',
            message:
                'Toàn bộ danh sách model và gán tác vụ sẽ bị xóa để nạp lại cấu hình chuẩn. Bạn có chắc không?',
            okText: 'Xác nhận Reset',
        });

        if (!confirmed) return;

        try {
            const res = await authFetch('/api/models/reset-defaults', { method: 'POST' });
            if (!res.ok) {
                throw new Error(await this.readError(res, 'Lỗi khi khôi phục'));
            }

            showToast('Đã khôi phục cấu hình mặc định', 'success');
            await this.refreshData();
        } catch (err) {
            showToast((err as Error).message || 'Lỗi kết nối', 'error');
        }
    }

    public showModal(id?: string) {
        const modal = document.getElementById('modelModal');
        const title = document.getElementById('modalTitle');
        const form = document.getElementById('modelForm') as HTMLFormElement | null;

        if (!modal || !form) return;

        form.reset();
        (document.getElementById('modelId') as HTMLInputElement).value = id || '';

        if (id) {
            const model = this.models.find((item) => item.id === id);
            if (model) {
                if (title) title.textContent = 'Cập nhật AI Model';
                (document.getElementById('m-name') as HTMLInputElement).value = model.name || '';
                (document.getElementById('m-provider') as HTMLSelectElement).value = model.provider || 'ollama';
                (document.getElementById('m-model-name') as HTMLInputElement).value = model.llm_model_name || '';
                (document.getElementById('m-description') as HTMLTextAreaElement).value = model.description || '';
                (document.getElementById('m-base-url') as HTMLInputElement).value = model.base_url || '';
                (document.getElementById('m-api-key') as HTMLInputElement).value = model.api_key || '';
                (document.getElementById('m-active') as HTMLInputElement).checked = model.is_active;
                (document.getElementById('m-default') as HTMLInputElement).checked = !!model.is_default;
                (document.getElementById('m-chat-enabled') as HTMLInputElement).checked = !!model.is_chat_enabled;
            }
        } else if (title) {
            title.textContent = 'Thêm AI Model mới';
        }

        this.toggleProviderFields();
        modal.style.display = 'flex';
    }

    private hideModal() {
        const modal = document.getElementById('modelModal');
        if (modal) modal.style.display = 'none';
    }

    private toggleProviderFields() {
        const provider = (document.getElementById('m-provider') as HTMLSelectElement | null)?.value || 'ollama';
        const urlGroup = document.getElementById('url-group');
        const keyGroup = document.getElementById('key-group');

        if (urlGroup) {
            urlGroup.style.display = provider === 'ollama' || provider === 'vllm' ? 'block' : 'none';
        }
        if (keyGroup) {
            keyGroup.style.display = provider !== 'ollama' ? 'block' : 'none';
        }
    }

    private async handleSaveModel() {
        const id = (document.getElementById('modelId') as HTMLInputElement).value.trim();
        const payload = this.buildPayload();

        try {
            const url = id ? `/api/models/${id}` : '/api/models';
            const method = id ? 'PATCH' : 'POST';

            const res = await authFetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });

            if (!res.ok) {
                throw new Error(await this.readError(res, 'Không thể lưu model'));
            }

            showToast(id ? 'Đã cập nhật model' : 'Đã thêm model mới', 'success');
            this.hideModal();
            await this.refreshData();
        } catch (err) {
            showToast((err as Error).message || 'Lỗi kết nối', 'error');
        }
    }

    public async confirmDelete(id: string) {
        const confirmed = await kpConfirm({
            title: 'Xóa model khỏi Registry?',
            message: 'Hành động này sẽ gỡ bỏ model khỏi hệ thống. Các gán tác vụ liên quan sẽ bị lỗi.',
            okText: 'Xóa model',
        });
        if (!confirmed) return;

        try {
            const res = await authFetch(`/api/models/${id}`, {
                method: 'DELETE',
            });

            if (res.status !== 204) {
                throw new Error(await this.readError(res, 'Không thể xóa model'));
            }

            showToast('Đã xóa model', 'success');
            await this.refreshData();
        } catch (err) {
            showToast((err as Error).message || 'Lỗi kết nối', 'error');
        }
    }

    private buildPayload() {
        const provider = (document.getElementById('m-provider') as HTMLSelectElement).value;

        return {
            name: (document.getElementById('m-name') as HTMLInputElement).value.trim(),
            provider,
            llm_model_name: (document.getElementById('m-model-name') as HTMLInputElement).value.trim(),
            description: this.normalizeOptional((document.getElementById('m-description') as HTMLTextAreaElement).value),
            base_url: this.normalizeOptional((document.getElementById('m-base-url') as HTMLInputElement).value),
            api_key: provider === 'ollama'
                ? null
                : this.normalizeOptional((document.getElementById('m-api-key') as HTMLInputElement).value),
            is_active: (document.getElementById('m-active') as HTMLInputElement).checked,
            is_default: (document.getElementById('m-default') as HTMLInputElement).checked,
            is_chat_enabled: (document.getElementById('m-chat-enabled') as HTMLInputElement).checked,
        };
    }

    private normalizeOptional(value: string): string | null {
        const normalized = value.trim();
        return normalized ? normalized : null;
    }

    private async readError(response: Response, fallback: string): Promise<string> {
        try {
            const data = await response.clone().json();
            if (typeof data?.detail === 'string') return data.detail;
            if (typeof data?.message === 'string') return data.message;
        } catch (err) {
            // Ignore JSON parsing errors and try text below.
        }

        try {
            const text = (await response.text()).trim();
            return text || fallback;
        } catch (err) {
            return fallback;
        }
    }
}
