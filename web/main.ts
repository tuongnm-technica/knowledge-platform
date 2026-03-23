// Gom toàn bộ CSS vào đây để Vite quản lý (HMR & Minify)
import './css/main.css';
import './css/components/buttons.css';
import './css/components/forms.css';
import './css/components/login.css';
import './css/components/modals.css';
import './css/components/toasts.css';
import './css/modules/admin.css';
import './css/modules/basket.css';
import './css/modules/chat.css';
import './css/modules/connectors.css';
import './css/modules/drafts.css';
import './css/modules/graph.css';
import './css/modules/history.css';
import './css/modules/search.css';
import './css/modules/tasks.css';
import './css/modules/prompts.css';
import './css/modules/documents.css';

import Navigo from 'navigo';
import Alpine from 'alpinejs';
import { AuthModule } from './auth';
import { ThemeModule } from './theme';
import { ChatModule } from './chat';
import { SearchModule } from './search';
import { TasksAlpine } from './tasks';
import { DraftsAlpine } from './drafts';
import { GraphModule } from './graph';
import { BasketAlpine } from './basket'; 
import { ConnectorsModule } from './connectors';
import { AdminAlpine } from './admin'; 
// HistoryModule removed
import { MemoryModule } from './memory';
import { PromptsModule } from './prompts';
import { WorkflowsModule } from './workflows';
import { DocumentsModule } from './documents';
import { API } from './client';

// Bắt lỗi module không load được
window.addEventListener('error', function(e) {
    if (e.message && (e.message.includes('module') || e.message.includes('import'))) {
        const err = document.getElementById('loginError');
        if (err) {
            err.textContent = 'Lỗi nạp file giao diện. Bấm F12 mở tab Console để xem file nào bị thiếu.';
            err.style.display = 'block';
        }
    }
}, true);

// --- Tính năng Health Check hệ thống ---
async function checkHealth(): Promise<void> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    try {
        const r = await fetch(`${API}/health`, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!r.ok) throw new Error(`HTTP Error: ${r.status}`);

        const d = await r.json() as { status: string, components?: any, postgresql?: string };
        const coreOk = d.status === 'ok' || (d.components?.postgresql === 'ok' && d.components?.qdrant === 'ok') || d.postgresql === 'ok';
        
        const dot = document.getElementById('statusDot');
        const txt = document.getElementById('statusText');
        if (d.status === 'degraded') {
            if (dot) dot.style.background = 'var(--warn)';
            if (txt) txt.textContent = 'Hệ thống hoạt động (một phần)';
        } else if (coreOk) {
            if (dot) dot.style.background = 'var(--success)';
            if (txt) txt.textContent = 'Hệ thống hoạt động';
        } else {
            if (dot) dot.style.background = 'var(--danger)';
            if (txt) txt.textContent = 'Hệ thống gặp lỗi';
        }
    } catch (err) {
        const dot = document.getElementById('statusDot');
        const txt = document.getElementById('statusText');
        if (dot) dot.style.background = 'var(--danger)';
        if (txt) txt.textContent = 'Không kết nối được API';
    }
}

