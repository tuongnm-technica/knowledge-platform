/**
 * Frontend Configuration Module
 * Centralizes all numeric constants, polling intervals, and business logic thresholds.
 */
export const Config = {
    // Global polling interval for most async status checks (Connectors, Tasks, etc)
    POLLING_INTERVAL_MS: 5000,
    
    // Chat-specific polling (needs to feel more real-time)
    CHAT_POLLING_INTERVAL_MS: 1000,
    
    // Maximum attempts for job status polling before timing out (600 = 10 minutes if 1s/poll)
    MAX_POLL_ATTEMPTS: 600,
    
    // UI Thresholds
    TOAST_DURATION_MS: 3000,
    MODAL_ANIMATION_DURATION_MS: 300,
};
