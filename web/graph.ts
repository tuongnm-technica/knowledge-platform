import { API, authFetch } from './client';
import { GraphNode, GraphLink } from './models';
import { showToast, kpPrompt, escapeHtml } from './ui';


export class GraphModule {
    private canvas: HTMLCanvasElement | null;
    private ctx: CanvasRenderingContext2D | null;
    
    private nodes: GraphNode[] = [];
    private links: GraphLink[] = [];
    
    private scale: number = 1;
    private offsetX: number = 0;
    private offsetY: number = 0;
    
    private isDragging: boolean = false;
    private hasDragged: boolean = false;
    private dragStartX: number = 0;
    private dragStartY: number = 0;
    private nodeDragOffsetX: number = 0;
    private nodeDragOffsetY: number = 0;
    private draggedNode: GraphNode | null = null;
    private hoveredNode: GraphNode | null = null;
    
    private searchQuery: string = '';
    private currentView: string = 'view';
    
    private animationFrameId: number | null = null;
    private simulationAlpha: number = 1; // Nhiệt độ mô phỏng (từ 1 giảm dần về 0)

    constructor() {
        this.canvas = document.getElementById('graphCanvas') as HTMLCanvasElement;
        this.ctx = this.canvas?.getContext('2d') || null;
        
        this.initCanvasEvents();
        
        // Dùng ResizeObserver để cập nhật lại size canvas khi Tab hiển thị
        if (this.canvas && this.canvas.parentElement) {
            const observer = new ResizeObserver(() => {
                this.handleResize();
            });
            observer.observe(this.canvas.parentElement);
        } else {
            this.handleResize();
            window.addEventListener('resize', () => this.handleResize());
        }
        
        document.getElementById('refreshGraphBtn')?.addEventListener('click', () => this.loadGraphDashboard());
        document.getElementById('graphSearchInput')?.addEventListener('input', () => this.graphSearchChanged());
        document.getElementById('resetGraphBtn')?.addEventListener('click', () => this.resetGraphView());
    }

    private handleResize(): void {
        if (!this.canvas || !this.canvas.parentElement) return;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.draw();
    }

    // ─── API & Data Loading ──────────────────────────────────────────────────

    public async loadGraphDashboard(): Promise<void> {
        await this.loadHealthStats();
        await this.switchView('view');
    }

