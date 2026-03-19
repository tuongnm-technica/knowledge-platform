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
import { ConnectorsModule } from './connectors'; // Sẽ update Connectors sau nếu cần
import { AdminAlpine } from './admin';
import { HistoryModule } from './history';
import { MemoryModule } from './memory';
import { PromptsModule } from './prompts';
import { showToast, escapeHtml, kpOpenModal, kpConfirm, kpPrompt } from './ui';
import { API } from './client';

// --- Tính năng Health Check hệ thống ---
async function checkHealth(): Promise<void> {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 5000);

    try {
        const r = await fetch(`${API}/health`, { signal: controller.signal });
        clearTimeout(timeoutId);

        if (!r.ok) throw new Error(`HTTP Error: ${r.status}`);

        const d = await r.json();
        const coreOk = d.status === 'ok' || (d.components?.postgresql === 'ok' && d.components?.qdrant === 'ok') || d.postgresql === 'ok';
        
        const dot = document.getElementById('statusDot');
        const txt = document.getElementById('statusText');
        if (d.status === 'degraded') {
            if (dot) dot.style.background = 'var(--warning)';
            if (txt) txt.textContent = 'Hệ thống hoạt động (một phần)';
        } else if (coreOk) {
            if (dot) dot.style.background = 'var(--success)';
            if (txt) txt.textContent = 'Hệ thống hoạt động';
        } else {
            if (dot) dot.style.background = 'var(--danger)';
            if (txt) txt.textContent = 'Hệ thống gặp lỗi';
        }
    } catch (e) {
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
    // (Lưu ý: trong HTML của bạn không có thẻ <form>, nên chúng ta gán sự kiện trực tiếp cho nút bấm)
    document.getElementById('loginBtn')?.addEventListener('click', async () => {
        const email = (document.getElementById('loginEmail') as HTMLInputElement).value;
        const pwd = (document.getElementById('loginPwd') as HTMLInputElement).value;
        try {
            await AuthModule.login(email, pwd);
            window.location.reload(); // Tải lại trang để áp dụng token mới
        } catch (e: any) {
            const err = document.getElementById('loginError');
            if (err) { err.textContent = e.message; err.style.display = 'block'; }
        }
    });

    document.getElementById('loginEmail')?.addEventListener('keydown', (e: KeyboardEvent) => {
        if (e.key === 'Enter') document.getElementById('loginPwd')?.focus();
    });

    document.getElementById('loginPwd')?.addEventListener('keydown', (e: KeyboardEvent) => {
        if (e.key === 'Enter') document.getElementById('loginBtn')?.click();
    });

    document.getElementById('logoutBtn')?.addEventListener('click', () => AuthModule.logout());
    document.getElementById('themeToggle')?.addEventListener('click', () => ThemeModule.toggleTheme());

    // 2. Khởi tạo Modules
    const chat = new ChatModule('chatMessages', 'chatInput', 'sendBtn');
    const search = new SearchModule('searchInput', 'searchBtn', 'searchResults');
    const graph = new GraphModule();
    const connectors = new ConnectorsModule();
    const history = new HistoryModule();
    const memory = new MemoryModule();
    const prompts = new PromptsModule();

    // Khởi tạo AlpineJS
    (window as any).Alpine = Alpine;
    Alpine.store('badges', { tasks: 0, drafts: 0, basket: 0 }); // Lưu trữ Badge toàn cục
    Alpine.data('tasksModule', TasksAlpine); // Đăng ký module Tasks
    Alpine.data('basketModule', BasketAlpine);
    Alpine.data('draftsModule', DraftsAlpine);
    Alpine.data('adminModule', AdminAlpine);
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

        // Tải dữ liệu tương ứng khi chuyển tab
        if (target === 'tasks') { document.dispatchEvent(new CustomEvent('kp-refresh-tasks')); }
        else if (target === 'drafts') { document.dispatchEvent(new CustomEvent('kp-refresh-drafts')); }
        else if (target === 'graph') { graph.loadGraphDashboard(true); }
        // Giỏ hàng được quản lý qua biến isDrawerOpen của BasketAlpine
        else if (target === 'connectors') { connectors.loadConnectorStats(); }
        else if (target === 'users') { admin.loadUsersAdmin(); }
        else if (target === 'prompts') { prompts.loadPromptsPage(); }
        else if (target === 'history') { history.loadHistoryPage(); }
        else if (target === 'memory') { 
            memory.loadMemoryPage(); 
        }
    };

    // Đăng ký các Routes
    router
        .on('/', () => { router.navigate('/chat'); }) // Trang chủ mặc định redirect về /chat
        .on('/:page', (match) => {
            const page = match?.data?.page || 'chat';
            renderPage(page);
        })
        .resolve();

    // Bắt sự kiện chuyển trang từ thanh Menu
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const target = (e.currentTarget as HTMLElement).getAttribute('data-target');
            if (target) router.navigate(`/${target}`);
        });
    });

    // Global event để các module khác tự chuyển trang mà không cần gọi window
    document.addEventListener('kp-navigate', (e: any) => {
        router.navigate(`/${e.detail}`);
    });
});