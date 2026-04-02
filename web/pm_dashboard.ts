import { authFetch } from './client';
import { AuthModule } from './auth';
import { showToast, formatDateTime, escapeHtml, formatNumber } from './ui';
import { renderMarkdown } from './format';
import Chart from 'chart.js/auto';

/**
 * PM Dashboard 2.0 Module
 * Fixed: Removed duplicates, synced IDs, and handled dark mode visibility.
 */
export class PMDashboardModule {
    private isInitialized = false;
    private workloadChart: Chart | null = null;
    private leadTimeChart: Chart | null = null;
    private velocityTrendChart: Chart | null = null;
    private issueTypeChart: Chart | null = null;
    private cfdChart: Chart | null = null;
    private burnupChart: Chart | null = null;
    private logTimeChart: Chart | null = null;
    private logTimeTrendChart: Chart | null = null;
    
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
                if (targetId) this.switchTab(targetId);
            });
        });

        // Custom Report
        const generateBtn = document.getElementById('pmGenerateCustomBtn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.handleGenerateCustomReport('custom'));
        }

        // Quick Actions
        document.querySelectorAll('.pm-quick-action').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const type = (e.currentTarget as HTMLElement).getAttribute('data-type');
                if (type) this.handleGenerateCustomReport(type);
            });
        });
    }

    private switchTab(tabId: string) {
        document.querySelectorAll('.pm-tab-btn').forEach(btn => {
            btn.classList.remove('active');
            const el = btn as HTMLElement;
            el.style.color = 'var(--text-dim)';
            el.style.borderBottomColor = 'transparent';
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
            const [stats, risks, workload, stale, epics, cfd, leadTime, issueTypes, retrospective, burnup, logtime, logtimeTrend] = await Promise.all([
                authFetch(`/api/pm/dashboard/stats${qs}`).then(r => r.ok ? r.json() : {}),
                authFetch(`/api/pm/dashboard/at-risk${qs}`).then(r => r.ok ? r.json() : { projects: [] }),
                authFetch(`/api/pm/dashboard/workload${qs}`).then(r => r.ok ? r.json() : { workload: {} }),
                authFetch(`/api/pm/dashboard/stale${qs}${qs ? '&' : '?'}days=3`).then(r => r.ok ? r.json() : { tasks: [] }),
                authFetch(`/api/pm/dashboard/epics${qs}`).then(r => r.ok ? r.json() : { epics: [] }),
                authFetch(`/api/pm/dashboard/cfd${qs}`).then(r => r.ok ? r.json() : { cfd: [] }),
                authFetch(`/api/pm/dashboard/lead-time${qs}`).then(r => r.ok ? r.json() : {}),
                authFetch(`/api/pm/dashboard/issue-types${qs}`).then(r => r.ok ? r.json() : { issue_types: [] }),
                authFetch(`/api/pm/dashboard/retrospective${qs}`).then(r => r.ok ? r.json() : { retrospectives: [] }),
                authFetch(`/api/pm/dashboard/burnup${qs}`).then(r => r.ok ? r.json() : { burnup: [] }),
                authFetch(`/api/pm/dashboard/logtime${qs}`).then(r => r.ok ? r.json() : { logtime: [] }),
                authFetch(`/api/pm/dashboard/logtime-trend${qs}`).then(r => r.ok ? r.json() : { trend: [] })
            ]);

            this.renderStats(stats);
            this.renderAtRisk(risks.projects || []);
            this.renderVelocityTrend(cfd.cfd || []);
            this.renderWorkload(workload.workload || {});
            this.renderStaleTasks(stale.tasks || []);
            this.renderCfd(cfd.cfd || []);
            this.renderLeadTime(leadTime);
            this.renderIssueTypes(issueTypes.issue_types || []);
            this.renderLogTime(logtime.logtime || []);
            this.renderLogTimeTrend(logtimeTrend.trend || []);
            this.renderEpics(epics.epics || []);
            this.renderRisks(risks.risks || []);
            this.renderRetrospectives(retrospective.retrospectives || []);
            this.renderBurnup(burnup.burnup || []);

        } catch (error) {
            console.error('Failed to refresh PM data:', error);
            showToast('Lỗi tải dữ liệu bảng quản trị PM.', 'error');
        }
    }

    private renderStats(s: any) {
        this.setEl('pmStatTotal', formatNumber(s.total_issues || 0));
        this.setEl('pmStatDone', formatNumber(s.done_issues || 0));
        this.setEl('pmStatInProgress', formatNumber(s.in_progress_issues || 0));
        this.setEl('pmStatTodo', formatNumber(s.todo_issues || 0));
        this.setEl('pmStatHighRisk', formatNumber(s.high_priority_issues || 0));
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
                <div class="risk-card" style="display: flex; justify-content: space-between; align-items: center; padding: 14px; border-left: 4px solid ${riskColor}; background: rgba(255,255,255,0.02); margin-bottom: 8px;">
                    <div>
                        <div style="font-weight: 800; font-family: 'Syne', sans-serif;">${p.project_key}</div>
                        <div style="font-size: 0.85em; color: var(--text-dim);">Velocity: ${p.velocity_weekly} task/tuần</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 1.4em; font-weight: 800; color: ${riskColor};">${formatNumber(p.risk_score)}</div>
                        <div style="font-size: 0.7em; text-transform: uppercase; color: var(--text-dim);">Risk Index</div>
                    </div>
                </div>
            `;
        }).join('');
    }

    private renderVelocityTrend(data: any[]) {
        const ctx = document.getElementById('pmVelocityTrendChart') as HTMLCanvasElement;
        if (!ctx) return;

        const recent = data.slice(-7);
        const labels = recent.map(d => d.date.split('T')[0]);
        const values = recent.map((d, i) => i === 0 ? 0 : d.done - data[data.indexOf(d)-1].done);

        if (this.velocityTrendChart) this.velocityTrendChart.destroy();
        this.velocityTrendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{ 
                    label: 'Task/Ngày', 
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
            <a href="${t.url || '#'}" target="_blank" class="stale-task-item" style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border-color); text-decoration: none; color: inherit; padding: 12px;">
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
                    { label: 'WIP', data: wip, borderColor: '#f59e0b', backgroundColor: 'rgba(245, 158, 11, 0.4)', fill: true, tension: 0.2, pointRadius: 0 }
                ]
            },
            options: { responsive: true, maintainAspectRatio: false, scales: { x: { type: 'category' }, y: { stacked: true, beginAtZero: true } } }
        });
    }

    private renderLeadTime(data: any) {
        this.setEl('pmOverallLeadTime', formatNumber(data.overall_avg_lead_time_days || 0));

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
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
        });
    }

    private renderLogTime(data: any[]) {
        const ctx = document.getElementById('pmLogTimeChart') as HTMLCanvasElement;
        if (!ctx) return;

        if (this.logTimeChart) this.logTimeChart.destroy();
        this.logTimeChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.user),
                datasets: [{
                    label: 'Giờ (Hours)',
                    data: data.map(d => d.hours),
                    backgroundColor: 'rgba(59, 130, 246, 0.6)',
                    borderColor: '#3b82f6',
                    borderWidth: 1
                }]
            },
            options: { 
                indexAxis: 'y',
                responsive: true, 
                maintainAspectRatio: false,
                scales: { x: { beginAtZero: true, title: { display: true, text: 'Hours' } } }
            }
        });
    }

    private renderLogTimeTrend(trend: any[]) {
        const ctx = document.getElementById('pmLogTimeTrendChart') as HTMLCanvasElement;
        if (!ctx) return;

        if (this.logTimeTrendChart) this.logTimeTrendChart.destroy();
        
        // Group by date
        const dates = [...new Set(trend.map(t => t.date))].sort();
        const users = [...new Set(trend.map(t => t.user))];
        
        const colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#64748b', '#ec4899', '#06b6d4'];
        
        const datasets = users.map((user, i) => {
            return {
                label: user,
                data: dates.map(date => {
                    const match = trend.find(t => t.date === date && t.user === user);
                    return match ? match.hours : 0;
                }),
                backgroundColor: colors[i % colors.length]
            };
        });

        this.logTimeTrendChart = new Chart(ctx, {
            type: 'bar',
            data: { labels: dates, datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { stacked: true, title: { display: true, text: 'Ngày' } },
                    y: { stacked: true, beginAtZero: true, title: { display: true, text: 'Tổng giờ (Hours)' } }
                },
                plugins: { legend: { position: 'top' } }
            }
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
            <div class="risk-card" style="padding: 16px; border-left: 4px solid var(--danger); margin-bottom: 12px;">
                <div style="font-weight: 700; margin-bottom: 6px;">${escapeHtml(r.title)}</div>
                <div style="font-size: 0.85em; color: var(--text-dim); line-height: 1.4;">${r.summary}</div>
            </div>
        `).join('');
    }

    private renderRetrospectives(retros: any[]) {
        const container = document.getElementById('pmRetroContainer');
        if (!container) return;
        container.innerHTML = retros.map(r => `
            <div class="risk-card" style="padding: 16px; border-left: 4px solid var(--accent-color); margin-bottom: 12px;">
                <div style="font-weight: 700; margin-bottom: 6px;">${escapeHtml(r.title)}</div>
                <div style="font-size: 0.85em; color: var(--text-dim); line-height: 1.4;">${renderMarkdown(r.summary)}</div>
            </div>
        `).join('');
    }

    private renderBurnup(data: any[]) {
        const ctx = document.getElementById('pmBurnupChart') as HTMLCanvasElement;
        if (!ctx) return;

        const labels = data.map(d => d.date);
        const values = data.map(d => d.cumulative);

        if (this.burnupChart) this.burnupChart.destroy();
        this.burnupChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Cumulative Done',
                    data: values,
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.2
                }]
            },
            options: { responsive: true, maintainAspectRatio: false }
        });
    }

    private setupDrillDown() {
        document.querySelectorAll('.pm-drilldown-trigger').forEach(el => {
            el.addEventListener('click', () => {
                const metric = el.getAttribute('data-metric');
                if (metric) this.openDrillDownModal(metric);
            });
        });

        document.getElementById('closePmDrillDown')?.addEventListener('click', () => {
            const modal = document.getElementById('pmDrillDownModal');
            if (modal) modal.style.display = 'none';
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
                            <td style="padding: 14px 12px; font-size: 0.85em; color: var(--text-dim);">${formatDateTime(i.updated_at)}</td>
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

    private async handleGenerateCustomReport(actionType: string = 'custom') {
        const promptEl = document.getElementById('pmCustomPrompt') as HTMLTextAreaElement;
        const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const resultWrapper = document.getElementById('pmCustomResult');
        const resultContent = document.getElementById('pmCustomResultContent');
        const loadingEl = document.getElementById('pmCustomLoading');
        const actionLabel = document.getElementById('pmCustomActionLabel');
        const metaEl = document.getElementById('pmCustomMeta');

        if (!select?.value) {
            showToast('Vui lòng chọn dự án.', 'warning');
            return;
        }

        if (actionType === 'custom' && !promptEl?.value) {
            showToast('Vui lòng nhập yêu cầu phân tích.', 'warning');
            return;
        }

        if (loadingEl) loadingEl.style.display = 'block';
        if (resultWrapper) resultWrapper.style.display = 'none';

        try {
            const res = await authFetch('/api/pm/dashboard/custom-report', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ 
                    project_key: select.value, 
                    prompt: promptEl.value,
                    action_type: actionType
                })
            });

            if (res.ok) {
                const { report, action } = await res.json();
                
                // Set Label
                if (actionLabel) {
                    const labels: Record<string, string> = {
                        'bottleneck': 'Phân tích Điểm nghẽn',
                        'risk': 'Đánh giá Rủi ro',
                        'velocity': 'Xu hướng Velocity',
                        'workload': 'Audit Khối lượng công việc',
                        'custom': 'Phân tích Tùy chỉnh'
                    };
                    actionLabel.textContent = labels[action] || 'AI Analysis';
                }

                // Process Report (Extract JSON metadata if present)
                let cleanReport = report;
                let metadata: any = null;
                const jsonMatch = report.match(/```json\n([\s\S]*?)\n```/);
                if (jsonMatch) {
                    try {
                        metadata = JSON.parse(jsonMatch[1]);
                        cleanReport = report.replace(jsonMatch[0], '').trim();
                    } catch(e) { console.error('Failed to parse report metadata'); }
                }

                // Update Meta
                if (metaEl && metadata) {
                    const riskColor = metadata.risk_level === 'critical' ? '#ef4444' : (metadata.risk_level === 'high' ? '#f97316' : '#10b981');
                    metaEl.innerHTML = `
                        Risk: <span style="color: ${riskColor}; font-weight: 800; text-transform: uppercase;">${metadata.risk_level}</span> | 
                        Confidence: <b>${metadata.confidence}</b>
                    `;
                }

                if (resultContent) {
                    resultContent.innerHTML = renderMarkdown(cleanReport);
                    this.renderInlineCharts(resultContent, cleanReport);
                }
                if (resultWrapper) resultWrapper.style.display = 'block';
                
                showToast('Đã tạo báo cáo AI thành công.', 'success');
                
                // Clear prompt if it was a quick action
                if (actionType !== 'custom' && promptEl) promptEl.value = '';
            }
        } catch (e) {
            console.error(e);
            showToast('Lỗi khi tạo báo cáo AI.', 'error');
        } finally {
            if (loadingEl) loadingEl.style.display = 'none';
        }
    }

    /**
     * Finds [[CHART:json]] tags and renders them as live Chart.js objects.
     */
    private renderInlineCharts(container: HTMLElement, content: string) {
        const chartRegex = /\[\[CHART:([\s\S]*?)\]\]/g;
        let match;
        const chartsToRender: { id: string, config: any }[] = [];

        // 1. Identify charts and inject containers
        let html = container.innerHTML;
        let index = 0;
        
        while ((match = chartRegex.exec(content)) !== null) {
            try {
                const config = JSON.parse(match[1]);
                const chartId = `ai-chart-${Date.now()}-${index++}`;
                
                // Replace the bracketed tag in the rendered HTML with a canvas container
                const replacement = `
                    <div class="stat-card premium-card" style="margin: 24px 0; padding: 20px; background: rgba(255,255,255,0.02); min-height: 250px;">
                        <h5 style="margin-bottom: 16px; font-family: 'Syne', sans-serif; text-align: center;">${config.title || 'Analysis Visualization'}</h5>
                        <div style="height: 200px; position: relative;">
                            <canvas id="${chartId}"></canvas>
                        </div>
                    </div>
                `;
                
                // Since marked might have escaped some chars or added tags, 
                // we'll try a more robust approach: find the raw match[0] text in the container
                // Actually, just searching for the raw string usually works if it wasn't modified much
                html = html.replace(match[0], replacement);
                chartsToRender.push({ id: chartId, config });
            } catch (e) {
                console.error("Failed to parse inline chart JSON:", e);
            }
        }
        
        container.innerHTML = html;

        // 2. Initialize Chart.js
        setTimeout(() => {
            chartsToRender.forEach(c => {
                const ctx = document.getElementById(c.id) as HTMLCanvasElement;
                if (!ctx) return;

                const chartType = (c.config.type || 'pie') as any;
                new Chart(ctx, {
                    type: chartType,
                    data: {
                        labels: c.config.labels || [],
                        datasets: [{
                            label: c.config.title || 'Dữ liệu',
                            data: c.config.data || [],
                            backgroundColor: chartType === 'pie' || chartType === 'doughnut' 
                                ? ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#64748b']
                                : 'rgba(59, 130, 246, 0.5)',
                            borderColor: '#3b82f6',
                            borderWidth: 1
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { position: chartType === 'pie' ? 'right' : 'top' } }
                    }
                });
            });
        }, 50);
    }

    private setEl(id: string, val: any) {
        const el = document.getElementById(id);
        if (el) el.textContent = String(val);
    }
}

export const pmDashboardModule = new PMDashboardModule();
