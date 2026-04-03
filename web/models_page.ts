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
    private editingTask: TaskType | null = null;

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
                throw new Error(await this.readError(modelsRes, (window as any).$t('models.err_load_models')));
            }
            if (!bindingsRes.ok) {
                throw new Error(await this.readError(bindingsRes, (window as any).$t('models.err_load_bindings')));
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
            showToast((err as Error).message || (window as any).$t('models.err_load_data'), 'error');
        }
    }

    private renderTasks() {
        const tbody = document.getElementById('bindingsTableBody');
        if (!tbody) return;

        const activeModels = this.models.filter((model) => model.is_active);
        const tasks: { type: TaskType; label: string; desc: string }[] = [
            { type: 'chat', label: (window as any).$t('models.task_chat_label'), desc: (window as any).$t('models.task_chat_desc') },
            { type: 'ingestion_llm', label: (window as any).$t('models.task_rag_label'), desc: (window as any).$t('models.task_rag_desc') },
            { type: 'agent', label: (window as any).$t('models.task_agent_label'), desc: (window as any).$t('models.task_agent_desc') },
            { type: 'embedding', label: (window as any).$t('models.task_vector_label'), desc: (window as any).$t('models.task_vector_desc') },
            { type: 'vision', label: (window as any).$t('models.task_vision_label'), desc: (window as any).$t('models.task_vision_desc') },
            { type: 'skill', label: (window as any).$t('models.task_skill_label'), desc: (window as any).$t('models.task_skill_desc') },
        ];

        tbody.innerHTML = tasks
            .map((task) => {
                const currentId = this.bindings[task.type];
                
                // For chat, show more info about multi-select
                let infoContainer = '';
                
                if (task.type === 'chat') {
                    if (this.editingTask === 'chat') {
                        // In edit mode, show checkboxes for all models
                        const checkList = activeModels.map(m => {
                            return `
                            <label class="chat-model-checkbox" style="display:flex; align-items:center; gap:6px; margin-bottom:4px; font-size:12px; cursor:pointer;">
                                <input type="checkbox" ${m.is_chat_enabled ? 'checked' : ''} onchange="window.modelsModule.toggleChatModel('${m.id}')">
                                <span style="white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${m.llm_model_name}">${m.llm_model_name}</span>
                            </label>`;
                        }).join('');

                        infoContainer = `<div style="max-height:120px; overflow-y:auto; border:1px solid var(--border); padding:8px; border-radius:6px; background:var(--bg2);">
                            <div style="font-size:10px; color:var(--text-dim); margin-bottom:6px; text-transform:uppercase; font-weight:700;">${(window as any).$t('models.hint_chat_available')}</div>
                            ${checkList}
                        </div>`;
                    } else {
                        const chatEnabledCount = this.models.filter(m => m.is_chat_enabled && m.is_active).length;
                        infoContainer = `<span class="count-badge">${chatEnabledCount}</span> ${(window as any).$t('models.models_available_suffix')}`;
                    }
                } else {
                    infoContainer = `<span style="color:var(--text-dim); font-size:11px;">${(window as any).$t('models.system_default_hint')}</span>`;
                }

                // Filter dropdown for Chat task: only show chat-enabled models
                const dropdownModels = task.type === 'chat' 
                    ? activeModels.filter(m => m.is_chat_enabled)
                    : activeModels;

                const isCurrentlyEditing = this.editingTask === task.type;

                return `
                <tr id="task-row-${task.type}" class="${isCurrentlyEditing ? 'is-editing' : ''}">
                    <td>
                        <div style="font-weight:600; font-size:14px;">${task.label}</div>
                        <div style="font-size:11px; color:var(--text-dim); margin-top:2px;">${task.desc}</div>
                    </td>
                    <td>
                        <select class="form-select task-binding-select" data-task="${task.type}" ${isCurrentlyEditing ? '' : 'disabled'} style="width:100%; border-radius:8px;">
                            <option value="">${(window as any).$t('models.select_default_model')}</option>
                            ${dropdownModels
                                .map(
                                    (model) =>
                                        `<option value="${model.id}" ${currentId === model.id ? 'selected' : ''}>${model.llm_model_name} - ${model.name} (${model.provider})</option>`
                                )
                                .join('')}
                        </select>
                    </td>
                    <td>
                        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:10px;">
                            ${infoContainer}
                            <div style="display:flex; flex-direction:column; gap:6px;">
                                <button class="btn-binding-toggle ${isCurrentlyEditing ? 'save' : 'edit'}" 
                                        onclick="window.modelsModule.toggleBindingEdit('${task.type}', this)">
                                    ${isCurrentlyEditing ? (window as any).$t('models.action_save') : (window as any).$t('models.action_edit')}
                                </button>
                                ${isCurrentlyEditing ? `
                                <button class="btn-binding-toggle cancel" onclick="window.modelsModule.cancelBindingEdit()">
                                    ${(window as any).$t('models.action_cancel')}
                                </button>` : ''}
                            </div>
                        </div>
                    </td>
                </tr>`;
            })
            .join('');
    }

    public async toggleBindingEdit(taskType: TaskType, _buttonEl: HTMLElement) {
        const isEditing = this.editingTask === taskType;

        if (isEditing) {
            // SAVE MODE
            const row = document.getElementById(`task-row-${taskType}`);
            const select = row?.querySelector('select') as HTMLSelectElement;
            if (!row || !select) return;

            const modelId = select.value;
            if (!modelId) {
                showToast((window as any).$t('models.err_no_model_selected'), 'warning');
                return;
            }

            const success = await this.updateBinding(taskType, modelId);
            if (success) {
                this.editingTask = null;
                await this.refreshData();
            }
        } else {
            // EDIT MODE
            this.editingTask = taskType;
            this.renderTasks();
            
            // Focus the select for better UX
            const targetRow = document.getElementById(`task-row-${taskType}`);
            const targetSelect = targetRow?.querySelector('select') as HTMLSelectElement;
            if (targetSelect) targetSelect.focus();
        }
    }

    public cancelBindingEdit() {
        this.editingTask = null;
        this.renderTasks();
    }

    public async toggleChatModel(modelId: string) {
        try {
            const res = await authFetch(`/api/models/${modelId}/toggle-chat`, {
                method: 'POST'
            });

            if (!res.ok) {
                throw new Error((window as any).$t('models.err_toggle_chat_failed'));
            }

            const updatedModel = await res.json();
            // Update local model state
            const idx = this.models.findIndex(m => m.id === modelId);
            if (idx !== -1) {
                this.models[idx].is_chat_enabled = updatedModel.is_chat_enabled;
            }
            
            const actionLabel = updatedModel.is_chat_enabled ? (window as any).$t('models.action_on') : (window as any).$t('models.action_off');
            showToast((window as any).$t('models.toggle_chat_success', { action: actionLabel }), 'success');
        } catch (err) {
            showToast((err as Error).message, 'error');
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
                throw new Error(await this.readError(res, (window as any).$t('models.err_update_binding_failed')));
            }

            this.bindings[taskType] = modelId;
            showToast((window as any).$t('models.update_binding_success', { task: taskType }), 'success');
            return true;
        } catch (err) {
            showToast((err as Error).message || (window as any).$t('models.err_connection'), 'error');
            return false;
        }
    }

    private renderModels() {
        const grid = document.getElementById('modelsGrid');
        if (!grid) return;

        if (this.models.length === 0) {
            grid.innerHTML =
                `<div style="grid-column: 1/-1; padding: 60px; text-align: center; color: var(--text-dim);"><h3>${(window as any).$t('models.registry_empty_title')}</h3><p>${(window as any).$t('models.registry_empty_sub')}</p></div>`;
            return;
        }

        grid.innerHTML = this.models
            .map((model) => {
                const statusClass = model.is_active ? 'active' : 'inactive';
                const statusLabel = model.is_active ? (window as any).$t('models.status_online') : (window as any).$t('models.status_offline');
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
                            ${isUsedInChat ? `<span class="status-pill chat">${(window as any).$t('models.badge_in_chat')}</span>` : ''}
                            ${model.is_default ? `<span class="status-pill default">${(window as any).$t('models.badge_default')}</span>` : ''}
                        </div>
                    </div>
                </div>
                <div class="mc-body" style="flex:1;">
                    <div style="font-size: 13px; font-weight: 700; color: var(--text); margin-bottom: 4px;">${model.name}</div>
                    <div class="mc-description">${model.description || (window as any).$t('models.no_description')}</div>
                </div>
                <div class="mc-footer">
                    <button class="secondary-btn mini" onclick="window.modelsModule.showModal('${model.id}')">${(window as any).$t('common.config')}</button>
                    <button class="danger-btn mini" onclick="window.modelsModule.confirmDelete('${model.id}')">${(window as any).$t('common.remove')}</button>
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
            title: (window as any).$t('models.confirm_reset_title'),
            message: (window as any).$t('models.confirm_reset_msg'),
            okText: (window as any).$t('models.btn_confirm_reset'),
        });

        if (!confirmed) return;

        try {
            const res = await authFetch('/api/models/reset-defaults', { method: 'POST' });
            if (!res.ok) {
                throw new Error(await this.readError(res, (window as any).$t('models.err_reset_failed')));
            }

            showToast((window as any).$t('models.reset_success'), 'success');
            await this.refreshData();
        } catch (err) {
            showToast((err as Error).message || (window as any).$t('models.err_connection'), 'error');
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
                if (title) title.textContent = (window as any).$t('models.modal_update_title');
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
            title.textContent = (window as any).$t('models.modal_create_title');
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
                throw new Error(await this.readError(res, (window as any).$t('models.err_save_failed')));
            }

            showToast(id ? (window as any).$t('models.save_update_success') : (window as any).$t('models.save_create_success'), 'success');
            this.hideModal();
            await this.refreshData();
        } catch (err) {
            showToast((err as Error).message || (window as any).$t('models.err_connection'), 'error');
        }
    }

    public async confirmDelete(id: string) {
        const confirmed = await kpConfirm({
            title: (window as any).$t('models.confirm_delete_title'),
            message: (window as any).$t('models.confirm_delete_msg'),
            okText: (window as any).$t('models.btn_delete_confirm'),
        });
        if (!confirmed) return;

        try {
            const res = await authFetch(`/api/models/${id}`, {
                method: 'DELETE',
            });

            if (res.status !== 204) {
                throw new Error(await this.readError(res, (window as any).$t('models.err_delete_failed')));
            }

            showToast((window as any).$t('models.delete_success'), 'success');
            await this.refreshData();
        } catch (err) {
            showToast((err as Error).message || (window as any).$t('models.err_connection'), 'error');
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
