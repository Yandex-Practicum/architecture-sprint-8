/**
 * BFF Authentication Service
 * Works with session-based authentication via bionicpro-auth BFF service
 */

// BFF handles all PKCE operations server-side

interface UserInfo {
  sub: string;
  crm_user_id: number | null;
  username: string;
  email: string;
  given_name?: string;
  family_name?: string;
  roles: string[];
  crm_info?: {
    id: number;
    name: string;
    email: string;
    age: number;
    gender: string;
    country: string;
  } | null;
}

// AuthRequest not needed - BFF handles PKCE server-side

interface AuthResponse {
  success: boolean;
  user?: UserInfo;
  session_id: string;
  message: string;
}

interface AuthConfig {
  bffUrl: string;
  redirectUri: string;
}

export class BFFAuthService {
  private config: AuthConfig;

  constructor(config: AuthConfig) {
    this.config = config;
  }

  /**
   * Initiates login by redirecting to the BFF's login endpoint.
   * The BFF will handle PKCE and Keycloak redirection.
   */
  async initiateLogin(): Promise<void> {
    try {
      window.location.href = `${this.config.bffUrl}/auth`;
    } catch (error) {
      console.error('Failed to initiate login via BFF:', error);
      throw new Error('Authentication initialization failed');
    }
  }

  /**
   * Handles the authorization callback from Keycloak, forwarding the code and state to the BFF.
   */
  async handleCallback(code: string, state: string): Promise<AuthResponse> {
    try {
      const response = await fetch(`${this.config.bffUrl}/auth/callback?code=${code}&state=${state}`, {
        method: 'GET',
        credentials: 'include', // Important: include cookies for session management
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Authentication failed: ${response.status} ${errorText}`);
      }

      const authResponse: AuthResponse = await response.json();
      return authResponse;

    } catch (error) {
      console.error('Callback handling failed:', error);
      throw error;
    }
  }

  /**
   * Get current user information from BFF
   */
  async getCurrentUser(): Promise<UserInfo | null> {
    try {
      const response = await fetch(`${this.config.bffUrl}/auth/user`, {
        method: 'GET',
        credentials: 'include', // Important: include session cookie
      });

      if (response.status === 401) {
        return null; // Not authenticated
      }

      if (!response.ok) {
        throw new Error(`Failed to get user info: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      console.error('Failed to get current user:', error);
      return null;
    }
  }

  /**
   * Check if user is authenticated
   */
  async isAuthenticated(): Promise<boolean> {
    const user = await this.getCurrentUser();
    return user !== null;
  }

  /**
   * Logout user via BFF
   */
  async logout(): Promise<void> {
    try {
      await fetch(`${this.config.bffUrl}/auth/logout`, {
        method: 'POST',
        credentials: 'include', // Important: include session cookie
      });
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      // Always redirect to home page
      window.location.href = '/';
    }
  }

  /**
   * Make authenticated request to protected API
   */
  async fetchProtected(url: string, options: RequestInit = {}): Promise<Response> {
    return fetch(url, {
      ...options,
      credentials: 'include', // Important: include session cookie
    });
  }

  // buildAuthorizationUrl removed - BFF handles Keycloak interaction
}

export const createBFFAuthService = () => {
  const config: AuthConfig = {
    bffUrl: process.env.REACT_APP_BFF_URL || 'http://localhost:5001',
    redirectUri: process.env.REACT_APP_REDIRECT_URI || `${window.location.origin}/auth/callback`,
  };
  return new BFFAuthService(config);
};
