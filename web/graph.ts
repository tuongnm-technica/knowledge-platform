import { API, authFetch } from './client';
import { GraphNode, GraphLink } from './models';
import { showToast, kpPrompt } from './ui';

interface GraphData {
    nodes: GraphNode[];
    edges: GraphLink[];
    detail?: {
        nodes: GraphNode[];
        edges: GraphLink[];
    };
}

export class GraphModule {
    private canvas: HTMLCanvasElement | null;
    private ctx: CanvasRenderingContext2D | null;
    
    private nodes: GraphNode[] = [];
    private links: GraphLink[] = [];
    
    private scale: number = 1;
    private offsetX: number = 0;
    private offsetY: number = 0;
    
    private isDragging: boolean = false;
    private dragStartX: number = 0;
    private dragStartY: number = 0;
    private draggedNode: GraphNode | null = null;
    private hoveredNode: GraphNode | null = null;
    
    private searchQuery: string = '';
    private activeView: string = 'snapshot';

    constructor() {
        this.canvas = document.getElementById('graphCanvas') as HTMLCanvasElement;
        this.ctx = this.canvas?.getContext('2d') || null;
        
        this.initCanvasEvents();
        
        document.getElementById('refreshGraphBtn')?.addEventListener('click', () => this.loadGraphDashboard());
        document.getElementById('graphSearchInput')?.addEventListener('input', () => this.graphSearchChanged());
        document.getElementById('resetGraphBtn')?.addEventListener('click', () => this.resetGraphView());
    }

    // ─── API & Data Loading ──────────────────────────────────────────────────

    public async loadGraphDashboard(): Promise<void> {
        this.renderViewToolbar();
        this.loadHealthStats();
        this.loadGraphData();
    }

    private async loadHealthStats(): Promise<void> {
        const grid = document.getElementById('graphHealthGrid');
        if (!grid) return;

        try {
            const response = await authFetch(`${API}/graph/health`);
            if (!response.ok) throw new Error('Failed to load graph health');
            const data = await response.json() as { total_nodes: number, total_edges: number };
            
            grid.innerHTML = `
                <div class="connector-summary-card">
                    <span>Total Entities</span>
                    <strong>${data.total_nodes || 0}</strong>
                    <small>Indexed in Graph</small>
                </div>
                <div class="connector-summary-card">
                    <span>Total Relations</span>
                    <strong>${data.total_edges || 0}</strong>
                    <small>Connections</small>
                </div>
            `;
        } catch (err) {
            grid.innerHTML = '<div class="search-empty" style="grid-column: 1/-1;">Lỗi tải dữ liệu sức khỏe đồ thị</div>';
        }
    }

    private async loadGraphData(): Promise<void> {
        this.showGraphLoading();
        try {
            const response = await authFetch(`${API}/graph/snapshot?limit=150`);
            if (!response.ok) throw new Error('Lỗi lấy dữ liệu đồ thị');
            const data = await response.json() as GraphData;

            this.nodes = (data.detail && data.detail.nodes) ? data.detail.nodes : (data.nodes || []);
            this.links = (data.detail && data.detail.edges) ? data.detail.edges : (data.edges || []);
            
            this.resetGraphView();
            this.startSimulation();
        } catch (err) {
            const error = err as Error;
            console.error('Graph Load Error:', error);
            showToast('Không tải được graph data', 'error');
        } finally {
            this.hideGraphLoading();
        }
    }

    // ─── View Toolbar & Advanced Views ───────────────────────────────────────

