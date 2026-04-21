// src/components/AuthCallback.tsx
import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

type CallbackStatus = 'processing' | 'success' | 'error';

const AuthCallback: React.FC = () => {
  const navigate = useNavigate();
  const { loadSession } = useAuth();
  const [status, setStatus] = useState<CallbackStatus>('processing');
  const [message, setMessage] = useState<string>('Processing authentication...');

  useEffect(() => {
    const processCallback = async (): Promise<void> => {
      const urlParams = new URLSearchParams(window.location.search);
      const success = urlParams.get('success');
      const error = urlParams.get('error');
      const sessionId = urlParams.get('sessionId');

      // Проверка на ошибку
      if (error) {
        setStatus('error');
        setMessage(`Authentication failed: ${error}`);
        setTimeout(() => navigate('/login'), 3000);
        return;
      }

      // Успешная аутентификация
      if (success === 'true' || sessionId) {
        setStatus('success');
        setMessage('Authentication successful! Loading your profile...');
        
        // Загружаем сессию
        await loadSession();
        
        setTimeout(() => navigate('/'), 1000);
        return;
      }

      // Неизвестный статус
      setStatus('error');
      setMessage('Unknown authentication response');
      setTimeout(() => navigate('/login'), 3000);
    };

    processCallback();
  }, [navigate, loadSession]);

  const getStatusIcon = (): string => {
    switch (status) {
      case 'processing': return '🔄';
      case 'success': return '✅';
      case 'error': return '❌';
      default: return '⏳';
    }
  };

  return (
    <div className="callback-container">
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '48px', marginBottom: '20px' }}>{getStatusIcon()}</div>
        <h2>{message}</h2>
        {status === 'processing' && (
          <div style={{ marginTop: '20px' }}>
            <div className="spinner"></div>
          </div>
        )}
      </div>
    </div>
  );
};

export default AuthCallback;