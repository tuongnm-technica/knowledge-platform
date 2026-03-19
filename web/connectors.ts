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

    public async loadConnectorStats(): Promise<void> {
        const grid = document.getElementById('connectorsSummaryGrid');
        const list = document.getElementById('connectorsGrid');

        if (grid) grid.innerHTML = '<div class="loading" style="grid-column: 1/-1;">Đang tải thống kê...</div>';
        if (list) list.innerHTML = '<div class="connectors-empty">Đang tải danh sách kết nối...</div>';

        try {
            const response = await authFetch(`${API}/connectors`);
            if (!response.ok) throw new Error('Không thể tải danh sách connectors');

            const data = await response.json();
            const connectors: Connector[] = data.connectors || data || [];

            this.renderStats(connectors);
            this.renderConnectors(connectors);
        } catch (e: any) {
            console.error('Lỗi tải connectors:', e);
            this.showToast(`Lỗi: ${e.message}`, 'error');
            if (grid) grid.innerHTML = '<div class="error" style="grid-column: 1/-1;">Lỗi tải thống kê</div>';
            if (list) list.innerHTML = '<div class="connectors-empty">Lỗi tải dữ liệu</div>';
        }
    }

    private renderStats(connectors: Connector[]): void {
        const grid = document.getElementById('connectorsSummaryGrid');
        if (!grid) return;

        const total = connectors.length;
        const active = connectors.filter(c => c.status === 'active' || c.status === 'ok').length;
        const errors = connectors.filter(c => c.status === 'error' || c.status === 'failed').length;
        const syncing = connectors.filter(c => c.status === 'syncing' || c.status === 'processing').length;

        grid.innerHTML = `
            <div class="connector-summary-card">
                <span>Total Sources</span>
                <strong>${total}</strong>
                <small>Connected integrations</small>
            </div>
            <div class="connector-summary-card">
                <span>Healthy</span>
                <strong style="color: var(--success)">${active}</strong>
                <small>Active connections</small>
            </div>
            <div class="connector-summary-card">
                <span>Errors</span>
                <strong style="color: var(--danger)">${errors}</strong>
                <small>Require attention</small>
            </div>
            <div class="connector-summary-card">
                <span>Syncing</span>
                <strong style="color: var(--warning)">${syncing}</strong>
                <small>In progress</small>
            </div>
        `;
    }

    private renderConnectors(connectors: Connector[]): void {
        const list = document.getElementById('connectorsGrid');
        if (!list) return;
        list.innerHTML = '';

        if (connectors.length === 0) {
            list.innerHTML = '<div class="connectors-empty">Chưa có hệ thống nào được kết nối. Bấm "+ Thêm kết nối" để bắt đầu.</div>';
            return;
        }

        connectors.forEach(conn => {
            const card = document.createElement('div');
            card.className = 'connector-card';
            
            const type = (conn.type || 'unknown').toUpperCase();
            const name = escapeHtml(conn.name || conn.type || 'Connector');
            const statusLabel = escapeHtml(conn.status || 'unknown');
            const statusColor = (conn.status === 'active' || conn.status === 'ok') ? 'var(--success)' :
                                (conn.status === 'error' || conn.status === 'failed') ? 'var(--danger)' :
                                (conn.status === 'syncing' || conn.status === 'processing') ? 'var(--warning)' : 'var(--text-dim)';

            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 12px;">
                    <div style="font-weight:700; font-size:15px; color:var(--text); display:flex; align-items:center; gap:8px;">
                        <span style="font-size:20px;">🔗</span> ${name}
                    </div>
                    <div style="font-size:11px; font-weight:700; text-transform:uppercase; padding:4px 8px; border-radius:12px; border:1px solid ${statusColor}; color:${statusColor};">
                        ● ${statusLabel}
                    </div>
                </div>
                <div style="font-size:13px; color:var(--text-dim); margin-bottom:16px;">
                    <div style="margin-bottom:6px;">Loại: <strong style="color:var(--text)">${type}</strong></div>
                    <div>Đồng bộ lần cuối: <span style="color:var(--text)">${formatDateTime(conn.last_sync)}</span></div>
                </div>
            `;
            list.appendChild(card);
        });
    }

    private showToast(message: string, type: 'success' | 'error' | 'warning' | 'info'): void {
        showToast(message, type);
    }
}