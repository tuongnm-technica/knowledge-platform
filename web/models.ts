export interface User {
    id: string;
    email: string;
    display_name: string;
    role: string;
    is_admin?: boolean;
    is_active?: boolean;
}

export interface ChatMessage {
    id: string;
    role: 'user' | 'assistant' | 'system';
    content: string;
    created_at: string;
}

export interface Task {
    id: string;
    title?: string;
    source?: string;
    status?: string;
    created_at?: string;
}

export interface Draft {
    id: string;
    doc_type?: string;
    title?: string;
    content?: string;
    status?: string;
    created_at?: string;
    updated_at?: string;
}

export interface GraphNode {
    id: string;
    label: string;
    type?: string;
    x?: number;
    y?: number;
    vx?: number;
    vy?: number;
    radius?: number;
    color?: string;
    pinned?: boolean;
    url?: string;
    meta?: any;
}

export interface GraphLink {
    source: string | GraphNode;
    target: string | GraphNode;
    label?: string;
}

export interface BasketItem {
    id: string;
    title: string;
}

export interface ConnectorInstance {
    instance_id: string;
    instance_name: string;
    connector_type: string;
    base_url?: string;
    status?: { code?: string; label?: string };
    sync?: { latest_run?: any; running?: boolean; is_running?: boolean };
    data?: { documents?: number; chunks?: number };
    config?: any;
}

export interface ConnectorTab {
    type: string;
    label?: string;
    instances: ConnectorInstance[];
    config?: any;
}

export interface Group {
    id: string;
    name: string;
}

export interface PromptSkill {
    id: string;
    name: string;
    description?: string;
    type?: string;
}

export interface MemoryItem {
    id: string;
    key: string;
    value: string;
    type: 'actor' | 'term' | 'rule' | string;
}

export interface ChatSession {
    id: string;
    title?: string;
    created_at?: string;
    updated_at?: string;
}