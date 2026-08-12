import React, { createContext, useContext, useEffect, useState } from 'react';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:4000';

interface AuthState {
  loading: boolean;
  authenticated: boolean;
  username: string | null;
  login: () => void;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [loading, setLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${AUTH_URL}/me`, { credentials: 'include' })
      .then((res) => {
        if (!res.ok) {
          throw new Error('not authenticated');
        }
        return res.json();
      })
      .then((data) => {
        setAuthenticated(true);
        setUsername(data.username);
      })
      .catch(() => {
        setAuthenticated(false);
        setUsername(null);
      })
      .finally(() => setLoading(false));
  }, []);

  // Аутентификация - это полная навигация страницы: bionicpro-auth
  // перенаправляет браузер через Keycloak и обратно. Фронтенд никогда
  // не обращается к Keycloak напрямую и не работает с токенами.
  const login = () => {
    window.location.href = `${AUTH_URL}/login`;
  };

  const logout = async () => {
    await fetch(`${AUTH_URL}/logout`, { method: 'POST', credentials: 'include' });
    setAuthenticated(false);
    setUsername(null);
  };

  return (
    <AuthContext.Provider value={{ loading, authenticated, username, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}

export { AUTH_URL };