    private renderViewToolbar(): void {
        const container = document.getElementById('graphCanvas');
        if (!container) return;
        const wrap = container.closest('.graph-panel');
        if (!wrap) return;
        let toolbar = document.getElementById('graphViewToolbar');
        if (!toolbar) {
            toolbar = document.createElement('div');
            toolbar.id = 'graphViewToolbar';
            toolbar.className = 'graph-view-toolbar';
            const mainToolbar = wrap.querySelector('.graph-toolbar');
            if (mainToolbar) mainToolbar.insertAdjacentElement('afterend', toolbar);
            else wrap.insertBefore(toolbar, wrap.firstChild);
        }
        const views = [
            { id: 'snapshot', label: '🗺️ Overview' },
            { id: 'gaps', label: '🔍 Gaps' },
            { id: 'focus', label: '🎯 Focus Node' },
            { id: 'impact', label: '💥 Impact' },
            { id: 'trace', label: '🔗 Trace' },
        ];
        toolbar.innerHTML = views.map(v => `
            <button class="graph-view-btn ${v.id === this.activeView ? 'active' : ''}" data-view="${v.id}">${v.label}</button>
        `).join('');

        toolbar.querySelectorAll('.graph-view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const viewId = (e.currentTarget as HTMLElement).getAttribute('data-view');
                if (viewId) this.switchView(viewId);
            });
        });
    }

    private async switchView(viewId: string): Promise<void> {
        const panel = this.getOrCreateResultPanel();
        if (panel) panel.style.display = (viewId === 'gaps') ? 'block' : 'none';

        if (viewId === 'focus') {
            const nodeId = await kpPrompt({ title: '🎯 Focus Node', message: 'Nhập node ID:', placeholder: 'vd: entity_123' });
            if (!nodeId) return;
            this.activeView = viewId; this.renderViewToolbar();
            return this.loadAdvancedGraph(`${API}/graph/focus?node_id=${encodeURIComponent(nodeId)}&depth=2`, `Đã tải Focus cho ${nodeId}`);
        }
        if (viewId === 'impact') {
            const docId = await kpPrompt({ title: '💥 Impact Analysis', message: 'Nhập document ID:', placeholder: 'vd: doc_abc' });
            if (!docId) return;
            this.activeView = viewId; this.renderViewToolbar();
            return this.loadAdvancedGraph(`${API}/graph/impact?doc_id=${encodeURIComponent(docId)}&depth=3`, 'Đã tải Impact Analysis');
        }
        if (viewId === 'trace') {
            const inputId = await kpPrompt({ title: '🔗 Trace Root Cause', message: 'Nhập ID hoặc Jira key:', placeholder: 'vd: PROJ-123' });
            if (!inputId) return;
            this.activeView = viewId; this.renderViewToolbar();
            const isJira = /^[A-Z]+-\d+$/.test(inputId.trim());
            const params = isJira ? `jira_key=${encodeURIComponent(inputId)}` : `doc_id=${encodeURIComponent(inputId)}`;
            return this.loadAdvancedGraph(`${API}/graph/trace?${params}&depth=4`, 'Đã tải Trace Root Cause');
        }
        
        this.activeView = viewId;
        this.renderViewToolbar();
        if (viewId === 'snapshot') return this.loadGraphData();
        if (viewId === 'gaps') return this.loadGraphGaps();
    }

    private async loadAdvancedGraph(url: string, successMsg: string): Promise<void> {
        this.showGraphLoading();
        try {
            const res = await authFetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json() as GraphData;
            this.nodes = (data.detail && data.detail.nodes) ? data.detail.nodes : (data.nodes || []);
            this.links = (data.detail && data.detail.edges) ? data.detail.edges : (data.edges || []);
            this.resetGraphView();
            this.startSimulation();
            showToast(successMsg, 'success');
        } catch (err) { 
            const error = err as Error;
            showToast(`Lỗi: ${error.message}`, 'error'); 
        } finally { 
            this.hideGraphLoading(); 
        }
    }

    private async loadGraphGaps(): Promise<void> {
        const panel = this.getOrCreateResultPanel();
        panel.style.display = 'block';
        panel.innerHTML = '<div class="graph-loading">Đang phân tích gaps...</div>';
        try {
            const res = await authFetch(`${API}/graph/gaps?since_days=30`);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json() as { orphanEntities?: any[] };
            panel.innerHTML = `<div class="graph-result-header"><h3>🔍 Gap Insights</h3></div>
                <div class="gap-section">Đã tìm thấy ${data.orphanEntities?.length || 0} Orphan Entities.</div>`;
        } catch (err) {
            const error = err as Error;
            panel.innerHTML = `<div class="graph-error">Lỗi: ${error.message}</div>`;
        }
    }

    private getOrCreateResultPanel(): HTMLElement {
        let panel = document.getElementById('graphResultPanel');
        if (!panel) {
            panel = document.getElementById('graphResultPanel'); 
            if (!panel) {
                panel = document.createElement('div');
                panel.id = 'graphResultPanel';
                panel.className = 'graph-result-panel';
                const wrap = document.querySelector('.graph-panel');
                if (wrap) wrap.appendChild(panel);
                else document.body.appendChild(panel);
            }
        }
        return panel;
    }

    private showGraphLoading(): void {
        let hint = document.getElementById('graphHintOverlay');
        if (!hint) {
            hint = document.createElement('div');
            hint.id = 'graphHintOverlay';
            hint.className = 'graph-loading-state';
            hint.innerHTML = '<div class="spinner"></div><p>Đang tải dữ liệu và tính toán lực...</p>';
            this.canvas?.parentElement?.appendChild(hint);
        } else hint.style.display = 'flex';
    }

    private hideGraphLoading(): void {
        const hint = document.getElementById('graphHintOverlay');
        if (hint) hint.style.display = 'none';
    }

    // ─── Canvas Interaction ──────────────────────────────────────────────────

    private initCanvasEvents(): void {
        if (!this.canvas) return;

        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const zoomIntensity = 0.1;
            const wheel = e.deltaY < 0 ? 1 : -1;
            const zoomFactor = Math.exp(wheel * zoomIntensity);
            
            const rect = this.canvas!.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            this.offsetX = mouseX - (mouseX - this.offsetX) * zoomFactor;
            this.offsetY = mouseY - (mouseY - this.offsetY) * zoomFactor;
            this.scale *= zoomFactor;
            
            this.draw();
        });

        this.canvas.addEventListener('mousedown', (e) => {
            const pos = this.getMousePos(e);
            this.draggedNode = this.getNodeAt(pos.x, pos.y);
            
            this.isDragging = true;
            this.dragStartX = e.clientX - this.offsetX;
            this.dragStartY = e.clientY - this.offsetY;
        });

        this.canvas.addEventListener('mousemove', (e) => {
            const pos = this.getMousePos(e);
            
            if (this.isDragging) {
                if (this.draggedNode) {
                    this.draggedNode.x = pos.x;
                    this.draggedNode.y = pos.y;
                } else {
                    this.offsetX = e.clientX - this.dragStartX;
                    this.offsetY = e.clientY - this.dragStartY;
                }
                this.draw();
            } else {
                const prevHover = this.hoveredNode;
                this.hoveredNode = this.getNodeAt(pos.x, pos.y);
                
                if (prevHover !== this.hoveredNode) {
                    this.canvas!.style.cursor = this.hoveredNode ? 'pointer' : 'grab';
                    this.draw();
                }
            }
        });

        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
            if (this.draggedNode) {
                this.showNodeDetails(this.draggedNode);
            }
            this.draggedNode = null;
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            this.draggedNode = null;
        });
    }

    private getMousePos(e: MouseEvent): { x: number, y: number } {
        const rect = this.canvas!.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;
        return {
            x: (mouseX - this.offsetX) / this.scale,
            y: (mouseY - this.offsetY) / this.scale
        };
    }

    private getNodeAt(x: number, y: number): GraphNode | null {
        for (let i = this.nodes.length - 1; i >= 0; i--) {
            const n = this.nodes[i];
            const r = n.radius || 15;
            if (n.x !== undefined && n.y !== undefined) {
                const dx = x - n.x;
                const dy = y - n.y;
                if (dx * dx + dy * dy <= r * r) {
                    return n;
                }
            }
        }
        return null;
    }

    // ─── Search & Reset ──────────────────────────────────────────────────────

    public graphSearchChanged(): void {
        const input = document.getElementById('graphSearchInput') as HTMLInputElement;
        this.searchQuery = input?.value.toLowerCase().trim() || '';
        this.draw();
    }

    public resetGraphView(): void {
        if (this.canvas) {
            this.scale = 1;
            this.offsetX = this.canvas.width / 2;
            this.offsetY = this.canvas.height / 2;
        }
        this.draw();
    }

    // ─── Drawing & Simulation ────────────────────────────────────────────────

    private startSimulation(): void {
        this.nodes.forEach(n => {
            if (n.x === undefined) n.x = (Math.random() - 0.5) * 500;
            if (n.y === undefined) n.y = (Math.random() - 0.5) * 500;
            if (!n.radius) n.radius = 15;
        });
        this.draw();
    }

    private draw(): void {
        if (!this.canvas || !this.ctx) return;
        const ctx = this.ctx;

        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        ctx.save();
        ctx.translate(this.offsetX, this.offsetY);
        ctx.scale(this.scale, this.scale);

        // Vẽ Links
        ctx.strokeStyle = '#cccccc';
        ctx.lineWidth = 1.5;
        this.links.forEach(link => {
            const sId = typeof link.source === 'object' ? link.source.id : link.source;
            const tId = typeof link.target === 'object' ? link.target.id : link.target;
            
            const s = this.nodes.find(n => n.id === sId);
            const t = this.nodes.find(n => n.id === tId);
            
            if (s && t && s.x !== undefined && s.y !== undefined && t.x !== undefined && t.y !== undefined) {
                ctx.beginPath();
                ctx.moveTo(s.x, s.y);
                ctx.lineTo(t.x, t.y);
                ctx.stroke();
            }
        });

        // Vẽ Nodes
        this.nodes.forEach(node => {
            if (node.x === undefined || node.y === undefined) return;
            
            const isSearched = this.searchQuery && node.label.toLowerCase().includes(this.searchQuery);
            const isHovered = this.hoveredNode === node;
            
            ctx.beginPath();
            ctx.arc(node.x, node.y, (node.radius || 15) + (isHovered ? 3 : 0), 0, Math.PI * 2);
            ctx.fillStyle = isSearched ? '#f59e0b' : (node.color || '#3b82f6');
            ctx.fill();
            
            ctx.strokeStyle = isHovered ? '#1e40af' : '#ffffff';
            ctx.lineWidth = 2;
            ctx.stroke();

            // Vẽ Label
            if (this.scale > 0.5 || isHovered || isSearched) {
                ctx.fillStyle = '#333333';
                ctx.font = '12px "DM Sans", sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText(node.label, node.x, node.y + (node.radius || 15) + 14);
            }
        });

        ctx.restore();
    }

    private showNodeDetails(node: GraphNode): void {
        const detailPanel = document.getElementById('graphNodeDetail');
        if (!detailPanel) return;
        
        detailPanel.style.display = 'block';
        detailPanel.innerHTML = `
            <h4>${node.label}</h4>
            <p>Type: <strong>${node.type || 'Unknown'}</strong></p>
            <p>ID: <code>${node.id}</code></p>
            <button id="graphViewDocBtn" data-id="${node.id}" class="primary-btn mini" style="margin-top: 10px;">📄 Xem chi tiết</button>
        `;
        detailPanel.querySelector('#graphViewDocBtn')?.addEventListener('click', (e) => {
            const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
            if (id) document.dispatchEvent(new CustomEvent('kp-view-document', { detail: { id } }));
        });
    }
}