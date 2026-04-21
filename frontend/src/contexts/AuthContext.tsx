// src/contexts/AuthContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { getLoginUrl, checkSession, logout } from '../services/api';
import { User, SessionResponse } from '../types/';

interface AuthContextType {
  isAuthenticated: boolean;
  user: User | null;
  loading: boolean;
  login: (idpHint?: string | null) => Promise<void>;
  logout: () => Promise<void>;
  loadSession: () => Promise<SessionResponse | null>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const loadSession = useCallback(async (): Promise<SessionResponse | null> => {
    try {
      const session = await checkSession();
      setIsAuthenticated(session.authenticated);
      setUser({
        authenticated: session.authenticated,
        username: session.username,
        email: session.email,
        otpEnabled: session.otpEnabled,
      });
      return session;
    } catch (error) {
      console.error('Failed to load session:', error);
      setIsAuthenticated(false);
      setUser(null);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const login = useCallback(async (idpHint: string | null = null): Promise<void> => {
    try {
      const url = await getLoginUrl(idpHint);
      window.location.href = url;
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    }
  }, []);

  const handleLogout = useCallback(async (): Promise<void> => {
      window.location.href = await logout();
  }, []);

  useEffect(() => {
    loadSession();
  }, [loadSession]);

  const value: AuthContextType = {
    isAuthenticated,
    user,
    loading,
    login,
    logout: handleLogout,
    loadSession,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};