import { authFetch } from './client';
import { AuthModule } from './auth';
import { showToast, formatDateTime } from './ui';
import { renderMarkdown } from './format';
import Chart from 'chart.js/auto';

export class PMDashboardModule {
    private isInitialized = false;
    private workloadChart: Chart | null = null;
    private burnupChart: Chart | null = null;
    private cfdChart: Chart | null = null;
    private leadTimeChart: Chart | null = null;
    private issueTypeChart: Chart | null = null;

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

        // Tabs Logic
        const tabs = document.querySelectorAll('.pm-tab-btn');
        tabs.forEach(tab => {
            tab.addEventListener('click', (e) => {
                const btn = e.currentTarget as HTMLElement;
                const targetId = btn.getAttribute('data-tab');
                
                tabs.forEach(t => {
                    const h = t as HTMLElement;
                    h.classList.remove('active');
                    h.style.color = 'var(--text-dim)';
                    h.style.borderBottomColor = 'transparent';
                });
                
                btn.classList.add('active');
                btn.style.color = 'var(--accent-color)';
                btn.style.borderBottomColor = 'var(--accent-color)';
                
                document.querySelectorAll('.pm-tab-content').forEach(c => (c as HTMLElement).style.display = 'none');
                if (targetId) {
                    const content = document.getElementById(targetId);
                    if (content) content.style.display = 'block';
                }
            });
        });

        // Custom Report Generate Button
        const generateAiReportBtn = document.getElementById('pmGenerateCustomBtn');
        if (generateAiReportBtn) {
            generateAiReportBtn.addEventListener('click', () => this.handleGenerateCustomReport());
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

    private async handleGenerateCustomReport() {
        const select = document.getElementById('pmProjectFilter') as HTMLSelectElement;
        const projectKey = select ? select.value : '';
        const promptInput = document.getElementById('pmCustomPrompt') as HTMLTextAreaElement;
        const prompt = promptInput ? promptInput.value.trim() : '';

        if (!projectKey) {
            showToast('Bạn phải chọn 1 dự án (Project) ở góc phải trên để phân tích!', 'warning');
            return;
        }

        if (!prompt) {
            showToast('Bạn chưa điền câu lệnh (Prompt).', 'warning');
            return;
        }

        const btn = document.getElementById('pmGenerateCustomBtn') as HTMLButtonElement;
        const loading = document.getElementById('pmCustomLoading');
        const resultContainer = document.getElementById('pmCustomResult');

        if (btn) btn.disabled = true;
        if (loading) loading.style.display = 'block';
        if (resultContainer) resultContainer.style.display = 'none';

        try {
            const res = await authFetch('/api/pm/dashboard/custom-report', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ project_key: projectKey, prompt })
            });

