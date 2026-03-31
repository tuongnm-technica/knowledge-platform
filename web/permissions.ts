/**
 * web/permissions.ts
 * 
 * Centralized Role-Based Access Control (RBAC) definitions.
 * This file ensures consistency between the Sidebar (visibility) and Router (access guards).
 */

import { User } from './models';

/**
 * High-level page targets that correspond to:
 * 1. data-target attribute in sidebar.html
 * 2. Route paths in main.ts
 */
export type PageTarget = 
    | 'chat' 
    | 'search' 
    | 'documents' 
    | 'graph' 
    | 'tasks' 
    | 'drafts' 
    | 'memory' 
    | 'ba-suite' 
    | 'workflows' 
    | 'users' 
    | 'connectors' 
    | 'prompts';

/**
 * Mapping of roles to allowed page targets.
 * Admin users bypass this and always have access to everything.
 */
export const PERMISSIONS: Record<string, PageTarget[]> = {
    'knowledge_architect': ['chat', 'search', 'documents', 'graph', 'prompts', 'memory'],
    'pm_po': ['chat', 'search', 'documents', 'graph', 'tasks', 'drafts', 'memory', 'ba-suite', 'workflows'],
    'ba_sa': ['chat', 'search', 'documents', 'graph', 'tasks', 'drafts', 'ba-suite', 'workflows'],
    'dev_qa': ['chat', 'search', 'documents', 'graph', 'tasks'],
    'standard': ['chat', 'search', 'documents', 'graph'],
};

/**
 * Checks if a user is allowed to access a specific target.
 */
export function isAllowed(user: User | null, target: string): boolean {
    if (!user) return false;
    
    // System admins and Root admins always have access
    if (user.is_admin || user.role === 'system_admin' || user.role === 'admin') {
        return true;
    }

    const role = (user.role || 'standard').toLowerCase();
    const allowedTargets = PERMISSIONS[role] || PERMISSIONS['standard'];
    return (allowedTargets as string[]).includes(target);
}

/**
 * List of targets that are strictly reserved for admins.
 * Non-admins can NEVER see these even if they are somehow in their role's list.
 */
export const ADMIN_ONLY_TARGETS: PageTarget[] = ['users', 'connectors'];
