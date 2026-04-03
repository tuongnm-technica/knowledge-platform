import i18next from 'i18next';
import LanguageDetector from 'i18next-browser-languagedetector';
import HttpApi from 'i18next-http-backend';
import { API, authFetch } from './client';

export const i18n = i18next;

export async function initI18n(initialLang?: string) {
    await i18next
        .use(HttpApi)
        .use(LanguageDetector)
        .init({
            fallbackLng: 'vi',
            lng: initialLang, // Use user preference if available
            supportedLngs: ['vi', 'en', 'jp'],
            debug: false,
            interpolation: {
                escapeValue: false,
            },
            backend: {
                loadPath: '/locales/{{lng}}.json',
            },
            detection: {
                order: ['querystring', 'localStorage', 'navigator'],
                caches: ['localStorage'],
            }
        });

    // Global $t function for Alpine.js and Vanilla TS
    (window as any).$t = (key: string, options?: any) => i18next.t(key, options);
    (window as any).changeLanguage = async (lng: string) => {
        await i18next.changeLanguage(lng);
        // Persist to DB if logged in
        try {
            const token = localStorage.getItem('kp_access_token');
            if (token) {
                await authFetch(`${API}/auth/me`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ language: lng })
                });
            }
        } catch (e) {
            console.warn('Failed to persist language preference to DB', e);
        }
        // Emit event for Alpine reactivity
        document.dispatchEvent(new CustomEvent('kp-lang-changed', { detail: lng }));
    };

    return i18next;
}
