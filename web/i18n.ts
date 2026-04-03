import i18next from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import HttpApi from 'i18next-http-backend';
import { API, authFetch } from './client';

export const i18n = i18next;

// Pre-expose $t for UI components
(window as any).i18n = i18next;
(window as any).$t = (key: string, options?: any) => {
    if (!i18next.isInitialized) {
        console.debug('i18next not initialized yet, returning key:', key);
        return key;
    }
    return i18next.t(key, options);
};

/**
 * Global function to change application language.
 * Can be called from anywhere (login, topbar, settings).
 */
(window as any).changeLanguage = async (lng: string) => {
    console.log(`Changing language to: ${lng}`);
    
    // 1. Persist to localStorage immediately
    localStorage.setItem('i18nextLng', lng);
    
    // 2. Change language in i18next instance if ready
    if (i18next.isInitialized) {
        await i18next.changeLanguage(lng);
    }
    
    // 3. Persist to backend if user is authenticated
    try {
        const token = localStorage.getItem('kp_access_token');
        if (token) {
            // We use a silent background update
            await authFetch(`${API}/auth/me`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ language: lng })
            });
        }
    } catch (e) {
        // Silently fail if not logged in or network error, localStorage is primary for session
        console.debug('Language persistence to server skipped or failed');
    }
    
    // 4. Notify Alpine.js components
    document.dispatchEvent(new CustomEvent('kp-lang-changed', { detail: lng }));
    
    // 5. Force a page reload to re-run all Vanilla JS rendering logic 
    // This is the most reliable way to update a multi-module SPA without React/Vue
    setTimeout(() => window.location.reload(), 150);
};

export async function initI18n(initialLang?: string) {
    await i18next
        .use(HttpApi)
        .use(LanguageDetector)
        .init({
            fallbackLng: 'vi',
            lng: initialLang,
            supportedLngs: ['vi', 'en', 'jp'],
            debug: false,
            interpolation: {
                escapeValue: false,
            },
            backend: {
                loadPath: '/locales/{{lng}}.json',
            },
            load: 'languageOnly',
            detection: {
                order: [ 'querystring', 'localStorage', 'navigator'],
                caches: ['localStorage'],
                lookupLocalStorage: 'i18nextLng'
            }
        });

    return i18next;
}
