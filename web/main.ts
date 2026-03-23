import './css/main.css';
import Navigo from 'navigo';
import { AuthModule } from './auth';
import { ChatModule } from './chat';
import { SearchModule } from './search';
import { DocumentsModule } from './documents';
import { ConnectorsModule } from './connectors';
import { GraphModule } from './graph';
import { BasketModule } from './basket';
import { TasksModule } from './tasks';
import { DraftsModule } from './drafts';
import { AdminModule } from './admin';
import { PromptsModule } from './prompts';
import { MemoryModule } from './memory';
import { WorkflowsModule } from './workflows';
import { SidebarModule } from './sidebar';

// --- Initialization ---

// Use slash for root to enable HTML5 History API routing
const router = new Navigo('/');
let appInitialized = false;
let isInitializing = false;

// Anti-loop protection
const RELOAD_KEY = 'kp_reload_count';
const RELOAD_TIME_KEY = 'kp_last_reload_time';
const now = Date.now();
const lastReload = parseInt(localStorage.getItem(RELOAD_TIME_KEY) || '0');
const reloadCount = parseInt(localStorage.getItem(RELOAD_KEY) || '0');

if (now - lastReload < 10000) { // If less than 10s since last reload
    if (reloadCount > 5) {
        localStorage.setItem(RELOAD_KEY, '0');
        document.body.innerHTML = `
            <div style="background:#1a1a1a; color:#ff4444; padding:40px; font-family:sans-serif; height:100vh; display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center;">
                <h1 style="font-size:48px; margin-bottom:16px;">⚠️ Redirect Loop Detected</h1>
                <p style="font-size:18px; color:#ccc; max-width:600px;">Ứng dụng bị khởi động lại quá nhiều lần. Vui lòng xóa Cache trình duyệt hoặc kiểm tra cấu hình mạng.</p>
                <button onclick="localStorage.clear(); location.href='/'" style="margin-top:24px; padding:12px 24px; background:#ff4444; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">Clear Storage & Retry</button>
            </div>
        `;
        throw new Error('Infinite redirect loop detected and halted.');
    }
    localStorage.setItem(RELOAD_KEY, (reloadCount + 1).toString());
} else {
    localStorage.setItem(RELOAD_KEY, '1');
}
localStorage.setItem(RELOAD_TIME_KEY, now.toString());

// Instances
const sidebarModule = new SidebarModule();
const chatModule = new ChatModule('chatMessages', 'chatInput', 'sendBtn');
const searchModule = new SearchModule('searchInput', 'searchBtn', 'searchResults');
const docsModule = new DocumentsModule();
const connectorsModule = new ConnectorsModule();
const graphModule = new GraphModule();
const basketModule = new BasketModule();
const tasksModule = new TasksModule();
const draftsModule = new DraftsModule();
const adminModule = new AdminModule();
const promptsModule = new PromptsModule();
const memoryModule = new MemoryModule();
const workflowModule = new WorkflowsModule();

async function initApp() {
    if (appInitialized || isInitializing) return;
    isInitializing = true;

    console.log('Knowledge Platform: initApp starting...');

    // Check Auth
    if (!AuthModule.isAuthenticated()) {
        console.log('Knowledge Platform: Not authenticated, showing login screen');
        const loginScreen = document.getElementById('login-screen');
        const appShell = document.getElementById('app-shell');
        if (loginScreen) loginScreen.style.display = 'flex';
        if (appShell) appShell.style.display = 'none';
        AuthModule.setupLoginForm('loginEmail', 'loginPassword', 'loginError');
        isInitializing = false;
        return;
    }

    console.log('Knowledge Platform: Authenticated, showing app shell');
    appInitialized = true;
    isInitializing = false;

    // Hide Login, Show App
    const loginScreen = document.getElementById('login-screen');
    const appShell = document.getElementById('app-shell');
    if (loginScreen) loginScreen.style.display = 'none';
    if (appShell) appShell.style.display = 'flex';

    // Global Events
    document.addEventListener('kp-navigate', (e: any) => {
        const path = e.detail.replace(/^\//, ''); // Ensure no double slashes
        router.navigate(`/${path}`);
    });

    // Logout
    document.getElementById('logoutBtn')?.addEventListener('click', () => AuthModule.logout());

    // Setup Sidebar & Global UI
    await sidebarModule.init();
    basketModule.bindGlobalTriggers();

    // Unauthorized handler
    document.addEventListener('kp-unauthorized', () => {
        appInitialized = false;
        AuthModule.logout();
    });

    // Routes
    router
        .on({
            '/chat': () => renderPage('chat', () => chatModule.init()),
            '/search': () => renderPage('search', () => searchModule.init()),
            '/documents': () => renderPage('documents', () => docsModule.loadDocumentsPage()),
            '/connectors': () => renderPage('connectors', () => connectorsModule.init()),
            '/graph': () => renderPage('graph', () => graphModule.init()),
            '/tasks': () => renderPage('tasks', () => tasksModule.init()),
            '/drafts': () => renderPage('drafts', () => draftsModule.init()),
            '/users': () => renderPage('users', () => adminModule.init('users')),
            '/groups': () => renderPage('users', () => adminModule.init('groups')),
            '/prompts': () => renderPage('prompts', () => promptsModule.init()),
            '/memory': () => renderPage('memory', () => memoryModule.init()),
            '/workflows': () => renderPage('workflows', () => workflowModule.init()),
        })
        .resolve();

    // Default route
    if (window.location.pathname === '/' || window.location.pathname === '') {
        console.log('Knowledge Platform: No route found, navigating to /chat');
        router.navigate('/chat');
    }
}

const PAGE_TITLES: Record<string, string> = {
    chat: 'Chat AI',
    search: 'Search',
    documents: 'Knowledge Base',
    connectors: 'Connectors',
    graph: 'Knowledge Graph',
    tasks: 'AI Task Drafts',
    drafts: 'Drafts',
    users: 'Quản lý người dùng',
    groups: 'Quản lý nhóm',
    prompts: 'Skill Prompts',
    memory: 'Project Memory',
    workflows: 'AI Workflows',
};

function renderPage(target: string, initFn?: () => void) {
    // Hide all pages and remove active class
    document.querySelectorAll('.page').forEach(p => {
        (p as HTMLElement).style.display = 'none';
        p.classList.remove('active');
    });
    
    // Show target with correct flex display + active class
    const page = document.getElementById(`page-${target}`);
    if (page) {
        page.style.display = 'flex';
        page.classList.add('active');
    } else {
        console.error(`Page not found: page-${target}`);
    }

    // Nav active state
    document.querySelectorAll('.nav-item').forEach(nav => {
        nav.classList.toggle('active', nav.getAttribute('data-target') === target);
    });

    // Update topbar page title
    const titleEl = document.getElementById('pageTitle');
    if (titleEl) titleEl.textContent = PAGE_TITLES[target] || target;

    if (initFn) initFn();
}

// Start
document.addEventListener('DOMContentLoaded', initApp);