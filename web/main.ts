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
import { HistoryModule } from './history';
import { SidebarModule } from './sidebar';

// --- Initialization ---

// Use slash for root to enable HTML5 History API routing
const router = new Navigo('/');
let appInitialized = false;
let isInitializing = false;

// Anti-loop protection
// ... (omitting reload logic for brevity if possible, but replace_file_content needs exact match)
// Actually I will just replace the module instantiation section

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
            '/memory': () => renderPage('memory', () => memoryModule.init()),
            '/ba-suite': () => renderPage('ba-suite'),
            '/workflows': () => renderPage('workflows', () => workflowModule.init()),
        })
        .resolve();

    // Default route
    if (window.location.pathname === '/' || window.location.pathname === '') {
        console.log('Knowledge Platform: No route found, navigating to /chat');
        router.navigate('/chat');
    }
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
    'ba-suite': 'Auto Work - Dashboard',
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

// --- SDLC Workflow Logic ---
;(window as any).showSdlcTab = function(tabId: string) {
    document.querySelectorAll('.result-tab').forEach(el => (el as HTMLElement).style.display = 'none');
    const tab = document.getElementById(tabId);
    if (tab) tab.style.display = 'block';
}

document.addEventListener('click', async (e) => {
    const target = e.target as HTMLElement;
    
    // Sử dụng event delegation để bắt click dù DOM load sau
    if (target && target.id === 'btn-start-sdlc') {
        const requestInput = document.getElementById('sdlc-request') as HTMLTextAreaElement;
        const requestText = requestInput ? requestInput.value : '';
        const progressDiv = document.getElementById('sdlc-progress');
        const resultsDiv = document.getElementById('sdlc-results');
        
        if (!requestText) return alert("Vui lòng nhập yêu cầu nghiệp vụ!");
        
        if (progressDiv) progressDiv.innerHTML = "<b>🚀 Đang khởi động Multi-Agent Swarm...</b><br/>";
        if (resultsDiv) resultsDiv.style.display = "none";

        try {
            const stepLiveView = document.getElementById('step-live-view');
            const stepContainer = document.getElementById('step-cards-container');
            
            if (stepLiveView) stepLiveView.style.display = 'block';
            if (stepContainer) stepContainer.innerHTML = ''; // Reset

            const response = await fetch('/api/sdlc/stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    request: requestText,
                    context: "Dự án nội bộ Technica",
                    user_id: "current-user"
                })
            });

            if (!response.body) throw new Error("Trình duyệt không hỗ trợ streaming");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let isDone = false;

            while (!isDone) {
                const { value, done } = await reader.read();
                isDone = done;
                if (value) {
                    const chunk = decoder.decode(value, { stream: true });
                    const events = chunk.split("\n\n");
                    
                    for (const event of events) {
                        if (event.startsWith("data: ")) {
                            try {
                                const data = JSON.parse(event.replace("data: ", ""));
                                if (progressDiv) {
                                    progressDiv.innerHTML += `👉 ${data.status}<br/>`;
                                    progressDiv.scrollTop = progressDiv.scrollHeight;
                                }
                                
                                if (data.status.includes("BA:")) {
                                    addStepCard("Business Analysis Agent", data.status);
                                } else if (data.status.includes("SA:")) {
                                    addStepCard("System Architect Agent", data.status, "Business Analysis Agent");
                                } else if (data.status.includes("QA:")) {
                                    addStepCard("Quality Assurance Agent", data.status, "System Architect Agent");
                                }

                                if (data.status === "DONE") {
                                    if (progressDiv) progressDiv.innerHTML += `<b>✅ Hoàn tất luồng Agent! Đang tải tài liệu JSON...</b>`;
                                    markAllStepsComplete();
                                    fetchFinalSDLCDocuments(requestText);
                                }
                            } catch (e) {
                                console.error("Parse error:", e);
                            }
                        }
                    }
                }
            }
        } catch (error) {
            if (progressDiv) progressDiv.innerHTML += `<br><span style="color:red">Lỗi: ${error}</span>`;
        }
    }
});

async function fetchFinalSDLCDocuments(requestText: string) {
    try {
        const res = await fetch('/api/sdlc/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ request: requestText, user_id: "current-user" })
        });
        
        const finalData = await res.json();
        
        if (finalData.status === "success") {
            const resultsDiv = document.getElementById('sdlc-results');
            if (resultsDiv) resultsDiv.style.display = "block";
            
            ;(window as any).showSdlcTab('ba-result');
            
            const baResult = document.getElementById('ba-result');
            const saResult = document.getElementById('sa-result');
            const qaResult = document.getElementById('qa-result');
            
            if (baResult) baResult.textContent = JSON.stringify(finalData.data.ba_document_json, null, 2);
            if (saResult) saResult.textContent = JSON.stringify(finalData.data.sa_document_json, null, 2);
            if (qaResult) qaResult.textContent = JSON.stringify(finalData.data.qa_document_json, null, 2);
        }
    } catch (error) {
        const progressDiv = document.getElementById('sdlc-progress');
        if (progressDiv) progressDiv.innerHTML += `<br><span style="color:red">Lỗi tải dữ liệu JSON: ${error}</span>`;
    }
}