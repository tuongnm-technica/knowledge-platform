import { authFetch } from './client';
import { LLMModel, TaskType, ModelBindings } from './models';
import { showToast } from './ui';

export class ModelsModule {
    private models: LLMModel[] = [];
    private bindings: ModelBindings = {
        chat: '',
        ingestion_llm: '',
        agent: '',
        embedding: ''
    };

    constructor() {}

    public async init() {
        this.bindEvents();
        await this.refreshData();
    }

    private bindEvents() {
        const addBtn = document.getElementById('addModelBtn');
        if (addBtn) {
            addBtn.onclick = () => this.showModal();
        }

        const modelForm = document.getElementById('modelForm') as HTMLFormElement;
        if (modelForm) {
            modelForm.onsubmit = (e) => {
                e.preventDefault();
                this.handleSaveModel();
            };
        }

        const closeModalBtns = document.querySelectorAll('.close-modal');
        closeModalBtns.forEach(btn => {
            (btn as HTMLElement).onclick = () => this.hideModal();
        });

        // Provider change logic
        const providerSelect = document.getElementById('m-provider') as HTMLSelectElement;
        if (providerSelect) {
            providerSelect.onchange = () => this.toggleProviderFields();
        }

        // Filter logic
        const filterSelect = document.getElementById('providerFilter') as HTMLSelectElement;
        if (filterSelect) {
            filterSelect.onchange = () => this.renderModels();
        }
    }

    private async refreshData() {
        try {
            const [modelsRes, bindingsRes] = await Promise.all([
                authFetch('/api/models/admin'),
                authFetch('/api/models/bindings')
            ]);

            if (modelsRes.ok) this.models = await modelsRes.json();
            if (bindingsRes.ok) this.bindings = await bindingsRes.json();

            this.renderBindings();
            this.renderModels();
        } catch (err) {
            console.error('Failed to fetch models data', err);
            showToast('Không thể tải dữ liệu models', 'error');
        }
    }

    private renderBindings() {
        const grid = document.getElementById('bindingsGrid');
        if (!grid) return;

        const tasks: { type: TaskType, label: string, icon: string }[] = [
            { type: 'chat', label: 'Hội thoại (Chat)', icon: '💬' },
            { type: 'ingestion_llm', label: 'Xử lý dữ liệu (Ingestion)', icon: '📥' },
            { type: 'agent', label: 'Suy luận Agent (ReAct)', icon: '🕵️' },
            { type: 'embedding', label: 'Vector hóa (Embedding)', icon: '🧬' }
        ];

        grid.innerHTML = tasks.map(task => `
            <div class="binding-card" data-task="${task.type}">
                <div class="binding-label">
                    <span class="binding-icon">${task.icon}</span> ${task.label}
                </div>
                <div class="binding-select-wrapper">
                    <select class="binding-select" onchange="window.modelsModule.updateBinding('${task.type}', this.value)">
                        <option value="">-- Chọn Model --</option>
                        ${this.models
                            .filter(m => m.is_active)
                            .map(m => `<option value="${m.id}" ${this.bindings[task.type] === m.id ? 'selected' : ''}>${m.name} (${m.provider})</option>`)
                            .join('')}
                    </select>
                </div>
            </div>
        `).join('');

        // Expose to window for inline onchange
        (window as any).modelsModule = this;
    }