            if (res.ok) {
                const data = await res.json();
                this.renderCustomReport(data.report || '');
                if (resultContainer) resultContainer.style.display = 'block';
                showToast('Đã tạo báo cáo!', 'success');
            } else {
                const err = await res.json();
                showToast(`Lỗi: ${err.detail || 'Không thể sinh báo cáo.'}`, 'error');
            }
        } catch (error) {
            console.error(error);
            showToast('Lỗi mạng khi gọi AI.', 'error');
        } finally {
            if (btn) btn.disabled = false;
            if (loading) loading.style.display = 'none';
        }
    }

    private renderCustomReport(reportMd: string) {
        const resultContainer = document.getElementById('pmCustomResult');
        if (!resultContainer) return;

        const jsonBlockRegex = /```json\s+({[\s\S]*?})\s+```/gi;
        let finalMd = reportMd;
        const chartConfigs: any[] = [];
        
        finalMd = finalMd.replace(jsonBlockRegex, (match, jsonString) => {
            try {
                const config = JSON.parse(jsonString);
                if (config.is_chart) {
                    chartConfigs.push(config);
                    return `<div class="ai-chart-container" style="height: 350px; position: relative; margin: 32px 0; border: 1px dashed var(--border-color); padding: 16px; border-radius: 8px; background: var(--bg-color);"><canvas class="ai-generated-chart"></canvas></div>`;
                }
            } catch(e) {
                console.error("Failed to parse chart json:", e);
            }
            return match;
        });

        const html = renderMarkdown(finalMd);
        resultContainer.innerHTML = html;

        setTimeout(() => {
            const canvases = resultContainer.querySelectorAll('.ai-generated-chart') as NodeListOf<HTMLCanvasElement>;
            chartConfigs.forEach((config, idx) => {
                const canvas = canvases[idx];
                if (canvas) {
                    new Chart(canvas, {
                        type: config.type || 'bar',
                        data: config.data,
                        options: {
                            ...(config.options || {}),
                            responsive: true,
                            maintainAspectRatio: false
                        }
                    });
                }
            });
        }, 50);
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
            const [statsRes, risksRes, workloadRes, staleRes, burnupRes, cfdRes, leadTimeRes, issueTypesRes, epicsRes, retroRes] = await Promise.all([
                authFetch(`/api/pm/dashboard/stats${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/risks${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/workload${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/stale${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/burnup${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/cfd${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/lead-time${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/issue-types${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/epics${qs}`).then(r => r.ok ? r.json() : null),
                authFetch(`/api/pm/dashboard/retrospective${qs}`).then(r => r.ok ? r.json() : null)
            ]);
            
            this.renderStats(statsRes);
            if (risksRes) this.renderRisks(risksRes.risks || []);
            if (workloadRes) this.renderWorkload(workloadRes.workload || {});
            if (staleRes) this.renderStaleTasks(staleRes.tasks || []);
            
            if (burnupRes) this.renderBurnup(burnupRes.burnup || []);
            if (cfdRes) this.renderCfd(cfdRes.cfd || []);
            if (leadTimeRes) this.renderLeadTime(leadTimeRes);
            if (issueTypesRes) this.renderIssueTypes(issueTypesRes.issue_types || []);
            if (epicsRes) this.renderEpics(epicsRes.epics || []);
            if (retroRes) this.renderRetrospectives(retroRes.retrospectives || []);
            
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

    private renderBurnup(data: any[]) {
        const ctx = document.getElementById('pmBurnupChart') as HTMLCanvasElement;
        if (!ctx) return;
        
        const labels = data.map(d => formatDateTime(d.date).split(' ')[0] || d.date);
        const cumulative = data.map(d => d.cumulative);
        const daily = data.map(d => d.daily_completed);

        if (this.burnupChart) this.burnupChart.destroy();

        this.burnupChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        type: 'bar',
                        label: 'Số Done hằng ngày',
                        data: daily,
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
                        borderColor: '#10b981',
                        borderWidth: 1,
                        yAxisID: 'y1'
                    },
                    {
                        type: 'line',
                        label: 'Lũy kế Done (Burn-up)',
                        data: cumulative,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.3,
                        yAxisID: 'y'
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    y: { type: 'linear', display: true, position: 'left', title: {display: true, text: 'Tổng Cumulative'} },
                    y1: { type: 'linear', display: true, position: 'right', grid: {drawOnChartArea: false}, title: {display: true, text: 'Hằng ngày'} }
                }
            }
        });
    }

    private renderCfd(data: any[]) {
        const ctx = document.getElementById('pmCfdChart') as HTMLCanvasElement;
        if (!ctx) return;
        
        const labels = data.map(d => d.date);
        const doneData = data.map(d => d.done);
        const wipData = data.map(d => d.wip);

        if (this.cfdChart) this.cfdChart.destroy();

        this.cfdChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Done',
                        data: doneData,
                        borderColor: '#10b981',
                        backgroundColor: '#10b981',
                        fill: true,
                        tension: 0.2,
                        pointRadius: 0
                    },
                    {
                        label: 'Trong quá trình (ToDo + WIP)',
                        data: wipData,
                        borderColor: '#f59e0b',
                        backgroundColor: '#f59e0b',
                        fill: true,
                        tension: 0.2,
                        pointRadius: 0
                    }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: {
                    x: { type: 'category' },
                    y: { stacked: true, beginAtZero: true }
                }
            }
        });
    }

    private renderLeadTime(data: any) {
        const overallSpan = document.getElementById('pmOverallLeadTime');
        if (overallSpan) {
            overallSpan.textContent = (data.overall_avg_lead_time_days || 0).toString();
        }

        const ctx = document.getElementById('pmLeadTimeChart') as HTMLCanvasElement;
        if (!ctx) return;

        const trend = data.trend || [];
        const labels = trend.map((d: any) => formatDateTime(d.date).split(' ')[0] || d.date);
        const leadTimes = trend.map((d: any) => d.avg_lead_time_days);

        if (this.leadTimeChart) this.leadTimeChart.destroy();

        this.leadTimeChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [{
                    label: 'Lead Time (Ngày)',
                    data: leadTimes,
                    borderColor: '#8b5cf6',
                    backgroundColor: 'rgba(139, 92, 246, 0.1)',
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                scales: { y: { beginAtZero: true } }
            }
        });
    }

    private renderIssueTypes(types: any[]) {
        const ctx = document.getElementById('pmIssueTypesChart') as HTMLCanvasElement;
        if (!ctx) return;

        if (this.issueTypeChart) this.issueTypeChart.destroy();
        
        if (!types || types.length === 0) return;

        const labels = types.map(t => t.type);
        const data = types.map(t => t.count);

        this.issueTypeChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels,
                datasets: [{
                    data,
                    backgroundColor: ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6', '#64748b', '#ec4899', '#06b6d4'],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right' }
                }
            }
        });
    }

    private renderEpics(epics: any[]) {
        const container = document.getElementById('pmEpicsList');
        if (!container) return;

        if (!epics || epics.length === 0) {
            container.innerHTML = '<div style="padding: 20px; text-align: center; color: var(--text-dim);">Chưa có dữ liệu Epics cho dự án này.</div>';
            return;
        }

        container.innerHTML = epics.map(e => `
            <div style="padding: 16px; border-bottom: 1px solid var(--border-color);">
                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;">
                    <a href="${e.url || '#'}" target="_blank" style="font-weight: 600; color: var(--text-color); text-decoration: none;">
                        <span style="color: var(--accent-color); margin-right: 4px;">[${e.key}]</span> ${this.escapeHTML(e.title)}
                    </a>
                    <span style="font-size: 0.85em; font-weight: 600; color: var(--text-dim); text-transform: uppercase;">${e.status}</span>
                </div>
                <div style="background: var(--bg-color); height: 8px; border-radius: 4px; overflow: hidden; margin-top: 12px;">
                    <div style="height: 100%; width: ${e.progress}%; background: ${e.progress === 100 ? 'var(--success)' : 'var(--accent-color)'}; transition: width 0.3s ease;"></div>
                </div>
            </div>
        `).join('');
    }

    private renderRetrospectives(retros: any[]) {
        const container = document.getElementById('pmRetroContainer');
        if (!container) return;

        if (!retros || retros.length === 0) {
            container.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--text-dim);">Chưa có báo cáo AI Retrospective.</div>';
            return;
        }

        container.innerHTML = retros.map(r => `
            <div class="risk-card" style="border-left: 4px solid #8b5cf6;">
                <div class="risk-card-header" style="margin-bottom: 8px; padding-bottom: 8px;">
                    <div class="risk-card-title">${this.escapeHTML(r.title)}</div>
                    <div class="risk-card-date">${r.created_at ? formatDateTime(r.created_at) : ''}</div>
                </div>
                <div class="risk-card-body" style="font-size: 0.9em;">
                    ${r.summary}
                </div>
            </div>
        `).join('');
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
