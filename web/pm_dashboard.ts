import { authFetch } from './client';
import { AuthModule } from './auth';
import { showToast, formatDateTime } from './ui';
import Chart from 'chart.js/auto';

export class PMDashboardModule {
    private isInitialized = false;
    private workloadChart: Chart | null = null;

    public async init() {
        if (this.isInitialized) return;

        console.log('PM Dashboard Module rendering...');
        const user = await AuthModule.getCurrentUser();
        if (!user) {
            return;
        }

        this.bindEvents();
        await this.loadProjects();
        await this.refreshData();
        this.isInitialized = true;
    }

    private bindEvents() {
        const filter = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const refreshBtn = document.getElementById('refreshPmBtn');

        if (filter) {
            filter.addEventListener('change', () => this.refreshData());
        }
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                showToast('Đang tải dữ liệu báo cáo...', 'info');
                this.refreshData();
            });
        }

        const refreshAiBtn = document.getElementById('refreshAiBtn');
        if (refreshAiBtn) {
            refreshAiBtn.addEventListener('click', () => this.handleRefreshAI());
        }
    }

    private async handleRefreshAI() {
        const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const projectKey = select ? select.value : '';

        if (!projectKey) {
            showToast('Vui lòng chọn một dự án cụ thể để làm mới phân tích AI.', 'warning');
            return;
        }

        try {
            showToast(`Đang yêu cầu AI phân tích dự án ${projectKey}...`, 'info');
            const res = await authFetch(`/api/pm/dashboard/refresh-ai?project_key=${encodeURIComponent(projectKey)}`, {
                method: 'POST'
            });

            if (res.ok) {
                showToast('Yêu cầu đã được gửi. Phân tích AI thường mất 15-30 giây. Vui lòng đợi...', 'success');
                
                // Tự động refresh phần Risks sau 20 giây
                setTimeout(() => {
                    this.refreshRisksOnly(projectKey);
                }, 20000);
            } else {
                const err = await res.json();
                showToast(`Lỗi: ${err.detail || 'Không thể yêu cầu AI.'}`, 'error');
            }
        } catch (error) {
            console.error('Failed to trigger AI refresh:', error);
            showToast('Lỗi kết nối khi yêu cầu AI.', 'error');
        }
    }

    private async refreshRisksOnly(projectKey: string) {
        try {
            const risksRes = await authFetch(`/api/pm/dashboard/risks?project_key=${encodeURIComponent(projectKey)}`).then(r => r.ok ? r.json() : null);
            if (risksRes) {
                this.renderRisks(risksRes.risks || []);
                showToast('Đã cập nhật báo cáo AI mới nhất.', 'success');
            }
        } catch (error) {
            console.error('Failed to refresh risks only:', error);
        }
    }


    private async loadProjects() {
        try {
            const res = await authFetch('/api/pm/projects');
            if (res.ok) {
                const data = await res.json();
                const projects = data.projects || [];
                
                const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
                if (!select) return;

                // Keep only the first "-- Tất cả dự án --" option
                select.innerHTML = '<option value="">-- Tất cả dự án --</option>';
                
                projects.forEach((p: any) => {
                    const opt = document.createElement('option');
                    opt.value = p.key;
                    opt.textContent = `[${p.key}] ${p.name}`;
                    select.appendChild(opt);
                });
            }
        } catch (error) {
            console.error('Failed to load projects:', error);
            showToast('Không thể tải danh sách dự án.', 'error');
        }
    }

    private async refreshData() {
        const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const projectKey = select ? select.value : '';
        
        let qs = '';
        if (projectKey) {
            qs = `?project_key=${encodeURIComponent(projectKey)}`;
        }
        
        try {
            const [statsRes, risksRes, workloadRes, staleRes] = await Promise.all([
                authFetch(`/api/pm/dashboard/stats${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/risks${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/workload${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/stale${qs}`).then(r => r.ok ? r.json() : null)
            ]);
            
            this.renderStats(statsRes);
            if (risksRes) {
                 this.renderRisks(risksRes.risks || []);
            }
            if (workloadRes) {
                this.renderWorkload(workloadRes.workload || {});
            }
            if (staleRes) {
                this.renderStaleTasks(staleRes.tasks || []);
            }
        } catch (error) {
            console.error('Failed to refresh PM data:', error);
            showToast('Lỗi tải dữ liệu bảng điều khiển PM.', 'error');
        }
    }

    private renderStats(stats: any) {
        if (!stats) return;
        
        const safeInt = (val: any) => parseInt(val) || 0;
        
        document.getElementById('pmStatTotal')!.textContent = safeInt(stats.total_issues).toString();
        document.getElementById('pmStatDone')!.textContent = safeInt(stats.done_issues).toString();
        document.getElementById('pmStatInProgress')!.textContent = safeInt(stats.in_progress_issues).toString();
        document.getElementById('pmStatTodo')!.textContent = safeInt(stats.todo_issues).toString();
        document.getElementById('pmStatHighRisk')!.textContent = safeInt(stats.high_priority_issues).toString();
        
        const rate = parseFloat(stats.completion_rate) || 0;
        document.getElementById('pmStatCompletion')!.textContent = `${rate}%`;
    }

    private renderRisks(risks: any[]) {
        const container = document.getElementById('pmRisksContainer');
        if (!container) return;
        
        if (!risks || risks.length === 0) {
            container.innerHTML = '<div style="padding: 32px; text-align: center; color: var(--text-dim);">Chưa có báo cáo rủi ro AI cho dự án này.</div>';
            return;
        }

        container.innerHTML = risks.map(r => `
            <div class="risk-card">
                <div class="risk-card-header">
                    <div class="risk-card-title">${this.escapeHTML(r.title)}</div>
                    <div class="risk-card-date">${r.created_at ? formatDateTime(r.created_at) : ''}</div>
                </div>
                <div class="risk-card-body">
                    ${r.summary}
                </div>
            </div>
        `).join('');
    }

    private renderWorkload(workload: Record<string, any>) {
        const ctx = document.getElementById('pmWorkloadChart') as HTMLCanvasElement;
        if (!ctx) return;

        const assignees = Object.keys(workload);
        const todoData = assignees.map(a => workload[a]['to do'] || 0);
        const inProgressData = assignees.map(a => workload[a]['in progress'] || 0);
        const doneData = assignees.map(a => workload[a]['done'] || 0);

        if (this.workloadChart) {
            this.workloadChart.destroy();
        }

        this.workloadChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: assignees,
                datasets: [
                    { label: 'To Do', data: todoData, backgroundColor: '#94a3b8' },
                    { label: 'In Progress', data: inProgressData, backgroundColor: '#f59e0b' },
                    { label: 'Done', data: doneData, backgroundColor: '#10b981' }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true },
                    y: { stacked: true, beginAtZero: true }
                },
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });
    }

    private renderStaleTasks(tasks: any[]) {
        const container = document.getElementById('pmStaleTasksList');
        if (!container) return;

        if (!tasks || tasks.length === 0) {
            container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-dim);">Không có task nào cần chú ý đặc biệt.</div>';
            return;
        }

        container.innerHTML = tasks.map(t => {
            const isStale = this.isOlderThan(t.updated_at, 3);
            const isHighPriority = t.priority === 'High' || t.priority === 'Highest';
            
            let tagClass = 'tag-warning';
            let tagText = 'Stale';
            if (isHighPriority) {
                tagClass = 'tag-danger';
                tagText = 'High Priority';
            }
            if (isStale && isHighPriority) tagText = 'Critical';

            return `
                <a href="${t.url || '#'}" target="_blank" class="stale-task-item">
                    <span class="stale-task-key">${t.key}</span>
                    <span class="stale-task-title" title="${this.escapeHTML(t.title)}">${this.escapeHTML(t.title)}</span>
                    <span class="stale-tag ${tagClass}">${tagText}</span>
                    <span class="stale-assignee">${this.escapeHTML(t.assignee)}</span>
                </a>
            `;
        }).join('');
    }

    private isOlderThan(dateStr: string, days: number): boolean {
        if (!dateStr) return false;
        const lastUpdate = new Date(dateStr).getTime();
        const now = new Date().getTime();
        const diffDays = (now - lastUpdate) / (1000 * 60 * 60 * 24);
        return diffDays > days;
    }

    private escapeHTML(str: string) {
        if (!str) return '';
        return str.replace(/[&<>'"]/g, 
            tag => ({
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                "'": '&#39;',
                '"': '&quot;'
            }[tag] || tag)
        );
    }
}

export const pmDashboardModule = new PMDashboardModule();