    public async updateBinding(taskType: TaskType, modelId: string) {
        if (!modelId) return;
        
        try {
            const res = await authFetch(`/api/models/bindings/${taskType}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ model_id: modelId })
            });

            if (res.ok) {
                showToast(`Đã cập nhật model cho tác vụ ${taskType}`, 'success');
                this.bindings[taskType] = modelId;
            } else {
                showToast('Lỗi khi cập nhật liên kết', 'error');
            }
        } catch (err) {
            showToast('Lỗi kết nối', 'error');
        }
    }

    private renderModels() {
        const grid = document.getElementById('modelsGrid');
        const filter = (document.getElementById('providerFilter') as HTMLSelectElement)?.value || 'all';
        if (!grid) return;

        const filtered = filter === 'all' ? this.models : this.models.filter(m => m.provider === filter);

        if (filtered.length === 0) {
            grid.innerHTML = '<div class="empty-state"><h3>Không có model nào phù hợp</h3></div>';
            return;
        }

        grid.innerHTML = filtered.map(m => `
            <div class="model-card ${m.is_default ? 'is-default' : ''}">
                <div class="model-header">
                    <div class="model-info">
                        <h3>${m.name}</h3>
                        <div class="model-provider">
                            <span class="provider-tag ${m.provider}">${m.provider}</span>
                        </div>
                    </div>
                    <div class="model-status-badges">
                        ${m.is_default ? '<span class="badge primary">Mặc định</span>' : ''}
                        <span class="badge ${m.is_active ? 'success' : 'warning'}">${m.is_active ? 'Hoạt động' : 'Tắt'}</span>
                    </div>
                </div>
                <div class="model-body">
                    <p>${m.description || 'Không có mô tả'}</p>
                    <code class="model-technical">${m.llm_model_name}</code>
                    ${m.base_url ? `<div style="font-size: 0.8rem; margin-top:5px; color:var(--text-dim)">URL: ${m.base_url}</div>` : ''}
                </div>
                <div class="model-actions">
                    <button class="btn btn-secondary sm" onclick="window.modelsModule.showModal('${m.id}')">Sửa</button>
                    ${!m.is_default ? `<button class="btn btn-outline sm" onclick="window.modelsModule.toggleDefault('${m.id}')">Đặt Mặc định</button>` : ''}
                    <button class="btn btn-danger sm" onclick="window.modelsModule.confirmDelete('${m.id}')">Xóa</button>
                </div>
            </div>
        `).join('');
    }

    public showModal(id?: string) {
        const modal = document.getElementById('modelModal');
        const title = document.getElementById('modalTitle');
        const form = document.getElementById('modelForm') as HTMLFormElement;
        
        form.reset();
        (document.getElementById('modelId') as HTMLInputElement).value = id || '';
        
        if (id) {
            const m = this.models.find(x => x.id === id);
            if (m) {
                if (title) title.textContent = 'Chỉnh sửa Model';
                (document.getElementById('m-name') as HTMLInputElement).value = m.name;
                (document.getElementById('m-provider') as HTMLSelectElement).value = m.provider;
                (document.getElementById('m-model-name') as HTMLInputElement).value = m.llm_model_name;
                (document.getElementById('m-description') as HTMLTextAreaElement).value = m.description || '';
                (document.getElementById('m-base-url') as HTMLInputElement).value = m.base_url || '';
                (document.getElementById('m-api-key') as HTMLInputElement).value = m.api_key || '';
                (document.getElementById('m-active') as HTMLInputElement).checked = m.is_active;
                (document.getElementById('m-default') as HTMLInputElement).checked = m.is_default;
            }
        } else {
            if (title) title.textContent = 'Thêm Model Mới';
        }

        this.toggleProviderFields();
        if (modal) modal.style.display = 'flex';
    }

    private hideModal() {
        const modal = document.getElementById('modelModal');
        if (modal) modal.style.display = 'none';
    }

    private toggleProviderFields() {
        const provider = (document.getElementById('m-provider') as HTMLSelectElement).value;
        const urlGroup = document.getElementById('url-group');
        const keyGroup = document.getElementById('key-group');

        if (urlGroup) urlGroup.style.display = (provider === 'ollama' || provider === 'vllm') ? 'block' : 'none';
        if (keyGroup) keyGroup.style.display = (provider !== 'ollama') ? 'block' : 'none';
    }

    private async handleSaveModel() {
        const id = (document.getElementById('modelId') as HTMLInputElement).value;
        const form = document.getElementById('modelForm') as HTMLFormElement;
        const formData = new FormData(form);
        
        const payload: any = {};
        formData.forEach((value, key) => {
            if (key === 'is_active' || key === 'is_default') {
                payload[key] = true;
            } else {
                payload[key] = value;
            }
        });
        
        // Handle checkboxes not in formData if unchecked
        if (!formData.has('is_active')) payload.is_active = false;
        if (!formData.has('is_default')) payload.is_default = false;

        try {
            const url = id ? `/api/models/${id}` : '/api/models';
            const method = id ? 'PATCH' : 'POST';
            
            const res = await authFetch(url, {
                method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                showToast(id ? 'Đã cập nhật model' : 'Đã thêm model mới', 'success');
                this.hideModal();
                await this.refreshData();
            } else {
                const err = await res.json();
                showToast(`Lỗi: ${err.detail || 'Không thể lưu'}`, 'error');
            }
        } catch (err) {
            showToast('Lỗi kết nối', 'error');
        }
    }

    public async toggleDefault(id: string) {
        try {
            const res = await authFetch(`/api/models/${id}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_default: true })
            });

            if (res.ok) {
                showToast('Đã đổi model mặc định', 'success');
                await this.refreshData();
            }
        } catch (err) {
            showToast('Lỗi kết nối', 'error');
        }
    }

    public async confirmDelete(id: string) {
        if (!confirm('Bạn có chắc chắn muốn xóa model này? Đang dùng model này cho các task sẽ bị mất liên kết.')) return;
        
        try {
            const res = await authFetch(`/api/models/${id}`, {
                method: 'DELETE'
            });

            if (res.status === 204) {
                showToast('Đã xóa model', 'success');
                await this.refreshData();
            }
        } catch (err) {
            showToast('Lỗi kết nối', 'error');
        }
    }
}