// Khởi tạo toàn bộ ứng dụng khi DOM đã sẵn sàng
document.addEventListener('DOMContentLoaded', () => {
    
    // 1. Giao diện & Đăng nhập
    ThemeModule.initTheme();
    
    // Hook theme toggle for login screen (before auth check)
    document.getElementById('loginThemeToggle')?.addEventListener('click', () => ThemeModule.toggleTheme());
    
    if (!AuthModule.isAuthenticated()) {
        const loginScreen = document.getElementById('login-screen');
        if (loginScreen) loginScreen.style.display = 'flex';
    } else {
        const loginScreen = document.getElementById('login-screen');
        if (loginScreen) loginScreen.style.display = 'none';
        
        // Chạy Health Check nếu đã đăng nhập
        checkHealth();
    }

    // Mapping Login Form 
    document.getElementById('loginBtn')?.addEventListener('click', async () => {
        const emailEl = document.getElementById('loginEmail') as HTMLInputElement;
        const pwdEl = document.getElementById('loginPwd') as HTMLInputElement;
        const email = emailEl ? emailEl.value : '';
        const pwd = pwdEl ? pwdEl.value : '';
        try {
            await AuthModule.login(email, pwd);
            window.location.reload(); // Tải lại trang để áp dụng token mới
        } catch (err) {
            const error = err as Error;
            const errEl = document.getElementById('loginError');
            if (errEl) { errEl.textContent = error.message; errEl.style.display = 'block'; }
        }
    });

    document.getElementById('loginEmail')?.addEventListener('keydown', (e: KeyboardEvent) => {
        if (e.key === 'Enter') (document.getElementById('loginPwd') as HTMLInputElement)?.focus();
    });

    document.getElementById('loginPwd')?.addEventListener('keydown', (e: KeyboardEvent) => {
        if (e.key === 'Enter') (document.getElementById('loginBtn') as HTMLButtonElement)?.click();
    });

    document.getElementById('logoutBtn')?.addEventListener('click', () => AuthModule.logout());
    document.getElementById('themeToggle')?.addEventListener('click', () => ThemeModule.toggleTheme());

    // 2. Khởi tạo Modules
    new ChatModule('chatMessages', 'chatInput', 'sendBtn');
    new SearchModule('searchInput', 'searchBtn', 'searchResults');
    const graph = new GraphModule();
    const connectors = new ConnectorsModule();
    // const history = new HistoryModule(); // Removed
    const memory = new MemoryModule();
    const prompts = new PromptsModule();
    const workflows = new WorkflowsModule();
    const documents = new DocumentsModule();

    // Populate Sidebars
    if (AuthModule.isAuthenticated()) {
        // history.loadHistoryPage(); // Removed
    }

    // Khởi tạo AlpineJS
    const win = window as any;
    win.Alpine = Alpine;
    Alpine.store('badges', { tasks: 0, drafts: 0, basket: 0 }); // Lưu trữ Badge toàn cục
    Alpine.data('tasksModule', TasksAlpine as any); // Đăng ký module Tasks
    Alpine.data('draftsModule', DraftsAlpine as any); // Đăng ký module Drafts
    Alpine.data('basketModule', BasketAlpine as any); // Đăng ký module Basket
    Alpine.data('adminModule', AdminAlpine as any);   // Đăng ký module Admin
    Alpine.start();

    // Khởi tạo Router (Sử dụng History API, không dùng hash #)
    const router = new Navigo('/', { hash: false });

    // Hàm render UI tương ứng với từng Route
    const renderPage = (target: string) => {
        const title = document.getElementById('pageTitle');
        if (title) title.textContent = target.charAt(0).toUpperCase() + target.slice(1);
        
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
        const page = document.getElementById('page-' + target);
        if (page) page.classList.add('active');

        document.querySelectorAll('.nav-item').forEach(li => li.classList.remove('active'));
        const navEl = document.querySelector(`.nav-item[data-target="${target}"]`);
        if (navEl) navEl.classList.add('active');

        // Tải dữ liệu tương ứng khi chuyển tab (Chỉ khi đã login)
        if (!AuthModule.isAuthenticated()) return;

        if (target === 'tasks') { document.dispatchEvent(new CustomEvent('kp-refresh-tasks')); }
        else if (target === 'drafts') { document.dispatchEvent(new CustomEvent('kp-refresh-drafts')); }
        else if (target === 'graph') { graph.loadGraphDashboard(); }
        else if (target === 'basket') { document.dispatchEvent(new CustomEvent('kp-refresh-basket')); }
        else if (target === 'connectors') { connectors.loadConnectorStats(); }
        else if (target === 'users') { document.dispatchEvent(new CustomEvent('kp-refresh-users')); }
        else if (target === 'prompts') { prompts.loadPromptsPage(); }
        else if (target === 'workflows') { workflows.loadWorkflowsPage(); }
        // target history removed
        else if (target === 'memory') { 
            memory.loadMemoryPage(); 
        }
        else if (target === 'documents') { documents.loadDocumentsPage(); }
    };

    // Đăng ký các Routes
        // Capturing local variables for the router callbacks

        router
            .on('/', () => { 
                if (AuthModule.isAuthenticated()) {
                    router.navigate('/chat'); 
                } else {
                    const loginScreen = document.getElementById('login-screen');
                    if (loginScreen) loginScreen.style.display = 'flex';
                }
            }) // Trang chủ mặc định redirect về /chat nếu đã login
            .on('/history', () => {
                router.navigate('/chat');
            })
            .on('/documents', () => {
                renderPage('documents');
                documents.loadDocumentsPage();
            })
            .on('/:page', (match) => {
                const page = (match && match.data && match.data.page) || 'chat';
                renderPage(page);
            })
            .resolve();

        // Batch delete docs
        document.getElementById('batchDeleteDocsBtn')?.addEventListener('click', () => {
            documents.batchDelete();
        });

    // Đăng ký EventListener thay thế cho việc gán vào window object
    // document.addEventListener('kp-refresh-history', () => {
    //     history.loadHistoryPage();
    // });
    
    document.addEventListener('kp-show-toast', (e: Event) => {
        const detail = (e as CustomEvent).detail;
        const { message, type } = detail;
        console.log(`[${type}] ${message}`); 
    });

    document.addEventListener('kp-unauthorized', () => {
        const loginScreen = document.getElementById('login-screen');
        if (loginScreen) loginScreen.style.display = 'flex';
        // Xóa data cũ (tùy chọn để bảo mật)
        document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    });

    // Bắt sự kiện chuyển trang từ thanh Menu
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = (e.currentTarget as HTMLElement).getAttribute('data-target');
            if (target) router.navigate(`/${target}`);
        });
    });

    // Global event để các module khác tự chuyển trang mà không cần gọi window
    document.addEventListener('kp-navigate', (e: Event) => {
        const detail = (e as CustomEvent).detail;
        router.navigate(`/${detail}`);
    });
});