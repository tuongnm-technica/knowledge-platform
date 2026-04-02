import { authFetch } from './client';
import { AuthModule } from './auth';
import { showToast, formatDateTime, escapeHtml, formatNumber } from './ui';
import { renderMarkdown } from './format';
import Chart from 'chart.js/auto';

/**
 * PM Dashboard 2.0 Module
 * Fully aligned with Backend endpoints and optimized for Premium UX.
 */
export class PMDashboardModule {
    private isInitialized = false;
    private workloadChart: Chart | null = null;
    private leadTimeChart: Chart | null = null;
    private velocityTrendChart: Chart | null = null;
    private issueTypeChart: Chart | null = null;
    private cfdChart: Chart | null = null;

    public async init() {
        if (this.isInitialized) return;

        console.log('PM Dashboard 2.0 Module initializing...');
        const user = await AuthModule.getCurrentUser();
        if (!user) return;

        this.bindEvents();
        this.setupDrillDown();
        await this.loadProjects();
        await this.refreshData();
        this.isInitialized = true;
    }

    private bindEvents() {
        const filter = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const refreshBtn = document.getElementById('refreshPmBtn');
        const refreshAiBtn = document.getElementById('refreshAiBtn');

        if (filter) {
            filter.addEventListener('change', () => this.refreshData());
        }
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                showToast('Đang cập nhật dữ liệu PM...', 'info');
                this.refreshData();
            });
        }
        if (refreshAiBtn) {
            refreshAiBtn.addEventListener('click', () => this.handleRefreshAI());
        }

        // Tab Switching
        document.querySelectorAll('.pm-tab-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const targetId = (e.currentTarget as HTMLElement).getAttribute('data-tab');
                this.switchTab(targetId!);
            });
        });

        // Custom Report
        const generateBtn = document.getElementById('pmGenerateCustomBtn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.handleGenerateCustomReport());
        }
    }

    private switchTab(tabId: string) {
        document.querySelectorAll('.pm-tab-btn').forEach(btn => {
            btn.classList.remove('active');
            (btn as HTMLElement).style.color = 'var(--text-dim)';
            (btn as HTMLElement).style.borderBottomColor = 'transparent';
        });

        const activeBtn = document.querySelector(`[data-tab="${tabId}"]`) as HTMLElement;
        if (activeBtn) {
            activeBtn.classList.add('active');
            activeBtn.style.color = 'var(--accent-color)';
            activeBtn.style.borderBottomColor = 'var(--accent-color)';
        }

        document.querySelectorAll('.pm-tab-content').forEach(c => (c as HTMLElement).style.display = 'none');
        const activeContent = document.getElementById(tabId);
        if (activeContent) activeContent.style.display = 'block';
    }

    private async handleRefreshAI() {
        const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const projectKey = select?.value;
        if (!projectKey) {
            showToast('Vui lòng chọn 1 dự án để AI phân tích chuyên sâu.', 'warning');
            return;
        }

        try {
            showToast('Đang yêu cầu AI phân tích dữ liệu dự án...', 'info');
            const res = await authFetch(`/api/pm/dashboard/refresh-ai?project_key=${encodeURIComponent(projectKey)}`, { method: 'POST' });
            if (res.ok) {
                showToast('Yêu cầu thành công! AI đang làm việc. Vui lòng quay lại sau 20s.', 'success');
            } else {
                showToast('Không thể kích hoạt AI ngay lúc này.', 'error');
            }
        } catch (e) {
            console.error(e);
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

                select.innerHTML = '<option value="">-- Global View --</option>';
                projects.forEach((p: any) => {
                    const opt = document.createElement('option');
                    opt.value = p.key;
                    opt.textContent = `[${p.key}] ${p.name}`;
                    opt.style.backgroundColor = 'var(--bg-color)';
                    opt.style.color = 'var(--text-color)';
                    select.appendChild(opt);
                });
            }
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    private async refreshData() {
        const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const projectKey = select ? select.value : '';
        const qs = projectKey ? `?project_key=${encodeURIComponent(projectKey)}` : '';

        try {
            const [stats, risks, workload, stale, epics, cfd, leadTime, issueTypes, retrospective] = await Promise.all([
                authFetch(`/api/pm/dashboard/stats${qs}`).then(r => r.ok ? r.json() : {}),
                authFetch(`/api/pm/dashboard/at-risk${qs}`).then(r => r.ok ? r.json() : { projects: [] }),
                authFetch(`/api/pm/dashboard/workload${qs}`).then(r => r.ok ? r.json() : { workload: {} }),
                authFetch(`/api/pm/dashboard/stale${qs}${qs ? '&' : '?'}days=3`).then(r => r.ok ? r.json() : { tasks: [] }),
                authFetch(`/api/pm/dashboard/epics${qs}`).then(r => r.ok ? r.json() : { epics: [] }),
                authFetch(`/api/pm/dashboard/cfd${qs}`).then(r => r.ok ? r.json() : { cfd: [] }),
                authFetch(`/api/pm/dashboard/lead-time${qs}`).then(r => r.ok ? r.json() : {}),
                authFetch(`/api/pm/dashboard/issue-types${qs}`).then(r => r.ok ? r.json() : { issue_types: [] }),
                authFetch(`/api/pm/dashboard/retrospective${qs}`).then(r => r.ok ? r.json() : { retrospectives: [] })
            ]);

            this.renderStats(stats);
            this.renderAtRisk(risks.projects || []);
            this.renderVelocityTrend(cfd.cfd || []); // Derived from CFD
            this.renderWorkload(workload.workload || {});
            this.renderStaleTasks(stale.tasks || []);
            this.renderCfd(cfd.cfd || []);
            this.renderLeadTime(leadTime);
            this.renderIssueTypes(issueTypes.issue_types || []);
            this.renderEpics(epics.epics || []);
            this.renderRisks(risks.risks || []); // Different from at-risk projects
            this.renderRetrospectives(retrospective.retrospectives || []);

        } catch (error) {
            console.error('Failed to refresh PM data:', error);
            showToast('Lỗi tải dữ liệu bảng quản trị PM.', 'error');
        }
    }

    private renderStats(s: any) {
        this.setEl('pmStatTotal', s.total_issues || 0);
        this.setEl('pmStatDone', s.done_issues || 0);
        this.setEl('pmStatInProgress', s.in_progress_issues || 0);
        this.setEl('pmStatTodo', s.todo_issues || 0);
        this.setEl('pmStatHighRisk', s.high_priority_issues || 0);
        this.setEl('pmStatCompletion', `${s.completion_rate || 0}%`);
    }

    private renderAtRisk(projects: any[]) {
        const container = document.getElementById('pmAtRiskList');
        if (!container) return;
        
        if (!projects || projects.length === 0) {
            container.innerHTML = `<div style="color: var(--success); text-align: center; padding: 20px; font-weight: 600; background: rgba(16, 185, 129, 0.05); border-radius: 12px; border: 1px dashed var(--success);">
                🛡️ Vận hành ổn định. Không phát hiện rủi ro nghiêm trọng.
            </div>`;
            return;
        }

        container.innerHTML = projects.map(p => {
            const riskColor = p.health_status === 'critical' ? '#ef4444' : '#f59e0b';
            return `
                <div class="risk-card" style="display: flex; justify-content: space-between; align-items: center; padding: 14px; border-left: 4px solid ${riskColor}; background: rgba(255,255,255,0.02);">
                    <div>
                        <div style="font-weight: 800; font-family: 'Syne', sans-serif;">${p.project_key}</div>
                        <div style="font-size: 0.85em; color: var(--text-dim);">Velocity: ${p.velocity_weekly} task/tuần</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.4em; font-weight: 800; color: ${riskColor};">${p.risk_score}</div>
                        <div style="font-size: 0.7em; text-transform: uppercase; color: var(--text-dim);">Risk Index</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    private renderVelocityTrend(data: any[]) {
        const ctx = document.getElementById('pmVelocityTrendChart') as HTMLCanvasElement;
        if (!ctx) return;

        // Velocity Trend uses the same data as Burnup/CFD but shows daily progress
        const recent = data.slice(-7);
        const labels = recent.map(d => d.date.split('T')[0]);
        const values = recent.map((d, i) => i === 0 ? 0 : d.done - data[data.indexOf(d)-1].done);

        if (this.velocityTrendChart) this.velocityTrendChart.destroy();
        this.velocityTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{ 
                    label: 'Thanh khoản (Task/Ngày)', 
                    data: values, 
                    borderColor: '#06b6d4', 
                    backgroundColor: 'rgba(6, 182, 212, 0.1)', 
                    fill: true, 
                    tension: 0.4,
                    pointRadius: 3
                }]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false, 
                plugins: { legend: { display: false } },
                scales: { x: { display: false }, y: { display: false } }
            }
        });
    }

    private renderStaleTasks(tasks: any[]) {
        const container = document.getElementById('pmStaleTasksList');
        if (!container) return;
        
        if (tasks.length === 0) {
            container.innerHTML = '<div style="padding: 30px; text-align: center; color: var(--text-dim);">🛡️ Không có task nào bị treo quá 3 ngày.</div>';
            return;
        }

        container.innerHTML = tasks.map(t => `
            <a href="${t.url || '#'}" target="_blank" class="stale-task-item" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); text-decoration: none; color: inherit;">
                <div style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 70%;">
                    <span style="font-weight: 800; color: var(--accent-color); font-size: 0.9em; margin-right: 8px;">${t.key}</span>
                    <span style="font-weight: 500;">${escapeHtml(t.title)}</span>
                </div>
                <div style="font-size: 0.8em; color: var(--text-dim); min-width: 80px; text-align: right;">
                    ${t.assignee || 'Unassigned'}
                </div>
            </a>
        `).join('');
    }

    private renderWorkload(workload: Record<string, any>) {
        const ctx = document.getElementById('pmWorkloadChart') as HTMLCanvasElement;
        if (!ctx) return;

        const assignees = Object.keys(workload);
        const todo = assignees.map(a => workload[a]['to do'] || 0);
        const wip = assignees.map(a => workload[a]['in progress'] || 0);
        const done = assignees.map(a => workload[a]['done'] || 0);

        if (this.workloadChart) this.workloadChart.destroy();
        this.workloadChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: assignees,
                datasets: [
                    { label: 'To Do', data: todo, backgroundColor: '#94a3b8' },
                    { label: 'WIP', data: wip, backgroundColor: '#f59e0b' },
                    { label: 'Done', data: done, backgroundColor: '#10b981' }
                ]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false, 
                scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true } } 
            }
        });
    }

    private renderCfd(data: any[]) {
        const ctx = document.getElementById('pmCfdChart') as HTMLCanvasElement;
        if (!ctx) return;
        
        const labels = data.map(d => d.date);
        const done = data.map(d => d.done);
        const wip = data.map(d => d.wip);

        if (this.cfdChart) this.cfdChart.destroy();
        this.cfdChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'Done', data: done, borderColor: '#10b981', backgroundColor: 'rgba(16, 185, 129, 0.4)', fill: true, tension: 0.2, pointRadius: 0 },
                    { label: 'WIP (ToDo + InProgress)', data: wip, borderColor: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.4)', fill: true, tension: 0.2, pointRadius: 0 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { x: { type: 'category' }, y: { stacked: true, beginAtZero: true } } }
        });
    }

    private renderLeadTime(data: any) {
        this.setEl('pmOverallLeadTime', data.overall_avg_lead_time_days || '-');

        const ctx = document.getElementById('pmLeadTimeChart') as HTMLCanvasElement;
        if (!ctx) return;

        const trend = data.trend || [];
        const labels = trend.map((d: any) => d.date);
        const values = trend.map((d: any) => d.avg_lead_time_days);

        if (this.leadTimeChart) this.leadTimeChart.destroy();
        this.leadTimeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{ 
                    label: 'Avg Days', 
                    data: values, 
                    borderColor: '#8b5cf6', 
                    backgroundColor: 'rgba(139, 92, 246, 0.1)', 
                    fill: true, 
                    tension: 0.3 
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { y: { beginAtZero: true } } }
        });
    }

    private renderIssueTypes(types: any[]) {
        const ctx = document.getElementById('pmIssueTypesChart') as HTMLCanvasElement;
        if (!ctx) return;

        if (this.issueTypeChart) this.issueTypeChart.destroy();
        this.issueTypeChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: types.map(t => t.type),
                datasets: [{
                    data: types.map(t => t.count),
                    backgroundColor: ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#64748b', '#ec4899', '#06b6d4'],
                    borderWidth: 0
                }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'right' } } }
        });
    }

    private renderEpics(epics: any[]) {
        const container = document.getElementById('pmEpicsList');
        if (!container) return;
        
        if (epics.length === 0) {
            container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-dim);">Chưa có dữ liệu Epic.</div>';
            return;
        }

        container.innerHTML = epics.map(e => `
            <div style="padding: 16px; border-bottom: 1px solid var(--border-color);">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <a href="${e.url || '#'}" target="_blank" style="font-weight: 700; color: var(--text-color); text-decoration: none; font-family: 'Syne', sans-serif;">
                        <span style="color: var(--accent-light); margin-right: 4px;">[${e.key}]</span> ${escapeHtml(e.title)}
                    </a>
                    <span style="font-size: 0.75em; padding: 2px 8px; border-radius: 12px; background: rgba(255,255,255,0.05); color: var(--text-dim); text-transform: uppercase; font-weight: 700;">${e.status}</span>
                </div>
                <div style="background: rgba(0,0,0,0.1); height: 6px; border-radius: 3px; overflow: hidden;">
                    <div style="height: 100%; width: ${e.progress}%; background: var(--accent-color); transition: width 0.3s;"></div>
                </div>
            </div>
        `).join('');
    }

    private renderRisks(risks: any[]) {
        const container = document.getElementById('pmRisksContainer');
        if (!container) return;
        container.innerHTML = risks.map(r => `
            <div class="risk-card" style="padding: 16px; border-left: 4px solid var(--danger);">
                <div style="font-weight: 700; margin-bottom: 6px;">${escapeHtml(r.title)}</div>
                <div style="font-size: 0.85em; color: var(--text-dim); line-height: 1.4;">${r.summary}</div>
            </div>
        `).join('');
    }

    private renderRetrospectives(retros: any[]) {
        const container = document.getElementById('pmRetroContainer');
        if (!container) return;
        container.innerHTML = retros.map(r => `
            <div class="risk-card" style="padding: 16px; border-left: 4px solid var(--accent-color);">
                <div style="font-weight: 700; margin-bottom: 6px;">${escapeHtml(r.title)}</div>
                <div style="font-size: 0.85em; color: var(--text-dim); line-height: 1.4;">${r.summary}</div>
            </div>
        `).join('');
    }

    private setupDrillDown() {
        document.querySelectorAll('.pm-drilldown-trigger').forEach(el => {
            el.addEventListener('click', () => {
                const metric = el.getAttribute('data-metric');
                this.openDrillDownModal(metric!);
            });
        });

        document.getElementById('closePmDrillDown')?.addEventListener('click', () => {
            document.getElementById('pmDrillDownModal')!.style.display = 'none';
        });
    }

    private async openDrillDownModal(metric: string) {
        const modal = document.getElementById('pmDrillDownModal');
        const title = document.getElementById('pmDrillDownTitle');
        const body = document.getElementById('pmDrillDownBody');
        const loading = document.getElementById('pmDrillDownLoading');
        const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const projectKey = select?.value || '';

        if (!modal || !body || !loading) return;

        modal.style.display = 'block';
        body.innerHTML = '';
        loading.style.display = 'block';
        if (title) title.textContent = `Danh sách: ${metric.replace('_', ' ').toUpperCase()}`;

        try {
            const res = await authFetch(`/api/pm/dashboard/details?metric=${metric}&project_key=${encodeURIComponent(projectKey)}`);
            if (res.ok) {
                const { issues } = await res.json();
                if (issues.length === 0) {
                    body.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 40px; color: var(--text-dim);">Không tìm thấy issue nào.</td></tr>';
                } else {
                    body.innerHTML = issues.map((i: any) => `
                        <tr style="border-bottom: 1px solid var(--border-color); transition: background 0.2s;">
                            <td style="padding: 14px 12px; font-weight: 800; color: var(--accent-color); font-family: 'Syne', sans-serif;">${i.key}</td>
                            <td style="padding: 14px 12px; font-weight: 500; font-size: 0.9em;">${escapeHtml(i.title)}</td>
                            <td style="padding: 14px 12px; color: var(--text-dim); font-size: 0.85em;">${i.assignee || 'Unassigned'}</td>
                            <td style="padding: 14px 12px;"><span style="background: rgba(255,255,255,0.05); padding: 2px 8px; border-radius: 8px; font-size: 0.75em; text-transform: uppercase;">${i.status}</span></td>
                            <td style="padding: 14px 12px;"><a href="${i.url}" target="_blank" style="color: var(--accent-light); font-weight: 700; text-decoration: none;">Link ↗</a></td>
                        </tr>
                    `).join('');
                }
            }
        } catch (e) {
            console.error(e);
        } finally {
            loading.style.display = 'none';
        }
    }

    private async handleGenerateCustomReport() {
        const promptEl = document.getElementById('pmCustomPrompt') as HTMLTextAreaElement;
        const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const resultEl = document.getElementById('pmCustomResult');
        const loadingEl = document.getElementById('pmCustomLoading');

        if (!promptEl?.value || !select?.value) {
            showToast('Vui lòng chọn dự án và nhập yêu cầu.', 'warning');
            return;
        }

        if (loadingEl) loadingEl.style.display = 'block';
        if (resultEl) resultEl.style.display = 'none';

        try {
            const res = await authFetch('/api/pm/dashboard/custom-report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_key: select.value, prompt: promptEl.value })
            });

            if (res.ok) {
                const { report } = await res.json();
                if (resultEl) {
                    resultEl.innerHTML = renderMarkdown(report);
                    resultEl.style.display = 'block';
                }
                showToast('Đã tạo báo cáo AI thành công.', 'success');
            }
        } catch (e) {
            console.error(e);
            showToast('Lỗi khi tạo báo cáo AI.', 'error');
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
    }

    private setEl(id: string, val: any) {
        const el = document.getElementById(id);
        if (el) el.textContent = String(val);
    }
}

export const pmDashboardModule = new PMDashboardModule();
