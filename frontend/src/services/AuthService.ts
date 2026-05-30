class AuthService {
    private readonly AUTH_PORT = '8081';
    private readonly REPORTS_PORT = '8082';
    private readonly AUTH_URL = process.env.REACT_APP_AUTH_URL || `http://localhost:${this.AUTH_PORT}`;
    private readonly REPORTS_URL = process.env.REACT_APP_REPORTS_URL || `http://localhost:${this.REPORTS_PORT}`;

    private accessToken: string | null = null;

    async checkAuth(): Promise<boolean> {
        try {
            const response = await fetch(`${this.AUTH_URL}/auth/check`, {
                method: 'GET',
                credentials: 'include',
            });
            if (response.ok) {
                // После успешной проверки получаем токен
                await this.refreshToken();
            }
            return response.ok;
        } catch (error) {
            console.error('Check auth error:', error);
            return false;
        }
    }

    async refreshToken(): Promise<string | null> {
        try {
            console.log('Refreshing token...');
            const response = await fetch(`${this.AUTH_URL}/auth/token`, {
                method: 'GET',
                credentials: 'include',
            });

            if (response.ok) {
                const data = await response.json();
                this.accessToken = data.accessToken;
                console.log('Token refreshed successfully');
                return this.accessToken;
            } else {
                console.error('Failed to refresh token, status:', response.status);
                this.accessToken = null;
                return null;
            }
        } catch (error) {
            console.error('Refresh token error:', error);
            this.accessToken = null;
            return null;
        }
    }

    async getCurrentUser(): Promise<UserInfo | null> {
        try {
            const response = await fetch(`${this.AUTH_URL}/auth/me`, {
                method: 'GET',
                credentials: 'include',
            });
            if (response.ok) {
                return await response.json();
            }
            return null;
        } catch (error) {
            console.error('Get user error:', error);
            return null;
        }
    }

    async getUserId(): Promise<string> {
        const user = await this.getCurrentUser();
        return user?.userId || 'current';
    }

    async getReport(format: string = 'xml'): Promise<Response> {
        const userId = await this.getUserId();

        // Ждём токен, если его нет
        if (!this.accessToken) {
            console.log('No access token, refreshing...');
            await this.refreshToken();
        }

        // Если после обновления токена всё равно нет - перенаправляем на логин
        if (!this.accessToken) {
            console.error('No access token available, redirecting to login');
            this.login();
            throw new Error('No access token');
        }

        const url = `${this.REPORTS_URL}/api/reports/${userId}?format=${format}`;

        console.log('Request URL:', url);
        console.log('Using token:', this.accessToken ? 'Yes' : 'No');

        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${this.accessToken}`,
                'Content-Type': 'application/xml',
            }
        });

        // Если 401 Unauthorized - пробуем обновить токен и повторить запрос
        if (response.status === 401) {
            console.log('Token expired, refreshing and retrying...');
            await this.refreshToken();

            if (this.accessToken) {
                // Повторяем запрос с новым токеном
                return fetch(url, {
                    method: 'GET',
                    headers: {
                        'Authorization': `Bearer ${this.accessToken}`,
                        'Content-Type': 'application/xml',
                    }
                });
            } else {
                this.login();
                throw new Error('Session expired');
            }
        }

        return response;
    }

    login(): void {
        this.accessToken = null;
        window.location.href = `${this.AUTH_URL}/auth/login`;
    }

    async logout(): Promise<void> {
        this.accessToken = null;
        try {
            await fetch(`${this.AUTH_URL}/auth/logout`, {
                method: 'POST',
                credentials: 'include',
            });
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            window.location.href = '/';
        }
    }
}

export interface UserInfo {
    username: string;
    userId: string;
    email: string;
    roles: string[];
    authenticated: boolean;
}

export default new AuthService();