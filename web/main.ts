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

const router = new Navigo('/', { hash: true });

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
    // Check Auth
    if (!AuthModule.isAuthenticated()) {
        const loginScreen = document.getElementById('login-screen');
        if (loginScreen) loginScreen.style.display = 'flex';
        AuthModule.setupLoginForm('loginEmail', 'loginPassword', 'loginError');
        return;
    }

    // Hide Login, Show App
    const loginScreen = document.getElementById('login-screen');
    const appShell = document.getElementById('app-shell');
    if (loginScreen) loginScreen.style.display = 'none';
    if (appShell) appShell.style.display = 'flex';

    // Global Events
    document.addEventListener('kp-navigate', (e: any) => {
        router.navigate(e.detail);
    });

    // Logout
    document.getElementById('logoutBtn')?.addEventListener('click', () => AuthModule.logout());

    // Setup Sidebar & Global UI
    await sidebarModule.init();
    basketModule.bindGlobalTriggers();

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
            '/groups': () => renderPage('groups', () => adminModule.init('groups')),
            '/prompts': () => renderPage('prompts', () => promptsModule.init()),
            '/memory': () => renderPage('memory', () => memoryModule.init()),
            '/workflows': () => renderPage('workflows', () => workflowModule.init()),
        })
        .resolve();

    // Default route
    if (!window.location.hash || window.location.hash === '#/') {
        router.navigate('/chat');
    }
}

function renderPage(target: string, initFn?: () => void) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => (p as HTMLElement).style.display = 'none');
    
    // Show target
    const page = document.getElementById(`page-${target}`);
    if (page) {
        page.style.display = 'block';
    } else {
        console.error(`Page not found: page-${target}`);
    }

    // Nav active state
    document.querySelectorAll('.nav-item').forEach(nav => {
        nav.classList.toggle('active', nav.getAttribute('data-target') === target);
    });

    if (initFn) initFn();
}

// Start
document.addEventListener('DOMContentLoaded', initApp);