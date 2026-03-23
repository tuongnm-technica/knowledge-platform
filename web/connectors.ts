import { API, authFetch } from './client';
import { Config } from './config';
import { ConnectorTab, ConnectorInstance } from './models';
import { escapeHtml, showToast, kpOpenModal, kpConfirm, _kpBuildModalField } from './ui';

interface ConnectorSummary {
    total?: number;
    healthy?: number;
    documents?: number;
    syncing?: number;
}

export class ConnectorsModule {
    private dashboardData: { tabs?: ConnectorTab[] } | null = null;
    private activeTab: string = 'confluence';
    private syncPollTimer: any = null;

    constructor() {
        this.initEvents();
    }

    private initEvents(): void {
        const grid = document.getElementById('connectorsGrid');
        if (grid) {
            grid.addEventListener('click', (e) => {
                const btn = (e.target as HTMLElement).closest('button');
                if (!btn) return;
                
                const action = btn.getAttribute('data-action');
                const type = btn.getAttribute('data-type');
                const id = btn.getAttribute('data-id');
                
                if (!action || !type || !id) return;
                
                if (action === 'sync') this.openSyncModal(type, id);
                else if (action === 'stop') this.stopConnectorInstance(type, id);
                else if (action === 'test') this.testConnection(type, id);
                else if (action === 'delete') this.deleteConnectorInstance(type, id);
                else if (action === 'clear') this.clearConnectorData(type, id);
                else if (action === 'edit') this.openEditModal(type, id);
                else if (action === 'config') this.openConfigModal(type, id);
                else if (action === 'scope') this.openScopeModal(type, id);
                else if (action === 'history') this.openHistoryModal(type, id);
            });
        }

        const addBtn = document.getElementById('addConnectorBtn');
        if (addBtn) {
            addBtn.addEventListener('click', () => this.openCreateModal());
        }
    }

    public async loadConnectorStats(refresh = false): Promise<void> {
        if (this.syncPollTimer) clearTimeout(this.syncPollTimer);

        try {
            const res = await authFetch(`${API}/connectors`);
            if (!res.ok) throw new Error('API failed');
            const data = await res.json() as { summary: ConnectorSummary, tabs?: ConnectorTab[] };
            
            this.dashboardData = data;
            const summary = data.summary || {};
            this.updateSummaryGrid(summary);
            
            this.renderTabs(this.dashboardData?.tabs || []);
            this.renderConnectorGrid(this.dashboardData?.tabs || []);

            if (summary.syncing && summary.syncing > 0) {
                this.syncPollTimer = setTimeout(() => {
                    const page = document.getElementById('page-connectors');
                    if (page && page.classList.contains('active')) {
                        this.loadConnectorStats(true);
                    }
                }, Config.POLLING_INTERVAL_MS);
            }
        } catch (err) {
            const error = err as Error;
            console.error('Lỗi tải connectors:', error);
            if (!refresh) showToast('Không tải được connector stats', 'error');
        }
    }

    private async loadConnectorCatalog(): Promise<void> {
        await this.loadConnectorStats();
    }

    private updateSummaryGrid(summary: ConnectorSummary): void {
        const grid = document.getElementById('connectorsSummaryGrid');
        if (!grid) return;
        grid.innerHTML = `
            <div class="connector-summary-card">
                <span class="summary-label">Total Sources</span>
                <strong class="summary-value">${summary.total || 0}</strong>
                <small class="summary-hint">Nguồn dữ liệu</small>
            </div>
            <div class="connector-summary-card">
                <span class="summary-label">Healthy</span>
                <strong class="summary-value status-healthy">${summary.healthy || 0}</strong>
                <small class="summary-hint">Trạng thái Healthy</small>
            </div>
            <div class="connector-summary-card">
                <span class="summary-label">Documents</span>
                <strong class="summary-value">${(summary.documents || 0).toLocaleString()}</strong>
                <small class="summary-hint">Đã đồng bộ</small>
            </div>
            <div class="connector-summary-card">
                <span class="summary-label">Syncing</span>
                <strong class="summary-value status-syncing">${summary.syncing || 0}</strong>
                <small class="summary-hint">Đang sync (Running)</small>
            </div>
        `;
    }


