export interface User {
  userId: string;
  username: string;
  createdAt: string;
  lastActivityAt?: string;
}

export interface LoginResponse {
  user: User;
  message: string;
}

export interface ValidationResponse {
  valid: boolean;
}

class AuthService {

  private readonly API_URL = process.env.REACT_APP_VITE_API_URL;


  async login(username: string, password: string): Promise<{ success: boolean; user?: User; error?: string }> {

    try {
      const response = await fetch(`${this.API_URL}/api/auth/login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Origin': window.location.origin,
        },
        credentials: 'include', // Важно для отправки и получения cookies
        body: JSON.stringify({ username, pass:password }),
      });

      if (response.ok) {
        const data: LoginResponse = await response.json();
        return { success: true, user: data.user };
      }

      const errorData = await response.json().catch(() => ({ error: 'Login failed' }));
      return { success: false, error: errorData.error || 'Invalid credentials' };
    } catch (error) {
      console.error('Login error:', error);
      return { success: false, error: 'Network error. Please try again.' };
    }
  }

  async logout(): Promise<{ success: boolean; error?: string }> {
    try {
      const response = await fetch(`${this.API_URL}/api/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });

      if (response.ok) {
        return { success: true };
      }

      return { success: false, error: 'Logout failed' };
    } catch (error) {
      console.error('Logout error:', error);
      return { success: false, error: 'Network error' };
    }
  }

  async getCurrentUser(): Promise<User | null> {
    try {
      const response = await fetch(`${this.API_URL}/api/auth/me`, {
        credentials: 'include',
      });

      if (response.ok) {
        const user: User = await response.json();
        return user;
      }
      return null;
    } catch (error) {
      console.error('Get user error:', error);
      return null;
    }
  }

  async validateSession(): Promise<boolean> {
    try {
      const response = await fetch(`${this.API_URL}/api/auth/validate`, {
        credentials: 'include',
      });
      return response.ok;
    } catch (error) {
      console.error('Validate session error:', error);
      return false;
    }
  }
}

export const authService = new AuthService();