import { API, authFetch } from './client';
import { ConnectorTab, ConnectorInstance } from './models';
import { escapeHtml, showToast, kpConfirm, kpOpenModal, _kpBuildModalField } from './ui';

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
                
                if (action === 'sync') (this as any).syncConnector(type, id);
                else if (action === 'test') (this as any).testConnection(type, id);
                else if (action === 'delete') (this as any).deleteConnectorInstance(type, id);
            });
        }
    }

    public async loadConnectorStats(refresh = false): Promise<void> {
        if (this.syncPollTimer) clearTimeout(this.syncPollTimer);

        try {
            const res = await authFetch(`${API}/connectors/stats`);
            if (!res.ok) throw new Error('Stats API failed');
            const data = await res.json();
            const summary = data.summary || {};
            this.updateSummaryGrid(summary);
            
            await this.loadConnectorCatalog();

            if (summary.syncing && summary.syncing > 0) {
                this.syncPollTimer = setTimeout(() => {
                    const page = document.getElementById('page-connectors');
                    if (page && page.classList.contains('active')) {
                        this.loadConnectorStats(true);
                    }
                }, 10000);
            }
        } catch (e: any) {
            console.error('Lỗi tải connectors:', e);
            if (!refresh) this.showToast('Không tải được connector stats', 'error');
        }
    }

    private async loadConnectorCatalog(): Promise<void> {
        try {
            const res = await authFetch(`${API}/connectors`);
            if (!res.ok) throw new Error('Catalog API failed');
            this.dashboardData = await res.json();
            this.renderTabs(this.dashboardData?.tabs || []);
            this.renderConnectorGrid(this.dashboardData?.tabs || []);
        } catch (e) {
            console.error('[Connectors] loadConnectorCatalog error:', e);
        }
    }

    private updateSummaryGrid(summary: any): void {
        const grid = document.getElementById('connectorsSummaryGrid');
        if (!grid) return;
        grid.innerHTML = `
            <div class="connector-summary-card">
                <span>Total Sources</span>
                <strong>${summary.total || 0}</strong>
                <small>Nguồn dữ liệu</small>
            </div>
            <div class="connector-summary-card">
                <span>Healthy</span>
                <strong style="color: var(--success)">${summary.healthy || 0}</strong>
                <small>Trạng thái Healthy</small>
            </div>
            <div class="connector-summary-card">
                <span>Documents</span>
                <strong>${(summary.documents || 0).toLocaleString()}</strong>
                <small>Đã đồng bộ</small>
            </div>
            <div class="connector-summary-card">
                <span>Syncing</span>
                <strong style="color: var(--warning)">${summary.syncing || 0}</strong>
                <small>Đang sync (Running)</small>
            </div>
        `;
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
            list.innerHTML = '<div class="connectors-empty">Chưa có hệ thống nào được kết nối. Bấm "+ Thêm kết nối" để bắt đầu.</div>';
            list.className = 'connectors-grid';
            return;
        }

        list.className = 'connectors-grid connectors-grid-rich';
        list.innerHTML = currentTab.instances.map(inst => this.renderConnectorCard(inst)).join('');
    }

    private renderConnectorCard(inst: ConnectorInstance): string {
        const status = inst.status || {};
        const sync   = (inst.sync?.latest_run) || {};
        const data   = inst.data || {};
        const cfg    = inst.config || {};
        const type   = inst.connector_type || '';
        const iid    = inst.instance_id;
        const docsVal = (data.documents || 0).toLocaleString();
        const isRunning = inst.sync?.is_running || status.code === 'syncing';

        let badgeClass = status.code || 'neutral';
        if (isRunning) badgeClass = 'syncing';
        else if (badgeClass === 'ok') badgeClass = 'connected';

        return `
            <article class="connector-card-rich accent-${escapeHtml(type)}">
                ${isRunning ? '<div class="sync-status-bar running"></div>' : ''}
                <div class="connector-header">
                    <div style="display:flex;align-items:center;gap:12px">
                        <div class="connector-icon">${type === 'confluence' ? '📘' : type === 'jira' ? '🎫' : '🔗'}</div>
                        <div style="min-width:0;flex:1">
                            <div class="connector-name" style="font-weight:700;font-size:14px;">${escapeHtml(inst.instance_name)}</div>
                            <div class="connector-desc" style="font-size:11px;color:var(--text-dim);">${escapeHtml(inst.base_url || type)}</div>
                        </div>
                    </div>
                </div>
                <div class="connector-body">
                    <div class="connector-config-grid">
                        <div class="connector-status-badge ${badgeClass}" style="margin-right:8px">
                            <div class="status-dot-sm"></div>
                            <span>${escapeHtml(status.label || status.code || '—')}</span>
                        </div>
                        <div class="connector-config-item">
                            <span>Sync</span><strong>${cfg.auto_sync ? '🕐 Auto' : '⛔ Manual'}</strong>
                        </div>
                    </div>
                    <div class="connector-stats">
                        <div class="stat-item"><div class="stat-value">${docsVal}</div><div class="stat-label">Tài liệu</div></div>
                    </div>
                </div>
                <div class="connector-actions-row">
                    <button class="primary-btn mini" style="padding:6px 12px" data-action="sync" data-type="${type}" data-id="${iid}" title="Sync">🔄 Sync</button>
                    <button class="secondary-btn mini" style="padding:6px" data-action="test" data-type="${type}" data-id="${iid}" title="Test">🔌</button>
                    <button class="secondary-btn mini" style="padding:6px" data-action="config" data-type="${type}" data-id="${iid}" title="Config">⚙️</button>
                    <button class="secondary-btn mini" style="padding:6px" data-action="edit" data-type="${type}" data-id="${iid}" title="Sửa">✏️</button>
                    <button class="secondary-btn mini" style="padding:6px" data-action="scope" data-type="${type}" data-id="${iid}" title="Scope">🔍</button>
                    <button class="danger-btn mini" style="padding:6px" data-action="delete" data-type="${type}" data-id="${iid}" title="Xóa">🗑</button>
                </div>
            </article>
        `;
    }

    private showToast(message: string, type: 'success' | 'error' | 'warning' | 'info'): void {
        showToast(message, type);
    }
}