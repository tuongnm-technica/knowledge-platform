/**
 * Điểm bắt đầu của ứng dụng Frontend Knowledge Platform.
 * Quản lý khởi tạo ứng dụng, xác thực người dùng, định tuyến (Routing) bằng Navigo,
 * và điều phối các module chức năng (Chat, Search, Graph, Documents, v.v.).
 */
import './css/main.css';
import Alpine from 'alpinejs';
import Navigo from 'navigo';
import { AuthModule } from './auth';
import { isAllowed } from './permissions';
import { ChatModule } from './chat';
import { SearchModule } from './search';
import { showToast } from './ui';
import { DocumentsModule } from './documents';
import { ConnectorsModule } from './connectors';
import { GraphModule } from './graph';
import { BasketModule } from './basket';
import { TasksModule } from './tasks';
import { DraftsModule } from './drafts';
import { AdminModule } from './admin';
import { PromptsModule } from './prompts';
// import { MemoryModule } from './memory';
import { WorkflowsModule } from './workflows';
import { HistoryModule } from './history';
import { SidebarModule } from './sidebar';
import { ThemeModule } from './theme';
import { ModelsModule } from './models_page';
import { integrationModule } from './integration';
import { pmDashboardModule } from './pm_dashboard';
import { initI18n, i18n } from './i18n';
import { renderMarkdown } from './format';

// --- Alpine.js Setup ---
(window as any).Alpine = Alpine;
// Magic $t can be used as $t('key') in Alpine templates
Alpine.magic('t', () => (window as any).$t);
// Alpine.start() will be called after i18n is ready inside initApp/DOMContentLoaded

// --- Initialization ---

// Use slash for root to enable HTML5 History API routing
const router = new Navigo('/');
let appInitialized = false;
let isInitializing = false;

const sidebarModule = new SidebarModule();
const chatModule = new ChatModule('chatMessages', 'chatInput', 'sendBtn');
const historyModule = new HistoryModule();
const searchModule = new SearchModule('searchInput', 'searchBtn', 'searchResults');
const docsModule = new DocumentsModule();
const connectorsModule = new ConnectorsModule();
const graphModule = new GraphModule();
const basketModule = new BasketModule();
const tasksModule = new TasksModule();
const draftsModule = new DraftsModule();
const adminModule = new AdminModule();
const promptsModule = new PromptsModule();
// const memoryModule = new MemoryModule();
const workflowModule = new WorkflowsModule();
const modelsModule = new ModelsModule();

