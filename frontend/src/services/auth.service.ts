import axios from 'axios';
import pkceChallenge from 'pkce-challenge';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5050';
const KEYCLOAK_URL = process.env.REACT_APP_KEYCLOAK_URL || 'http://localhost:8080';
const REALM = process.env.REACT_APP_KEYCLOAK_REALM || 'reports-realm';
const CLIENT_ID = process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'reports-backend';

// Создаем axios instance с credentials для отправки cookies
export const apiClient = axios.create({
    baseURL: BACKEND_URL,
    withCredentials: true, // ВАЖНО: отправка cookies
    headers: {
        'Content-Type': 'application/json',
    },
});

export interface PKCEChallenge {
    code_verifier: string;
    code_challenge: string;
}

export class AuthService {
    /**
     * Генерация PKCE challenge
     */
    static generatePKCE(): PKCEChallenge {
        const challenge = pkceChallenge();
        return {
            code_verifier: challenge.code_verifier,
            code_challenge: challenge.code_challenge,
        };
    }

    /**
     * Получить URL для авторизации в Keycloak с PKCE
     */
    static async getAuthorizationUrl(idpHint?: string): Promise<string> {
        const pkce = this.generatePKCE();
        const state = this.generateState();

        // Сохраняем в sessionStorage для использования после редиректа
        sessionStorage.setItem('pkce_code_verifier', pkce.code_verifier);
        sessionStorage.setItem('auth_state', state);

        // ✅ ЖДЕМ завершения отправки PKCE параметров на backend
        await this.initAuthFlow(pkce, state);

        const params = new URLSearchParams({
            client_id: CLIENT_ID,
            redirect_uri: `${BACKEND_URL}/auth/callback`,
            response_type: 'code',
            scope: 'openid profile email',
            code_challenge: pkce.code_challenge,
            code_challenge_method: 'S256',
            state: state,
        });

        // Добавляем kc_idp_hint для прямого редиректа на внешний IdP
        if (idpHint) {
            params.append('kc_idp_hint', idpHint);
        }

        return `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/auth?${params.toString()}`;
    }

    /**
     * Инициализация auth flow на backend (отправка PKCE параметров)
     */
    static async initAuthFlow(pkce: PKCEChallenge, state: string): Promise<void> {
        try {
            await apiClient.post('/auth/init', {
                code_challenge: pkce.code_challenge,
                code_verifier: pkce.code_verifier,
                state: state,
            });
        } catch (error) {
            console.error('Failed to init auth flow:', error);
        }
    }

    /**
     * Генерация случайного state для защиты от CSRF
     */
    static generateState(): string {
        const array = new Uint8Array(16);
        crypto.getRandomValues(array);
        return Array.from(array, (byte) => byte.toString(16).padStart(2, '0')).join('');
    }

    /**
     * Начать процесс аутентификации (стандартный Keycloak)
     */
    static async login(): Promise<void> {
        const authUrl = await this.getAuthorizationUrl();
        window.location.href = authUrl;
    }

    /**
     * Начать процесс аутентификации через Яндекс ID
     */
    static async loginWithYandex(): Promise<void> {
        const authUrl = await this.getAuthorizationUrl('yandex');
        window.location.href = authUrl;
    }

    /**
     * Выход из системы
     */
    static async logout(): Promise<void> {
        try {
            await apiClient.post('/auth/logout');

            // Очистка sessionStorage
            sessionStorage.removeItem('pkce_code_verifier');
            sessionStorage.removeItem('auth_state');

            // Опционально: редирект на Keycloak logout
            const logoutUrl = `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/logout?redirect_uri=${encodeURIComponent(window.location.origin)}`;
            window.location.href = logoutUrl;
        } catch (error) {
            console.error('Logout failed:', error);
        }
    }

    /**
     * Проверка аутентификации (проверка наличия сессии)
     */
    static async checkAuth(): Promise<boolean> {
        try {
            const response = await apiClient.get('/api/user');
            return response.status === 200;
        } catch (error) {
            return false;
        }
    }

    /**
     * Получить информацию о текущем пользователе
     */
    static async getCurrentUser(): Promise<any> {
        try {
            const response = await apiClient.get('/api/user');
            return response.data;
        } catch (error) {
            console.error('Failed to get current user:', error);
            return null;
        }
    }
}
