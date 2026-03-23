/**
 * web/models.ts
 * 
 * TypeScript interfaces reflecting Backend Pydantic models and DB schemas.
 * 1-to-1 mapping ensures type safety across the stack.
 */

// --- Authentication & User ---

export interface User {
    id: string; // Matches BE 'id'
    email: string;
    display_name: string | null;
    role: string;
    is_admin: boolean;
    group_ids?: string[];
    groups?: Group[];
}

export interface AuthResponse extends User {
    access_token: string;
    refresh_token: string;
    token_type: string;
}

// --- Search & Chat ---

export interface SearchSource {
    id?: string;
    document_id?: string;
    title?: string;
    source?: string;
    url?: string;
    score?: number;
    snippet?: string;
    author?: string;
}

export interface SearchResult extends SearchSource {
    content?: string;
    author?: string;
    source_type?: string;
    filename?: string;
    source_id?: string;
    score_breakdown?: Record<string, any>;
}

export interface AskJobResponse {
    job_id: string;
    session_id: string;
}

export interface AskResponse {
    answer: string;
    sources: SearchSource[];
    rewritten_query: string;
    agent_steps: any[];
    agent_plan: any[];
    used_tools: string[];
    session_id: string | null;
}

export interface JobStatusResponse {
    job_id: string;
    status: 'queued' | 'running' | 'completed' | 'failed';
    progress: number;
    thoughts: any[];
    result: AskResponse | string | null;
    error: string | null;
}

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    created_at: string;
    agent_plan?: any[];
    sources?: SearchSource[];
    rewritten_query?: string;
}

export interface ChatSession {
    id: string;
    title: string;
    created_at: string;
    updated_at: string;
    messages?: ChatMessage[];
}

// --- Tasks ---

export interface Task {
    id: string;
    title: string;
    source: string;
    source_id: string;
    status: 'pending' | 'approved' | 'rejected';
    created_at: string;
    updated_at: string;
    meta: Record<string, any>;
    description?: string;
    suggested_assignee?: string;
    issue_type?: string;
    jira_project?: string;
    source_summary?: string;
}

// --- Drafts ---

export interface Draft {
    id: string;
    doc_type: string;
    title: string;
    content: string;
    status: 'draft' | 'review' | 'approved' | 'published' | 'rejected';
    created_at: string;
    updated_at: string;
    user_id?: string;
}

// --- Connectors ---

export interface SyncRun {
    id: number;
    status: string;
    started_at: string | null;
    finished_at: string | null;
    last_sync_at: string | null;
    fetched: number;
    indexed: number;
    errors: number;
}

export interface ConnectorInstance {
    id: string; // connector_key (e.g. "confluence:uuid")
    instance_id: string; // uuid only
    instance_name: string;
    connector_type: string;
    base_url: string;
    configured: boolean;
    status: {
        code: string;
        tone: 'success' | 'warning' | 'danger' | 'info' | 'neutral';
        label: string;
        message: string;
    };
    sync: {
        schedule_label: string;
        running: boolean;
        latest_run: SyncRun | null;
        latest_completed_run: SyncRun | null;
        history: SyncRun[];
    };
    data: {
        documents: number;
        chunks: number;
    };
    config: {
        target_label: string;
        target_value: string;
        scope_label?: string;
        auth_label: string;
        auth_value: string;
        username: string;
        auth_type: string;
        extra: Record<string, any>;
    };
    state: {
        enabled: boolean;
        auto_sync: boolean;
        schedule_hour: number | null;
        schedule_minute: number | null;
        schedule_tz: string;
        selection: Record<string, any>;
    };
}

export interface ConnectorTab {
    type: string;
    label: string;
    instances: ConnectorInstance[];
}

// --- Knowledge Graph & Basket ---

export interface GraphNode {
    id: string;
    label: string;
    type?: string;
    kind?: string;
    subkind?: string;
    size?: number;
    color?: string;
    radius?: number;
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
    fx?: number | null;
    fy?: number | null;
}

export interface GraphLink {
    source: string | GraphNode;
    target: string | GraphNode;
    type?: string;
    label?: string;
}

export interface BasketItem {
    id: string; // document_id
    title: string;
}

// --- Admin & Misc ---

export interface Group {
    id: string;
    name: string;
}

export interface PromptSkill {
    id: string;
    name: string;
    description: string;
    template: string;
    type?: string;
    doc_type?: string;
    label?: string;
}

export interface MemoryItem {
    type: string;
    key: string;
    value: string;
}

// --- AI Workflows ---

export interface AIWorkflowNode {
    id?: string;
    step_order: number;
    name: string;
    model_override?: string | null;
    system_prompt: string;
}

export interface AIWorkflow {
    id: string;
    name: string;
    description: string;
    trigger_type: string;
    nodes?: AIWorkflowNode[];
    created_at?: string;
    updated_at?: string;
    updated_by?: string;
}