async function initApp() {
    if (appInitialized || isInitializing) return;
    isInitializing = true;

    console.log('Knowledge Platform: initApp starting...');

    // Check Auth
    if (!AuthModule.isAuthenticated()) {
        console.log('Knowledge Platform: Not authenticated, showing login screen');
        showLoginScreen();
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

    // Set language from user profile before initializing the rest of the UI
    try {
        const user = await AuthModule.getCurrentUser();
        if (user.language) {
            i18n.changeLanguage(user.language);
        }
    } catch (e) {
        console.error("Could not set user language on init", e);
    }

    // Global Events
    document.addEventListener('kp-navigate', (e: any) => {
        const path = e.detail.replace(/^\//, ''); // Ensure no double slashes
        router.navigate(`/${path}`);
    });

    // Logout
    document.getElementById('logoutBtn')?.addEventListener('click', () => AuthModule.logout());

    // Setup Sidebar & Global UI
    await sidebarModule.init();
    ThemeModule.setupThemeToggle('themeToggle');
    basketModule.bindGlobalTriggers();

    // Unauthorized handler
    document.addEventListener('kp-unauthorized', () => {
        appInitialized = false;
        AuthModule.logout();
    });

    // Routes
    router
        .on({
            '/login': () => {
                if (AuthModule.isAuthenticated()) {
                    router.navigate('/chat');
                } else {
                    showLoginScreen();
                }
            },
            '/chat': () => renderPage('chat', () => {
                chatModule.init();
                historyModule.loadHistoryPage('chatHistoryList');
            }),
            '/search': () => renderPage('search', () => searchModule.init()),
            '/documents': () => renderPage('documents', () => docsModule.loadDocumentsPage()),
            '/connectors': () => renderPage('connectors', () => connectorsModule.init()),
            '/graph': () => renderPage('graph', () => graphModule.init()),
            '/tasks': () => renderPage('tasks', () => tasksModule.init()),
            '/drafts': () => renderPage('drafts', () => draftsModule.init()),
            '/users': () => renderPage('users', () => adminModule.init('users')),
            '/groups': () => renderPage('users', () => adminModule.init('groups')),
            '/prompts': () => renderPage('prompts', () => promptsModule.init()),
            // '/memory': () => renderPage('memory', () => memoryModule.init()),
            '/ba-suite': () => renderPage('ba-suite'),
            '/workflows': () => renderPage('workflows', () => workflowModule.init()),
            '/models': () => renderPage('models', () => modelsModule.init()),
            '/integrations': () => renderPage('integration', () => integrationModule.init()),
            '/pm-dashboard': () => renderPage('pm_dashboard', () => pmDashboardModule.init()),
        })
        .resolve();

    // Default route
    if (window.location.pathname === '/' || window.location.pathname === '') {
        console.log('Knowledge Platform: No route found, navigating to /chat');
        router.navigate('/chat');
    }
}

function showLoginScreen() {
    const loginScreen = document.getElementById('login-screen');
    const appShell = document.getElementById('app-shell');
    if (loginScreen) loginScreen.style.display = 'flex';
    if (appShell) appShell.style.display = 'none';
    AuthModule.setupLoginForm('loginEmail', 'loginPassword', 'loginError');
}

function addStepCard(agentName: string, statusText: string, prevAgentName?: string) {
    const container = document.getElementById('step-cards-container');
    if (!container) return;

    let card = document.getElementById(`step-card-${agentName.replace(/\s+/g, '-')}`);
    
    // Mark previous as complete
    if (prevAgentName) {
        const prevCard = document.getElementById(`step-card-${prevAgentName.replace(/\s+/g, '-')}`);
        if (prevCard) {
            prevCard.classList.remove('active');
            prevCard.classList.add('complete');
        }
    }

    if (!card) {
        card = document.createElement('div');
        card.id = `step-card-${agentName.replace(/\s+/g, '-')}`;
        card.className = 'step-card active';
        card.innerHTML = `
            <div style="font-weight: 600; margin-bottom: 5px;">${agentName}</div>
            <div class="step-status" style="font-size: 13px; color: #495057;">${statusText}</div>
        `;
        container.appendChild(card);
    } else {
        const statusEl = card.querySelector('.step-status');
        if (statusEl) statusEl.textContent = statusText;
    }
}

function markAllStepsComplete() {
    document.querySelectorAll('.step-card').forEach(card => {
        card.classList.remove('active');
        card.classList.add('complete');
    });
}

const PAGE_TITLES: Record<string, string> = {
    chat: 'nav.chat',
    search: 'nav.search',
    documents: 'nav.documents',
    connectors: 'nav.connectors',
    graph: 'nav.graph',
    tasks: 'nav.tasks',
    drafts: 'nav.drafts',
    users: 'nav.users',
    groups: 'nav.groups',
    prompts: 'nav.prompts',
    'ba-suite': 'nav.ba-suite',
    workflows: 'nav.workflows',
    models: 'nav.models',
    integration: 'nav.integrations',
    pm_dashboard: 'nav.pm_dashboard',
};

async function renderPage(target: string, initFn?: () => void) {
    // RBAC Check
    try {
        const user = await AuthModule.getCurrentUser();
        if (!isAllowed(user, target)) {
            console.warn(`Unauthorized access attempt to ${target} by role ${user?.role}`);
            router.navigate('/chat');
            return;
        }
    } catch (e) {
        console.error('RBAC Check failed', e);
        // If not authenticated or error, redirect to login is handled by client.ts (401)
        // or we can fallback to chat if just a data error
        if (!AuthModule.isAuthenticated()) {
            router.navigate('/login');
            return;
        }
    }

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
    if (titleEl) titleEl.textContent = (window as any).$t(PAGE_TITLES[target]) || target;

    if (initFn) initFn();
}

// Start
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await initI18n();
    } catch (e) {
        console.warn('i18n initialization failed, fallback to default:', e);
    }
    
    // Start Alpine only after i18n is ready so $t magic works during initial scan
    Alpine.start();
    
    ThemeModule.initTheme();
    initApp();
});

// --- SDLC Workflow Logic ---
;(window as any).showSdlcTab = function(tabId: string) {
    document.querySelectorAll('.result-tab').forEach(el => (el as HTMLElement).style.display = 'none');
    const tab = document.getElementById(tabId);
    if (tab) tab.style.display = 'block';
}

document.addEventListener('click', async (e) => {
    const target = e.target as HTMLElement;
    
    if (target && target.id === 'btn-start-sdlc') {
        const requestInput = document.getElementById('sdlc-request') as HTMLTextAreaElement;
        const requestText = requestInput ? requestInput.value : '';
        const progressDiv = document.getElementById('sdlc-progress');
        const resultsDiv = document.getElementById('sdlc-results');
        
        if (!requestText) {
            showToast((window as any).$t('ba.err_no_request'), "warning");
            return;
        }
        
        if (progressDiv) progressDiv.innerHTML = `<b>🚀 ${(window as any).$t('ba.starting_async')}</b><br/>`;
        if (resultsDiv) resultsDiv.style.display = "none";

        try {
            const stepLiveView = document.getElementById('step-live-view');
            const stepContainer = document.getElementById('step-cards-container');
            
            if (stepLiveView) stepLiveView.style.display = 'block';
            if (stepContainer) stepContainer.innerHTML = ''; 

            // 1. Khởi tạo job
            const response = await fetch('/api/sdlc/async', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    request: requestText,
                    context: "Dự án nội bộ Technica",
                    user_id: "current-user"
                })
            });
            const jobData = await response.json();
            const jobId = jobData.job_id;

            if (progressDiv) progressDiv.innerHTML += `Job ID: <code>${jobId}</code><br/>${(window as any).$t('ba.queued')}<br/>`;

            // 2. Bắt đầu polling
            pollSDLCStatus(jobId);

        } catch (error) {
            if (progressDiv) progressDiv.innerHTML += `<br><span style="color:red">${(window as any).$t('common.error')}: ${error}</span>`;
        }
    }
});

