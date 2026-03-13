import React, { createContext, useState, useEffect, useCallback } from 'react';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8000';

interface User {
  sub: string;
  username: string;
  email: string;
  name: string;
  roles: string[];
}

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: () => void;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  login: () => {},
  logout: async () => {},
});

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    try {
      const response = await fetch(`${AUTH_URL}/auth/me`, {
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        setUser(data);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = () => {
    window.location.href = `${AUTH_URL}/auth/login`;
  };

  const logout = async () => {
    try {
      await fetch(`${AUTH_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // best effort
    }
    setUser(null);
    window.location.href = '/';
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
