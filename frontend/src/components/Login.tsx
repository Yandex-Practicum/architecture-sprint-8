// src/components/Login.tsx
import React, { useState, useEffect } from 'react';
import { useAuth } from '../contexts/AuthContext';

const Login: React.FC = () => {
  const { login, loading } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [isLoggingIn, setIsLoggingIn] = useState<boolean>(false);

  useEffect(() => {
    // Проверяем ошибку в URL
    const urlParams = new URLSearchParams(window.location.search);
    const errorParam = urlParams.get('error');
    if (errorParam) {
      setError(errorParam);
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const handleKeycloakLogin = async (): Promise<void> => {
    setIsLoggingIn(true);
    setError(null);
    try {
      await login();
    } catch (err) {
      setError('Failed to initiate login. Please try again.');
      setIsLoggingIn(false);
    }
  };

  const handleYandexLogin = async (): Promise<void> => {
    setIsLoggingIn(true);
    setError(null);
    try {
      await login('yandex-oauth2');
    } catch (err) {
      setError('Failed to initiate Yandex login. Please try again.');
      setIsLoggingIn(false);
    }
  };

  const isLoading = loading || isLoggingIn;

  return (
    <div className="login-container">
      <div className="login-card">
        <h1>🔐 BionicPRO</h1>
        <p>Secure Authentication System</p>
        
        {error && (
          <div className="error-message">
            ⚠️ {error}
          </div>
        )}
        
        <button 
          onClick={handleKeycloakLogin} 
          disabled={isLoading}
        >
          <span>🔑</span>
          {isLoggingIn ? 'Redirecting...' : 'Sign in with Keycloak'}
        </button>
        
        <button 
          onClick={handleYandexLogin} 
          disabled={isLoading}
        >
          <span>Y</span>
          {isLoggingIn ? 'Redirecting...' : 'Sign in with Yandex ID'}
        </button>
        
        <p className="note">
          🔒 Two-Factor Authentication with FreeOTP<br />
          🔐 OTP codes are validated by Keycloak
        </p>
      </div>
    </div>
  );
};

export default Login;