    private async loadHealthStats(): Promise<void> {
        const grid = document.getElementById('graphHealthGrid');
        if (!grid) return;

        try {
            const response = await authFetch(`${API}/graph/health`);
            if (!response.ok) throw new Error('Failed to load graph health');
            const data = await response.json() as { 
                totalDocuments: number, 
                coveragePercent: number, 
                freshnessDays: number,
                entities: number, 
                relations: number,
                document_links: number
            };
            
            grid.innerHTML = `
                <div class="connector-summary-card">
                    <span>Tổng tài liệu</span>
                    <strong>${data.totalDocuments || 0}</strong>
                    <small>Trong kho tri thức</small>
                </div>
                <div class="connector-summary-card">
                    <span>Độ phủ & Tươi mới</span>
                    <strong>${data.coveragePercent || 0}% / ${data.freshnessDays || 0}d</strong>
                    <small>Coverage / Freshness</small>
                </div>
                <div class="connector-summary-card">
                    <span>Thực thể (Entities)</span>
                    <strong>${data.entities || 0}</strong>
                    <small>Nodes trích xuất</small>
                </div>
                <div class="connector-summary-card">
                    <span>Quan hệ (Relations)</span>
                    <strong>${(data.relations || 0) + (data.document_links || 0)}</strong>
                    <small>Edges trong Graph</small>
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
            const data = await response.json() as any;

            this.nodes = (data.detail && data.detail.nodes) ? data.detail.nodes : (data.nodes || []);
            
            // Map node properties for simulation
            this.nodes.forEach(n => {
                n.type = n.type || n.kind || n.subkind || 'entity';
                n.radius = n.radius || n.size || 25;
            });

            const rawEdges = (data.detail && (data.detail.edges || data.detail.links)) ? (data.detail.edges || data.detail.links) : (data.edges || data.links || []);
            
            this.links = rawEdges.map((e: any) => ({
                source: e.source || e.from || e.source_id,
                target: e.target || e.to || e.target_id,
                label: e.label || e.type || e.relation_type || 'related',
                weight: e.weight || e.strength || 1
            }));
            
            // Tối ưu O(1): Gán trực tiếp reference của object Node vào source/target của Link
            const nodeMap = new Map(this.nodes.map(n => [n.id, n]));
            this.links.forEach(l => {
                const sourceId = typeof l.source === 'object' ? (l.source as any).id : l.source;
                const targetId = typeof l.target === 'object' ? (l.target as any).id : l.target;
                l.source = nodeMap.get(sourceId) || l.source;
                l.target = nodeMap.get(targetId) || l.target;
            });

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
            { id: 'view', label: '🗺️ Overview' },
            { id: 'snapshot', label: '📊 Entities' },
            { id: 'gaps', label: '🔍 Gaps' },
            { id: 'focus', label: '🎯 Focus' },
            { id: 'impact', label: '💥 Impact' },
            { id: 'trace', label: '🔗 Trace' }
        ];
        toolbar.innerHTML = views.map(v => `
            <button class="graph-view-btn ${this.currentView === v.id ? 'active' : ''}" 
                    data-view="${v.id}">${v.label}</button>
        `).join('');

        toolbar.querySelectorAll('.graph-view-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const viewId = (e.currentTarget as HTMLElement).getAttribute('data-view');
                if (viewId) this.switchView(viewId);
            });
        });
    }

    public async switchView(viewId: string): Promise<void> {
        this.currentView = viewId;
        this.renderViewToolbar();

        const resultPanel = document.getElementById('graphResultPanel');
        if (resultPanel) resultPanel.innerHTML = '';

        if (viewId === 'view') return this.loadAdvancedGraph(`${API}/graph/view?since_days=30`, 'Đã tải bản đồ tổng quan');
        if (viewId === 'snapshot') return this.loadGraphData();
        
        if (viewId === 'gaps') {
            return this.loadAdvancedGraph(`${API}/graph/gaps`, 'Đã phân tích lỗ hổng dữ liệu');
        }
        if (viewId === 'focus') {
            const nodeId = await kpPrompt({ title: '🎯 Focus Node', message: 'Nhập node ID:', placeholder: 'vd: entity_123' });
            if (!nodeId) return;
            return this.loadAdvancedGraph(`${API}/graph/focus?node_id=${encodeURIComponent(nodeId)}&depth=2`, `Đã tải Focus cho ${nodeId}`);
        }
        if (viewId === 'impact') {
            const docId = await kpPrompt({ title: '💥 Impact Analysis', message: 'Nhập document ID:', placeholder: 'vd: doc_abc' });
            if (!docId) return;
            return this.loadAdvancedGraph(`${API}/graph/impact?doc_id=${encodeURIComponent(docId)}&depth=3`, 'Đã tải Impact Analysis');
        }
        if (viewId === 'trace') {
            const inputId = await kpPrompt({ title: '🔗 Trace Root Cause', message: 'Nhập ID hoặc Jira key:', placeholder: 'vd: PROJ-123' });
            if (!inputId) return;
            const isJira = /^[A-Z]+-\d+$/.test(inputId.trim());
            const params = isJira ? `jira_key=${encodeURIComponent(inputId)}` : `doc_id=${encodeURIComponent(inputId)}`;
            return this.loadAdvancedGraph(`${API}/graph/trace?${params}&depth=4`, 'Đã tải Trace Root Cause');
        }
    }

    private async loadAdvancedGraph(url: string, successMsg: string): Promise<void> {
        this.showGraphLoading();
        try {
            const res = await authFetch(url);
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            const data = await res.json() as any;
            
            this.nodes = (data.detail && data.detail.nodes) ? data.detail.nodes : (data.nodes || []);
            
            // Handle empty state
            if (this.nodes.length === 0) {
                const canvas = document.getElementById('graphCanvas') as HTMLCanvasElement;
                if (canvas) {
                    const ctx = canvas.getContext('2d');
                    if (ctx) {
                        ctx.clearRect(0, 0, canvas.width, canvas.height);
                        ctx.fillStyle = '#888888';
                        ctx.font = '16px Inter, sans-serif';
                        ctx.textAlign = 'center';
                        ctx.fillText('Chưa có dữ liệu đồ thị. Vui lòng trích xuất thực thể từ tài liệu.', canvas.width / 2, canvas.height / 2);
                    }
                }
                this.hideGraphLoading();
                showToast('Không có dữ liệu đồ thị để hiển thị', 'info');
                return;
            }

            // Map node properties for simulation
            this.nodes.forEach(n => {
                n.type = n.type || n.kind || n.subkind || 'entity';
                n.radius = n.radius || n.size || 25;
            });

            const rawEdges = (data.detail && (data.detail.edges || data.detail.links)) ? (data.detail.edges || data.detail.links) : (data.edges || data.links || []);
            
            this.links = rawEdges.map((e: any) => ({
                source: e.source || e.from || e.source_id,
                target: e.target || e.to || e.target_id,
                label: e.label || e.type || e.relation_type || 'related',
                weight: e.weight || e.strength || 1
            }));
            
            // Tối ưu O(1) cho các Node
            const nodeMap = new Map(this.nodes.map(n => [n.id, n]));
            this.links.forEach(l => {
                const sourceId = typeof l.source === 'object' ? (l.source as any).id : l.source;
                const targetId = typeof l.target === 'object' ? (l.target as any).id : l.target;
                l.source = nodeMap.get(sourceId) || l.source;
                l.target = nodeMap.get(targetId) || l.target;
            });

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
            // Đánh thức lại mô phỏng khi người dùng tương tác
            if (this.simulationAlpha < 0.1) this.reheatSimulation();
            
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
            this.hasDragged = false; // Reset cờ kéo
            
            if (this.draggedNode) {
                this.nodeDragOffsetX = this.draggedNode.x! - pos.x;
                this.nodeDragOffsetY = this.draggedNode.y! - pos.y;
                this.reheatSimulation();
            } else {
                this.dragStartX = e.clientX - this.offsetX;
                this.dragStartY = e.clientY - this.offsetY;
            }
        });

        this.canvas.addEventListener('mousemove', (e) => {
            const pos = this.getMousePos(e);
            
            if (this.isDragging) {
                this.hasDragged = true; // Đánh dấu là chuột có di chuyển
                if (this.draggedNode) {
                    this.draggedNode.x = pos.x + this.nodeDragOffsetX;
                    this.draggedNode.y = pos.y + this.nodeDragOffsetY;
                    // Triệt tiêu vận tốc để Node không bị văng đi sau khi thả
                    this.draggedNode.vx = 0;
                    this.draggedNode.vy = 0;
                    this.reheatSimulation(); // Giữ lực tác động khi đang kéo
                } else {
                    this.offsetX = e.clientX - this.dragStartX;
                    this.offsetY = e.clientY - this.dragStartY;
                }
            } else {
                const prevHover = this.hoveredNode;
                this.hoveredNode = this.getNodeAt(pos.x, pos.y);
                
                if (prevHover !== this.hoveredNode) {
                    this.canvas!.style.cursor = this.hoveredNode ? 'pointer' : 'grab';
                }
            }
        });

        this.canvas.addEventListener('mouseup', () => {
            this.isDragging = false;
            // Chỉ hiện chi tiết nếu người dùng CLICK (không kéo đi xa)
            if (this.draggedNode && !this.hasDragged) {
                this.showNodeDetails(this.draggedNode);
            }
            this.draggedNode = null;
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            this.hasDragged = false;
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
            const r = n.radius || 25;
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
        if (!this.canvas || this.nodes.length === 0) {
            if (this.canvas) {
                this.scale = 1;
                this.offsetX = this.canvas.width / 2;
                this.offsetY = this.canvas.height / 2;
            }
            this.draw();
            return;
        }

        // Tính toán Bounding Box (Khu vực chứa toàn bộ các node)
        let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
        this.nodes.forEach(n => {
            if (n.x !== undefined && n.y !== undefined) {
                const r = n.radius || 25;
                minX = Math.min(minX, n.x - r);
                maxX = Math.max(maxX, n.x + r);
                minY = Math.min(minY, n.y - r);
                maxY = Math.max(maxY, n.y + r);
            }
        });

        if (minX !== Infinity) {
            const graphWidth = maxX - minX;
            const graphHeight = maxY - minY;
            const padding = 60; // Khoảng cách lề (pixels)
            
            const scaleX = (this.canvas.width - padding * 2) / (graphWidth || 1);
            const scaleY = (this.canvas.height - padding * 2) / (graphHeight || 1);
            
            // Tự động zoom nhỏ lại nếu đồ thị quá to, tối đa zoom out = 0.1, zoom in max = 1.2
            this.scale = Math.max(0.1, Math.min(scaleX, scaleY, 1.2));

            // Căn giữa dựa trên tọa độ trung tâm của Bounding Box
            const centerX = minX + graphWidth / 2;
            const centerY = minY + graphHeight / 2;
            this.offsetX = this.canvas.width / 2 - centerX * this.scale;
            this.offsetY = this.canvas.height / 2 - centerY * this.scale;
        }
        this.draw();
    }

    // ─── Drawing & Simulation ────────────────────────────────────────────────

    private startSimulation(): void {
        if (this.animationFrameId) cancelAnimationFrame(this.animationFrameId);
        this.simulationAlpha = 1;

        this.nodes.forEach(n => {
            if (n.x === undefined) n.x = (Math.random() - 0.5) * 400;
            if (n.y === undefined) n.y = (Math.random() - 0.5) * 400;
            n.vx = 0; n.vy = 0;
            if (!n.radius) n.radius = 25;
        });
        
        const tick = () => {
            if (this.simulationAlpha > 0.01) {
                this.applyPhysics();
                this.simulationAlpha *= 0.96;
                
                if (this.simulationAlpha > 0.3 && !this.isDragging) {
                    this.resetGraphView();
                }
            }
            this.draw();
            this.animationFrameId = requestAnimationFrame(tick);
        };
        tick();
    }
    
    private reheatSimulation(): void {
        this.simulationAlpha = Math.max(this.simulationAlpha, 0.3); // Hâm nóng lại khi kéo/thả
    }
    
    private applyPhysics(): void {
        const damping = 0.75;
        const repulsion = 1200;
        const springK = 0.08;
        const targetLength = 100;
        
        // Lực đẩy giữa các nodes (Repulsion)
        for (let i = 0; i < this.nodes.length; i++) {
            for (let j = i + 1; j < this.nodes.length; j++) {
                const n1 = this.nodes[i], n2 = this.nodes[j];
                let dx = n1.x! - n2.x!;
                let dy = n1.y! - n2.y!;
                let dSq = dx * dx + dy * dy;
                if (dSq === 0) { dx = Math.random(); dy = Math.random(); dSq = dx*dx+dy*dy; }
                
                // Giới hạn vùng tác dụng lực & Capping dSq để tránh "explosive repulsion"
                if (dSq < 80000) { 
                    const f = (repulsion / Math.max(dSq, 400)) * this.simulationAlpha;
                    n1.vx! += dx * f; n1.vy! += dy * f;
                    n2.vx! -= dx * f; n2.vy! -= dy * f;
                }
            }
        }
        
        // Lực kéo từ các cạnh (Springs)
        this.links.forEach(l => {
            const s = l.source as GraphNode;
            const t = l.target as GraphNode;
            if (!s || !t || s.x === undefined || t.x === undefined || s.y === undefined || t.y === undefined) return;
            
            const dx = t.x - s.x;
            const dy = t.y - s.y;
            const dist = Math.sqrt(dx*dx + dy*dy) || 1;
            
            const f = (dist - targetLength) * springK * this.simulationAlpha;
            const fx = (dx / dist) * f;
            const fy = (dy / dist) * f;
            
            s.vx! += fx; s.vy! += fy;
            t.vx! -= fx; t.vy! -= fy;
        });
        
        // Cập nhật vị trí và Lực hút tâm (Gravity)
        this.nodes.forEach(n => {
            n.vx! += (0 - n.x!) * 0.01 * this.simulationAlpha;
            n.vy! += (0 - n.y!) * 0.01 * this.simulationAlpha;
            
            if (n !== this.draggedNode) {
                n.x! += n.vx! * damping;
                n.y! += n.vy! * damping;
            }
        });
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
            const s = link.source as GraphNode;
            const t = link.target as GraphNode;
            if (s && t && s.x !== undefined && t.x !== undefined && s.y !== undefined && t.y !== undefined) {
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
            const radius = (node.radius || 25) + (isHovered ? 6 : 0);
            
            // Drop shadow for nodes
            ctx.shadowColor = 'rgba(0,0,0,0.15)';
            ctx.shadowBlur = 8;
            ctx.shadowOffsetX = 0;
            ctx.shadowOffsetY = 4;

            ctx.beginPath();
            ctx.arc(node.x, node.y, radius, 0, Math.PI * 2);
            
            // Premium gradients for nodes
            const gradient = ctx.createRadialGradient(node.x, node.y, 0, node.x, node.y, radius);
            const baseColor = isSearched ? '#f59e0b' : (node.color || '#3b82f6');
            gradient.addColorStop(0, this.lightenColor(baseColor, 20));
            gradient.addColorStop(1, baseColor);
            
            ctx.fillStyle = gradient;
            ctx.fill();
            
            ctx.shadowColor = 'transparent'; // Reset shadow
            ctx.shadowBlur = 0;

            ctx.strokeStyle = isHovered ? '#1e40af' : 'rgba(255,255,255,0.8)';
            ctx.lineWidth = isHovered ? 3 : 2;
            ctx.stroke();

            // Vẽ Label
            if (this.scale > 0.4 || isHovered || isSearched) {
                const fontSize = isHovered || isSearched ? 13 : 11;
                ctx.fillStyle = isHovered ? 'var(--text)' : 'var(--text-dim)';
                ctx.font = `${isHovered || isSearched ? 'bold' : '500'} ${fontSize}px "DM Sans", sans-serif`;
                ctx.textAlign = 'center';
                
                // Text background/halo for better readability
                ctx.strokeStyle = 'rgba(255,255,255,0.9)';
                ctx.lineWidth = 4;
                ctx.strokeText(node.label, node.x, node.y + radius + 20);
                ctx.fillText(node.label, node.x, node.y + radius + 20);
            }
        });

        ctx.restore();
    }

    private lightenColor(hex: string, percent: number): string {
        try {
            const num = parseInt(hex.replace("#", ""), 16),
            amt = Math.round(2.55 * percent),
            R = (num >> 16) + amt,
            B = (num >> 8 & 0x00FF) + amt,
            G = (num & 0x0000FF) + amt;
            return "#" + (0x1000000 + (R < 255 ? R < 0 ? 0 : R : 255) * 0x10000 + (B < 255 ? B < 0 ? 0 : B : 255) * 0x100 + (G < 255 ? G < 0 ? 0 : G : 255)).toString(16).slice(1);
        } catch (e) { return hex; }
    }

    private async showNodeDetails(node: GraphNode): Promise<void> {
        const detailPanel = document.getElementById('graphNodeDetail');
        if (!detailPanel) return;
        
        detailPanel.style.display = 'block';
        detailPanel.innerHTML = `
            <div class="graph-detail-header">
                <div class="graph-detail-title">${escapeHtml(node.label)}</div>
                <button class="graph-detail-close" onclick="this.parentElement.parentElement.style.display='none'">&times;</button>
            </div>
            <div class="graph-detail-body">
                <div class="graph-detail-item">
                    <span class="label">ID</span>
                    <span class="value"><code>${node.id}</code></span>
                </div>
                <div class="graph-detail-item">
                    <span class="label">Loại</span>
                    <span class="value">${escapeHtml(node.type || 'Thực thể')}</span>
                </div>
                <div id="nodeExtraDetails" class="graph-loading">Đang tải chi tiết...</div>
                <button id="graphViewDocBtn" data-id="${node.id}" class="primary-btn mini" style="margin-top: 10px; width: 100%;">📄 Xem tài liệu liên quan</button>
            </div>
        `;

        try {
            const res = await authFetch(`${API}/graph/node/${node.id}`);
            if (res.ok) {
                const data = await res.json();
                const extra = document.getElementById('nodeExtraDetails');
                if (extra && data.metadata) {
                    let html = '';
                    for (const [key, val] of Object.entries(data.metadata)) {
                        html += `
                            <div class="graph-detail-item">
                                <span class="label">${key}</span>
                                <span class="value">${val}</span>
                            </div>
                        `;
                    }
                    extra.outerHTML = html;
                }
            }
        } catch (e) {
            const extra = document.getElementById('nodeExtraDetails');
            if (extra) extra.style.display = 'none';
        }

        detailPanel.querySelector('#graphViewDocBtn')?.addEventListener('click', (e) => {
            const id = (e.currentTarget as HTMLElement).getAttribute('data-id');
            if (id) {
                // If it's a document, view it directly, otherwise search it
                if (node.type === 'document') {
                    document.dispatchEvent(new CustomEvent('kp-view-document', { detail: { id } }));
                } else {
                    document.dispatchEvent(new CustomEvent('kp-navigate', { detail: 'search' }));
                    setTimeout(() => {
                        const input = document.getElementById('searchInput') as HTMLInputElement;
                        if (input) {
                            input.value = node.label;
                            document.getElementById('searchBtn')?.click();
                        }
                    }, 100);
                }
            }
        });
    }
}