async function pollSDLCStatus(jobId: string) {
    const progressDiv = document.getElementById('sdlc-progress');
    const resultsDiv = document.getElementById('sdlc-results');
    
    let currentAgent = '';

    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/sdlc/jobs/${jobId}`);
            if (!res.ok) return;
            const data = await res.json();

            if (data.status === "completed") {
                clearInterval(interval);
                if (progressDiv) progressDiv.innerHTML += `<b>✅ ${(window as any).$t('ba.complete')}</b><br/>`;
                
                if (resultsDiv) {
                    resultsDiv.style.display = "block";
                    renderSDLCResults(data.result);
                }
                markAllStepsComplete();
                (window as any).showSdlcTab('ba-result');

            } else if (data.status === "failed") {
                clearInterval(interval);
                if (progressDiv) progressDiv.innerHTML += `<br><span style="color:red">❌ ${(window as any).$t('common.error')}: ${data.error}</span>`;
            } else {
                // Phân tích status từ backend: AGENT_BA_START, AGENT_SA_START, AGENT_QA_START
                const status = data.status || '';
                
                if (status === 'AGENT_BA_START' && currentAgent !== 'BA') {
                    currentAgent = 'BA';
                    addStepCard((window as any).$t('ba.agent_ba'), (window as any).$t('ba.step_ba_desc'));
                } else if (status === 'AGENT_SA_START' && currentAgent !== 'SA') {
                    currentAgent = 'SA';
                    addStepCard((window as any).$t('ba.agent_sa'), (window as any).$t('ba.step_sa_desc'), (window as any).$t('ba.agent_ba'));
                } else if (status === 'AGENT_QA_START' && currentAgent !== 'QA') {
                    currentAgent = 'QA';
                    addStepCard((window as any).$t('ba.agent_qa'), (window as any).$t('ba.step_qa_desc'), (window as any).$t('ba.agent_sa'));
                }
                
                if (progressDiv) {
                    progressDiv.scrollTop = progressDiv.scrollHeight;
                }
            }
        } catch (e) {
            console.error("Polling error:", e);
        }
    }, 2000);
}

function renderSDLCResults(result: any) {
    const baResult = document.getElementById('ba-result');
    const saResult = document.getElementById('sa-result');
    const qaResult = document.getElementById('qa-result');

    if (result.ba_document_json) {
        const doc = result.ba_document_json;
        let md = `## 📋 Business Requirements: ${doc.doc_id || 'SRS'}\n\n`;
        (doc.use_cases || []).forEach((uc: any) => {
            md += `### 🏷️ ${uc.id}: ${uc.name}\n`;
            md += `- **Actor**: ${uc.actor}\n`;
            md += `- **Trigger**: ${uc.trigger}\n`;
            md += `- **Preconditions**: ${uc.preconditions?.join(', ') || 'None'}\n\n`;
            md += `#### 🔄 Main Flow:\n`;
            (uc.main_flow || []).forEach((step: string, i: number) => {
                md += `${i + 1}. ${step}\n`;
            });
            md += `\n> **Technical Note**: ${uc.fe_technical_note || 'N/A'}\n\n---\n`;
        });
        if (baResult) baResult.innerHTML = renderMarkdown(md);
    }

    if (result.sa_document_json) {
        const doc = result.sa_document_json;
        let md = `## 🛠️ Solution Design: ${doc.design_id || 'SA'}\n\n`;
        md += `### 🏛️ Architecture Overview\n${doc.architecture_overview || 'N/A'}\n\n`;
        md += `### 🔌 API Contracts\n`;
        (doc.api_contracts || []).forEach((api: any) => {
            md += `#### \`${api.method || 'GET'}\` ${api.path || '/'}\n`;
            md += `- **Description**: ${api.description || ''}\n`;
            md += `- **Payload**: \`${JSON.stringify(api.payload || {})}\` \n`;
            md += `- **Response**: \`${JSON.stringify(api.response || {})}\` \n\n`;
        });
        if (saResult) saResult.innerHTML = renderMarkdown(md);
    }

    if (result.qa_document_json) {
        const doc = result.qa_document_json;
        let md = `## 🧪 Quality Assurance: ${doc.test_plan_id || 'QA'}\n\n`;
        md += `| Test ID | Type | Scenario | Expected Result |\n|---|---|---|---|\n`;
        (doc.test_cases || []).forEach((tc: any) => {
            md += `| **${tc.tc_id}** | ${tc.type} | ${tc.steps?.join('; ') || ''} | ${tc.expected_result || ''} |\n`;
        });
        if (qaResult) qaResult.innerHTML = renderMarkdown(md);
    }
}