    public async testConnection(type: string, id: string): Promise<void> {
        showToast(`Đang kiểm tra kết nối ${type}...`, 'info');
        try {
            const res = await authFetch(`${API}/connectors/${type}/instances/${id}/test`, { method: 'POST' });
            if (!res.ok) throw new Error('Kiểm tra kết nối thất bại');
            const data = await res.json() as { status?: string, success?: boolean, message?: string };
            if (data.status === 'ok' || data.success) {
                showToast('Kết nối thành công', 'success');
            } else {
                showToast(`Kết nối thất bại: ${data.message || 'Lỗi không xác định'}`, 'error');
            }
            this.loadConnectorStats(true);
        } catch (err) {
            const error = err as Error;
            showToast(error.message, 'error');
        }
    }

    public async deleteConnectorInstance(type: string, id: string): Promise<void> {
        const confirmed = await kpConfirm({
            title: 'Xác nhận xóa',
            message: `Bạn có chắc muốn xóa kết nối ${type} (ID: ${id})? Toàn bộ dữ liệu liên quan sẽ bị xóa.`,
            danger: true,
            okText: 'Xóa vĩnh viễn'
        });
        if (!confirmed) return;

        try {
            const res = await authFetch(`${API}/connectors/${type}/instances/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Xóa kết nối thất bại');
            showToast('Đã xóa kết nối thành công', 'success');
            this.loadConnectorStats(true);
        } catch (err) {
            const error = err as Error;
            showToast(error.message, 'error');
        }
    }

    public async stopConnectorInstance(type: string, id: string): Promise<void> {
        const confirmed = await kpConfirm({
            title: 'Dừng đồng bộ',
            message: 'Tiến trình đồng bộ đang chạy sẽ được thông báo dừng lại. Có thể mất khoảng 5-10 giây để dừng hoàn toàn.',
            okText: 'Dừng ngay'
        });
        if (!confirmed) return;

        try {
            const res = await authFetch(`${API}/connectors/${type}/instances/${id}/stop`, { method: 'POST' });
            if (!res.ok) throw new Error('Dừng tiến trình thất bại');
            showToast('Đang gửi tín hiệu dừng...', 'success');
            setTimeout(() => this.loadConnectorStats(true), 2000);
        } catch (err) {
            const error = err as Error;
            showToast(error.message, 'error');
        }
    }

    public async clearConnectorData(type: string, _id: string): Promise<void> {
        const confirmed = await kpConfirm({
            title: 'Xóa dữ liệu nguồn này',
            message: 'Tất cả Documents và Chunks liên quan đến kết nối này sẽ bị xoá khỏi hệ thống. Nếu bạn Sync lại, hệ thống sẽ phải cào lại toàn bộ. Bạn có chắc không?',
            danger: true,
            okText: 'Xóa sạch dữ liệu'
        });
        if (!confirmed) return;

        showToast('Đang tiến hành xoá dữ liệu...', 'info');
        try {
            const res = await authFetch(`${API}/connectors/${type}/clear`, { method: 'POST' });
            if (!res.ok) throw new Error('Yêu cầu xoá dữ liệu thất bại');
            showToast('Đã xoá dữ liệu đồng bộ thành công', 'success');
            this.loadConnectorStats(true);
        } catch (err) {
            const error = err as Error;
            showToast(error.message, 'error');
        }
    }

    private renderTabs(tabs: ConnectorTab[]): void {
        const container = document.getElementById('connectorTabs');
        if (!container) return;
        if (!tabs.find(t => t.type === this.activeTab)) this.activeTab = tabs[0]?.type || '';
        container.innerHTML = tabs.map(tab => `
            <div class="connector-tab-btn ${tab.type === this.activeTab ? 'active' : ''}" data-type="${tab.type}">
                ${escapeHtml(tab.label || tab.type)}
            </div>
        `).join('');

        container.querySelectorAll('.connector-tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const type = (e.currentTarget as HTMLElement).getAttribute('data-type');
                if (type) this.switchTab(type);
            });
        });
    }

    private switchTab(type: string): void {
        this.activeTab = type;
        if (this.dashboardData) {
            this.renderTabs(this.dashboardData.tabs || []);
            this.renderConnectorGrid(this.dashboardData.tabs || []);
        } else {
            this.loadConnectorCatalog();
        }
    }

    private renderConnectorGrid(tabs: ConnectorTab[]): void {
        const list = document.getElementById('connectorsGrid');
        if (!list) return;

        const currentTab = tabs.find(t => t.type === this.activeTab);

        if (!currentTab?.instances?.length) {
            list.innerHTML = `<div class="connectors-empty">Chưa có hệ thống ${escapeHtml(this.activeTab)} nào được kết nối. Bấm "+ Thêm kết nối" để bắt đầu.</div>`;
            list.className = 'connectors-grid';
            return;
        }

        list.className = 'connectors-grid connectors-grid-rich';
        list.innerHTML = currentTab.instances.map(inst => this.renderConnectorCard(inst)).join('');
    }

    private renderConnectorCard(inst: ConnectorInstance): string {
        const status = inst.status || {};
        const data   = inst.data || {};
        const type   = inst.connector_type || '';
        const iid    = inst.instance_id;
        const docsVal = (data.documents || 0).toLocaleString();
        const chunksVal = (data.chunks || 0).toLocaleString();
        
        const isRunning = inst.sync?.running || status.code === 'syncing';
        const currentRun: any = inst.sync?.latest_run || null;
        const latestRun = inst.sync?.latest_completed_run;

        let badgeClass = status.code || 'neutral';
        if (isRunning) badgeClass = 'syncing';
        else if (badgeClass === 'ok') badgeClass = 'connected';

        let icon = '🔗';
        if (type === 'confluence') icon = '📘';
        else if (type === 'jira') icon = '🎫';
        else if (type === 'slack') icon = '💬';
        else if (type === 'file_server') icon = '📁';

        let desc = inst.base_url || type;
        if (type === 'file_server' && inst.config.extra) {
            const ex = inst.config.extra;
            desc = `${ex.host || ''} (${ex.share || ''})`;
        }

        let progressHtml = '';
        if (isRunning) {
            let pct = -1; // Trạng thái chưa rõ (Indeterminate)
            let text = 'Đang khởi tạo đồng bộ...';
            
            if (currentRun && currentRun.fetched > 0) {
                const fetched = currentRun.fetched || 0;
                const indexed = currentRun.indexed || 0;
                pct = Math.round((indexed / fetched) * 100);
                if (pct > 100) pct = 100;
                text = `Đang đồng bộ: ${pct}% (${indexed.toLocaleString()}/${fetched.toLocaleString()})`;
            } else if (currentRun && currentRun.fetched === 0 && currentRun.indexed > 0) {
                text = `Đang xử lý... (Đã index: ${currentRun.indexed.toLocaleString()})`;
            }

            progressHtml = `
                <div class="sync-progress-wrap">
                    <div class="sync-progress-bar ${pct < 0 ? 'indeterminate' : ''}" style="width: ${pct < 0 ? '40' : pct}%"></div>
                </div>
                <div class="sync-progress-text"><span class="spin">🔄</span> ${escapeHtml(text)}</div>
            `;
        }

        return `
            <article class="connector-card-rich accent-${escapeHtml(type)}">
                ${isRunning ? progressHtml : ''}
                <div class="connector-card-top">
                    <div class="connector-header-left">
                        <div class="connector-icon">${icon}</div>
                        <div class="connector-info">
                            <div class="connector-card-name">${escapeHtml(inst.instance_name)}</div>
                            <div class="connector-card-url" title="${escapeHtml(desc)}">${escapeHtml(desc)}</div>
                        </div>
                    </div>
                </div>
                <div class="connector-body">
                    <div class="connector-config-grid">
                        <div class="connector-status-badge ${badgeClass}">
                            <div class="status-dot-sm"></div>
                            <span>${escapeHtml(status.label || status.code || '—')}</span>
                        </div>
                        <div class="connector-config-item">
                            <span>Sync</span><strong>${inst.state?.auto_sync ? '🕐 Auto' : '⛔ Manual'}</strong>
                        </div>
                    </div>
                    <div class="connector-stats">
                        <div class="stat-item">
                            <div class="stat-value">${docsVal}</div>
                            <div class="stat-label">Tổng số</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-value">${chunksVal}</div>
                            <div class="stat-label">Chunks</div>
                        </div>
                        <div class="stat-item" title="Đồng bộ gần nhất">
                            <div class="stat-value small-text">${latestRun?.finished_at ? new Date(latestRun.finished_at).toLocaleDateString('vi-VN') : '—'}</div>
                            <div class="stat-label">Last Sync</div>
                        </div>
                    </div>
                    ${latestRun ? `
                        <div class="connector-latest-run-summary">
                            <span class="run-summary-text">Mới nhất: <strong class="highlight">+${latestRun.indexed || 0}</strong>/${latestRun.fetched || 0} docs</span>
                            ${latestRun.errors > 0 ? `<span class="run-summary-error">⚠️ ${latestRun.errors} lỗi</span>` : ''}
                        </div>
                    ` : ''}
                </div>
                <div class="connector-actions-row">
                    ${isRunning 
                        ? `<button class="primary-btn mini action-stop" data-action="stop" data-type="${type}" data-id="${iid}" style="background-color: var(--danger-color); border-color: var(--danger-color);" title="Dừng đồng bộ">⛔ Stop</button>`
                        : `<button class="primary-btn mini action-sync" data-action="sync" data-type="${type}" data-id="${iid}" title="Sync">🔄 Sync</button>`
                    }
                    <button class="secondary-btn mini action-icon" data-action="test" data-type="${type}" data-id="${iid}" title="Test Connection">🔌</button>
                    <button class="secondary-btn mini action-icon" data-action="config" data-type="${type}" data-id="${iid}" title="Schedule & Automation">⚙️</button>
                    <button class="secondary-btn mini action-icon" data-action="edit" data-type="${type}" data-id="${iid}" title="Sửa thông tin kết nối">✏️</button>
                    <button class="secondary-btn mini action-icon" data-action="scope" data-type="${type}" data-id="${iid}" title="Quản lý Scope (${escapeHtml(inst.config.scope_label || 'Items')})">🔍</button>
                    <button class="secondary-btn mini action-icon" data-action="history" data-type="${type}" data-id="${iid}" title="Xem lịch sử đồng bộ">🕒</button>
                    <button class="danger-btn mini action-icon" data-action="clear" data-type="${type}" data-id="${iid}" title="Clear Data (Xóa dữ liệu đã tải)">🧹</button>
                    <button class="danger-btn mini action-icon" data-action="delete" data-type="${type}" data-id="${iid}" title="Xóa kết nối">🗑</button>
                </div>
            </article>
        `;
    }

    // --- Modal Actions ---

    private async openSyncModal(type: string, id: string): Promise<void> {
        const inst = this.findInstance(type, id);
        if (!inst) return;

        const body = document.createElement('div');
        body.className = 'sync-modal-content';
        body.innerHTML = `
            <div class="modal-intro">
                Chọn chế độ đồng bộ cho <strong>${escapeHtml(inst.instance_name)}</strong>:
            </div>
            <div class="sync-options">
                <label class="sync-option-card active">
                    <input type="radio" name="syncMode" value="incremental" checked>
                    <div class="option-body">
                        <div class="option-title highlight">▶ Tiếp tục / Cập nhật mới (Khuyên dùng)</div>
                        <div class="option-desc">Chỉ lấy các dữ liệu mới tạo hoặc bị sửa đổi kể từ lần đồng bộ thành công gần nhất. <br><b>Phù hợp để Resume</b> nếu lần chạy trước bị dừng hoặc lỗi giữa chừng.</div>
                    </div>
                </label>
                <label class="sync-option-card">
                    <input type="radio" name="syncMode" value="full">
                    <div class="option-body">
                        <div class="option-title">🔄 Đồng bộ lại từ đầu (Full Sync)</div>
                        <div class="option-desc">Bỏ qua lịch sử cũ, quét lại toàn bộ kho dữ liệu từ con số 0. Quá trình này sẽ mất nhiều thời gian hơn rất nhiều.</div>
                    </div>
                </label>
            </div>
        `;

        // Add visual feedback for radio selection
        body.querySelectorAll('input[name="syncMode"]').forEach(input => {
            input.addEventListener('change', (e) => {
                body.querySelectorAll('.sync-option-card').forEach(card => card.classList.remove('active'));
                (e.target as HTMLElement).closest('.sync-option-card')?.classList.add('active');
            });
        });

        await kpOpenModal({
            title: '🚀 Khởi chạy Đồng bộ',
            content: body,
            okText: 'Bắt đầu',
            onOk: async () => {
                const mode = (body.querySelector('input[name="syncMode"]:checked') as HTMLInputElement).value;
                const forceFull = mode === 'full';
                
                showToast(`Đang yêu cầu đồng bộ ${type}...`, 'info');
                try {
                    const res = await authFetch(`${API}/connectors/${type}/instances/${id}/sync`, { 
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ force_full: forceFull })
                    });
                    if (!res.ok) throw new Error('Yêu cầu đồng bộ thất bại');
                    showToast('Đã bắt đầu tiến trình đồng bộ', 'success');
                    setTimeout(() => this.loadConnectorStats(true), 1000);
                    return true;
                } catch (err) {
                    const error = err as Error;
                    return { error: error.message };
                }
            }
        });
    }

    private openHistoryModal(type: string, id: string): void {
        const inst = this.findInstance(type, id);
        if (!inst) return;

        const history = inst.sync?.history || [];
        const body = document.createElement('div');

        if (history.length === 0) {
            body.innerHTML = '<div class="connectors-empty">Chưa có lịch sử đồng bộ nào.</div>';
        } else {
            let html = '<div class="connector-history-list">';
            history.forEach((run: any) => {
                let statusClass = 'status-running';
                let statusText = 'Đang chạy';
                if (run.status === 'completed') { statusClass = 'status-success'; statusText = 'Thành công'; }
                else if (run.status === 'failed') { statusClass = 'status-failed'; statusText = 'Lỗi/Dừng'; }

                const startTime = run.started_at ? new Date(run.started_at).toLocaleString('vi-VN') : '—';
                const endTime = run.finished_at ? new Date(run.finished_at).toLocaleString('vi-VN') : '—';

                html += `
                    <div class="history-item">
                        <div class="history-head">
                            <div class="history-id">Tiến trình #${run.id}</div>
                            <div class="history-status-badge ${statusClass}">${statusText}</div>
                        </div>
                        <div class="history-times">
                            <div class="time-row">Bắt đầu: <strong class="time-val">${startTime}</strong></div>
                            <div class="time-row">Kết thúc: <strong class="time-val">${endTime}</strong></div>
                        </div>
                        <div class="history-metrics">
                            <div class="metric-col">
                                <span class="metric-label">Lấy về (Fetch):</span>
                                <strong class="metric-val">${run.fetched || 0}</strong>
                            </div>
                            <div class="metric-col">
                                <span class="metric-label">Đã index:</span>
                                <strong class="metric-val">${run.indexed || 0}</strong>
                            </div>
                            <div class="metric-col">
                                <span class="metric-label">Số lỗi:</span>
                                <strong class="metric-val ${run.errors > 0 ? 'error' : ''}">${run.errors || 0}</strong>
                            </div>
                        </div>
                    </div>
                `;
            });
            html += '</div>';
            body.innerHTML = html;
        }

        kpOpenModal({
            title: `🕒 Lịch sử đồng bộ: ${inst.instance_name}`,
            content: body,
            okText: 'Đóng',
            cancelText: null
        });
    }

    private async openCreateModal(): Promise<void> {
        const body = document.createElement('div');
        body.style.display = 'flex';
        body.style.flexDirection = 'column';
        body.style.gap = '12px';

        const { wrap: typeWrap, input: typeInput } = _kpBuildModalField({
            id: 'connType', label: 'Loại kết nối', type: 'select', value: this.activeTab,
            options: [
                { value: 'confluence', label: 'Confluence' },
                { value: 'jira', label: 'Jira' },
                { value: 'slack', label: 'Slack' },
                { value: 'file_server', label: 'File Server (SMB)' }
            ]
        });
        const { wrap: nameWrap, input: nameInput } = _kpBuildModalField({
            id: 'connName', label: 'Tên gợi nhớ', placeholder: 'VD: Production Confluence', required: true
        });

        const dynamicContainer = document.createElement('div');
        dynamicContainer.style.display = 'flex';
        dynamicContainer.style.flexDirection = 'column';
        dynamicContainer.style.gap = '12px';

        const updateFields = () => {
            const type = (typeInput as HTMLSelectElement).value;
            dynamicContainer.innerHTML = '';

            if (type === 'file_server') {
                const { wrap: hostWrap } = _kpBuildModalField({ id: 'connHost', label: 'Host / IP', placeholder: '192.168.1.100' });
                const { wrap: shareWrap } = _kpBuildModalField({ id: 'connShare', label: 'Share Name', placeholder: 'Documents' });
                const { wrap: pathWrap } = _kpBuildModalField({ id: 'connPath', label: 'Base Path (optional)', placeholder: '\\Folder' });
                dynamicContainer.append(hostWrap, shareWrap, pathWrap);
            } else if (type !== 'slack') {
                const { wrap: urlWrap } = _kpBuildModalField({ id: 'connUrl', label: 'Base URL', placeholder: 'https://domain.atlassian.net' });
                dynamicContainer.append(urlWrap);
            }

            const { wrap: authWrap, input: authInput } = _kpBuildModalField({
                id: 'connAuth', label: 'Auth Type', type: 'select', value: 'token',
                options: [
                    { value: 'token', label: 'Token / API Key' },
                    { value: 'basic', label: 'Username + Password/Token' }
                ]
            });
            dynamicContainer.append(authWrap);

            const userRow = document.createElement('div');
            userRow.id = 'userRow';
            userRow.style.display = 'none';
            const { wrap: userWrap } = _kpBuildModalField({ id: 'connUser', label: 'Username', placeholder: 'email@domain.com' });
            userRow.append(userWrap);
            dynamicContainer.append(userRow);

            const secretLabel = type === 'slack' ? 'Bot Token' : 'Password / Token';
            const { wrap: secretWrap } = _kpBuildModalField({ 
                id: 'connSecret', label: secretLabel, type: 'password', placeholder: '••••••••' 
            });
            dynamicContainer.append(secretWrap);

            authInput.addEventListener('change', () => {
                userRow.style.display = (authInput as HTMLSelectElement).value === 'basic' ? 'block' : 'none';
            });
            // Trigger initial state
            userRow.style.display = (authInput as HTMLSelectElement).value === 'basic' ? 'block' : 'none';
        };

        typeInput.addEventListener('change', updateFields);
        updateFields();

        body.append(typeWrap, nameWrap, dynamicContainer);

        await kpOpenModal({
            title: '➕ Thêm kết nối mới',
            content: body,
            okText: 'Tạo kết nối',
            onOk: async () => {
                const type = (typeInput as HTMLSelectElement).value;
                const name = (nameInput as HTMLInputElement).value.trim();
                if (!name) return { error: 'Vui lòng nhập tên kết nối' };

                const auth_type = (body.querySelector('#connAuth') as HTMLSelectElement).value;
                const username = (body.querySelector('#connUser') as HTMLInputElement).value.trim();
                const secret = (body.querySelector('#connSecret') as HTMLInputElement).value.trim();
                
                let base_url = '';
                let extra: any = {};

                if (type === 'file_server') {
                    const host = (body.querySelector('#connHost') as HTMLInputElement).value.trim();
                    const share = (body.querySelector('#connShare') as HTMLInputElement).value.trim();
                    const path = (body.querySelector('#connPath') as HTMLInputElement).value.trim();
                    base_url = `\\\\${host}\\${share}`;
                    extra = { host, share, base_path: path };
                } else if (type !== 'slack') {
                    base_url = (body.querySelector('#connUrl') as HTMLInputElement)?.value.trim() || '';
                }

                try {
                    const res = await authFetch(`${API}/connectors/${type}/instances`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, base_url, auth_type, username, secret, extra })
                    });
                    if (!res.ok) throw new Error('Không thể tạo kết nối');
                    showToast('Đã thêm kết nối mới', 'success');
                    this.loadConnectorStats(true);
                    return true;
                } catch (e) {
                    return { error: (e as Error).message };
                }
            }
        });
    }

    private async openEditModal(type: string, id: string): Promise<void> {
        const inst = this.findInstance(type, id);
        if (!inst) return;

        const body = document.createElement('div');
        body.style.display = 'flex';
        body.style.flexDirection = 'column';
        body.style.gap = '12px';

        const { wrap: nameWrap, input: nameInput } = _kpBuildModalField({
            id: 'editName', label: 'Tên kết nối', value: inst.instance_name, required: true
        });
        body.append(nameWrap);

        if (type === 'file_server') {
            const ex = inst.config.extra || {};
            const { wrap: hostWrap } = _kpBuildModalField({ id: 'editHost', label: 'Host / IP', value: ex.host || '' });
            const { wrap: shareWrap } = _kpBuildModalField({ id: 'editShare', label: 'Share Name', value: ex.share || '' });
            const { wrap: pathWrap } = _kpBuildModalField({ id: 'editPath', label: 'Base Path', value: ex.base_path || '' });
            body.append(hostWrap, shareWrap, pathWrap);
        } else if (type !== 'slack') {
            const { wrap: urlWrap } = _kpBuildModalField({ id: 'editUrl', label: 'Base URL', value: inst.base_url || '' });
            body.append(urlWrap);
        }

        const { wrap: authWrap, input: authInput } = _kpBuildModalField({
            id: 'editAuth', label: 'Auth Type', type: 'select', value: inst.config.auth_type || 'token',
            options: [{ value: 'token', label: 'Token / API Key' }, { value: 'basic', label: 'Username + Password/Token' }]
        });
        body.append(authWrap);

        const userRow = document.createElement('div');
        userRow.style.display = inst.config.auth_type === 'basic' ? 'block' : 'none';
        const { wrap: userWrap, input: userInput } = _kpBuildModalField({ id: 'editUser', label: 'Username', value: inst.config.username || '' });
        userRow.append(userWrap);
        body.append(userRow);

        const { wrap: secretWrap } = _kpBuildModalField({
            id: 'editSecret', label: 'Secret Key / Token', type: 'password', placeholder: 'Bỏ trống nếu không đổi'
        });
        body.append(secretWrap);

        authInput.addEventListener('change', () => {
            userRow.style.display = (authInput as HTMLSelectElement).value === 'basic' ? 'block' : 'none';
        });

        await kpOpenModal({
            title: `✏️ Chỉnh sửa: ${inst.instance_name}`,
            content: body,
            okText: 'Lưu thay đổi',
            onOk: async () => {
                const name = (nameInput as HTMLInputElement).value.trim();
                const auth_type = (authInput as HTMLSelectElement).value;
                const username = (userInput as HTMLInputElement).value.trim();
                const secret = (body.querySelector('#editSecret') as HTMLInputElement).value.trim();

                let base_url = inst.base_url;
                let extra = inst.config.extra || {};

                if (type === 'file_server') {
                    const host = (body.querySelector('#editHost') as HTMLInputElement).value.trim();
                    const share = (body.querySelector('#editShare') as HTMLInputElement).value.trim();
                    const path = (body.querySelector('#editPath') as HTMLInputElement).value.trim();
                    base_url = `\\\\${host}\\${share}`;
                    extra = { ...extra, host, share, base_path: path };
                } else if (type !== 'slack') {
                    base_url = (body.querySelector('#editUrl') as HTMLInputElement)?.value.trim() || '';
                }

                const payload: any = { name, base_url, auth_type, username, extra };
                if (secret) payload.secret = secret;

                try {
                    const res = await authFetch(`${API}/connectors/${type}/instances/${id}`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(payload)
                    });
                    if (!res.ok) throw new Error('Cập nhật thất bại');
                    showToast('Đã lưu thông tin', 'success');
                    this.loadConnectorStats(true);
                    return true;
                } catch (e) {
                    return { error: (e as Error).message };
                }
            }
        });
    }

    private async openConfigModal(type: string, id: string): Promise<void> {
        const inst = this.findInstance(type, id);
        if (!inst) return;

        const body = document.createElement('div');
        body.style.display = 'flex';
        body.style.flexDirection = 'column';
        body.style.gap = '16px';

        const { wrap: autoWrap, input: autoInput } = _kpBuildModalField({
            id: 'cfgAuto', label: 'Tự động đồng bộ', type: 'select', value: inst.state.auto_sync ? 'true' : 'false',
            options: [{ value: 'true', label: 'Bật (On)' }, { value: 'false', label: 'Tắt (Off)' }]
        });
        
        const hourRow = document.createElement('div');
        hourRow.style.display = 'flex';
        hourRow.style.gap = '12px';
        
        const { wrap: hWrap, input: hInput } = _kpBuildModalField({
            id: 'cfgHour', label: 'Giờ (0-23)', type: 'number', value: inst.state.schedule_hour ?? 2
        });
        const { wrap: mWrap, input: mInput } = _kpBuildModalField({
            id: 'cfgMin', label: 'Phút (0-59)', type: 'number', value: inst.state.schedule_minute ?? 0
        });
        
        hourRow.append(hWrap, mWrap);
        body.append(autoWrap, hourRow);

        await kpOpenModal({
            title: `⚙️ Cấu hình Automation: ${inst.instance_name}`,
            content: body,
            okText: 'Lưu cấu hình',
            onOk: async () => {
                const auto_sync = (autoInput as HTMLSelectElement).value === 'true';
                const hour = parseInt((hInput as HTMLInputElement).value) || 0;
                const minute = parseInt((mInput as HTMLInputElement).value) || 0;

                try {
                    const res = await authFetch(`${API}/connectors/${type}/instances/${id}/config`, {
                        method: 'PUT',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ auto_sync, schedule_hour: hour, schedule_minute: minute })
                    });
                    if (!res.ok) throw new Error('Lưu cấu hình thất bại');
                    showToast('Đã cập nhật cấu hình', 'success');
                    this.loadConnectorStats(true);
                    return true;
                } catch (e) {
                    return { error: (e as Error).message };
                }
            }
        });
    }

    private async openScopeModal(type: string, id: string): Promise<void> {
        const inst = this.findInstance(type, id);
        if (!inst) return;

        const scopeLabel = inst.config.scope_label || 'Items';
        const currentSelection = inst.state.selection || {};
        const currentScope: string[] = currentSelection.spaces || currentSelection.projects || currentSelection.channels || currentSelection.folders || [];

        showToast(`Đang tải danh sách ${scopeLabel}...`, 'info');
        
        let availableScopes: any[] = [];
        let discoverFailed = false;

        try {
            const res = await authFetch(`${API}/connectors/${type}/instances/${id}/discover`);
            if (!res.ok) throw new Error('API failed');
            const data = await res.json();
            availableScopes = data.scopes || data.items || (Array.isArray(data) ? data : []);
        } catch (e) {
            console.warn("Discover scopes failed", e);
            discoverFailed = true;
        }

        const body = document.createElement('div');
        
        const handleSave = async (list: string[]) => {
            const selection: any = {};
            if (type === 'confluence') selection.spaces = list;
            else if (type === 'jira') selection.projects = list;
            else if (type === 'slack') selection.channels = list;
            else if (type === 'file_server') selection.folders = list;

            try {
                const res = await authFetch(`${API}/connectors/${type}/instances/${id}/config`, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ selection })
                });
                if (!res.ok) throw new Error('Cập nhật scope thất bại');
                showToast('Đã cập nhật phạm vi đồng bộ', 'success');
                this.loadConnectorStats(true);
                return true;
            } catch (e) {
                return { error: (e as Error).message };
            }
        };

        if (discoverFailed || availableScopes.length === 0) {
            const scopeText = Array.isArray(currentScope) ? currentScope.join(', ') : '';
            body.innerHTML = `
                <div style="margin-bottom:12px; font-size:13px; color:var(--text-dim);">
                    Không thể lấy danh sách tự động. Nhập danh sách <strong>${escapeHtml(scopeLabel)}</strong> cách nhau bằng dấu phẩy.
                    Để trống nếu muốn đồng bộ tất cả.
                </div>
            `;
            const { wrap: sWrap, input: sInput } = _kpBuildModalField({
                id: 'scopeInput', label: scopeLabel, type: 'textarea', value: scopeText,
                placeholder: 'VD: PROJ-A, PROJ-B'
            });
            body.append(sWrap);

            await kpOpenModal({
                title: `🔍 Cấu hình phạm vi (Scope): ${inst.instance_name}`,
                content: body,
                okText: 'Cập nhật Scope',
                onOk: async () => {
                    const text = (sInput as HTMLTextAreaElement).value.trim();
                    const list = text ? text.split(',').map(s => s.trim()).filter(Boolean) : [];
                    return handleSave(list);
                }
            });
        } else {
            body.innerHTML = `
                <div style="margin-bottom:12px; font-size:13px; color:var(--text-dim);">
                    Chọn các <strong>${escapeHtml(scopeLabel)}</strong> để giới hạn phạm vi đồng bộ. 
                    Bỏ chọn tất cả nếu muốn đồng bộ toàn bộ mặc định.
                </div>
            `;
            
            const listContainer = document.createElement('div');
            listContainer.className = 'connector-scope-list';
            
            for (const item of availableScopes) {
                const itemId = String(item.id || item.key || item.name || item);
                const itemName = String(item.name || item.label || itemId);
                const isChecked = currentScope.includes(itemId);
                
                const label = document.createElement('label');
                label.className = 'scope-item';
                label.style.cursor = 'pointer';
                label.innerHTML = `
                    <input type="checkbox" class="scope-cb" value="${escapeHtml(itemId)}" ${isChecked ? 'checked' : ''}>
                    <span style="word-break:break-all">${escapeHtml(itemName)}</span>
                `;
                listContainer.append(label);
            }
            
            body.append(listContainer);

            await kpOpenModal({
                title: `🔍 Chọn phạm vi (Scope): ${inst.instance_name}`,
                content: body,
                okText: 'Lưu thay đổi',
                onOk: async () => {
                    const checkboxes = body.querySelectorAll('.scope-cb:checked') as NodeListOf<HTMLInputElement>;
                    const list = Array.from(checkboxes).map(cb => cb.value);
                    return handleSave(list);
                }
            });
        }
    }

    // --- Helpers ---

    private findInstance(type: string, id: string): ConnectorInstance | null {
        if (!this.dashboardData?.tabs) return null;
        const tab = this.dashboardData.tabs.find(t => t.type === type);
        return tab?.instances?.find(i => i.instance_id === id) || null;
    }
}