import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';

interface User {
  sub?: string;
  email?: string;
  name?: string;
  preferred_username?: string;
  given_name?: string;
  family_name?: string;
}

interface AuthContextType {
  authenticated: boolean;
  initialized: boolean;
  isNewSession: boolean;
  sessionCreatedAt: number | null;
  user: User | null;
  login: () => void;
  logout: () => Promise<void>;
  fetchWithAuth: (url: string, options?: RequestInit) => Promise<Response>;
  clearNewSessionFlag: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8000';

// Time window (ms) during which we consider the session "new" and suppress "Session expired" errors
const NEW_SESSION_WINDOW_MS = 30000; // 30 seconds

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authenticated, setAuthenticated] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [isNewSession, setIsNewSession] = useState(false);
  const [sessionCreatedAt, setSessionCreatedAt] = useState<number | null>(null);
  const [user, setUser] = useState<User | null>(null);
  const newSessionTimerRef = useRef<NodeJS.Timeout | null>(null);

  const clearNewSessionFlag = useCallback(() => {
    // Only clear if not within the new session window
    if (sessionCreatedAt && Date.now() - sessionCreatedAt < NEW_SESSION_WINDOW_MS) {
      return; // Don't clear yet - still in new session window
    }
    setIsNewSession(false);
  }, [sessionCreatedAt]);

  const checkSession = useCallback(async () => {
    try {
      const response = await fetch(`${AUTH_URL}/auth/session`, {
        credentials: 'include'
      });

      if (response.ok) {
        const data = await response.json();
        setAuthenticated(data.authenticated);
        setUser(data.user);
      } else {
        setAuthenticated(false);
        setUser(null);
      }
    } catch (error) {
      console.error('Session check error:', error);
      setAuthenticated(false);
      setUser(null);
    } finally {
      setInitialized(true);
    }
  }, []);

  useEffect(() => {
    // Check if we just returned from OAuth callback
    const urlParams = new URLSearchParams(window.location.search);
    const authParam = urlParams.get('auth');
    const errorParam = urlParams.get('error');

    // Clean up URL parameters
    if (authParam || errorParam) {
      const newUrl = window.location.pathname;
      window.history.replaceState({}, document.title, newUrl);
    }

    if (errorParam) {
      // OAuth error occurred
      console.error('OAuth error:', errorParam);
      setAuthenticated(false);
      setUser(null);
      setIsNewSession(false);
      setSessionCreatedAt(null);
      setInitialized(true);
    } else if (authParam === 'success') {
      // Mark this as a new session (just logged in)
      const now = Date.now();
      setIsNewSession(true);
      setSessionCreatedAt(now);

      // Auto-clear new session flag after the window expires
      if (newSessionTimerRef.current) {
        clearTimeout(newSessionTimerRef.current);
      }
      newSessionTimerRef.current = setTimeout(() => {
        setIsNewSession(false);
      }, NEW_SESSION_WINDOW_MS);

      // Give the cookie time to be set, then check session
      setTimeout(() => {
        checkSession();
      }, 100);
    } else {
      // Normal session check (not a new login)
      checkSession();
    }

    // Cleanup timer on unmount
    return () => {
      if (newSessionTimerRef.current) {
        clearTimeout(newSessionTimerRef.current);
      }
    };
  }, [checkSession]);

  const login = () => {
    window.location.href = `${AUTH_URL}/auth/login`;
  };

  const logout = async () => {
    try {
      await fetch(`${AUTH_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      setAuthenticated(false);
      setUser(null);
    }
  };

  const fetchWithAuth = async (url: string, options: RequestInit = {}): Promise<Response> => {
    const apiUrl = url.startsWith('http') ? url : `${AUTH_URL}/api/proxy${url}`;

    return fetch(apiUrl, {
      ...options,
      credentials: 'include'
    });
  };

  return (
    <AuthContext.Provider
      value={{
        authenticated,
        initialized,
        isNewSession,
        sessionCreatedAt,
        user,
        login,
        logout,
        fetchWithAuth,
        clearNewSessionFlag
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
