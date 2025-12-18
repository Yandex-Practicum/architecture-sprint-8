import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { createBFFAuthService } from '../auth/BFFAuthService';

interface AuthCallbackProps {
  onSuccess?: (tokens: any) => void;
  onError?: (error: Error) => void;
}

export const AuthCallback: React.FC<AuthCallbackProps> = ({ onSuccess, onError }) => {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [error, setError] = useState<string | null>(null);
  const processedRef = useRef(false);
  const navigate = useNavigate();

  useEffect(() => {
    if (processedRef.current) return;
    
    const handleCallback = async () => {
      processedRef.current = true;
      try {
        const urlParams = new URLSearchParams(window.location.search);
        const code = urlParams.get('code');
        const state = urlParams.get('state');
        const errorParam = urlParams.get('error');
        const errorDescription = urlParams.get('error_description');

        if (errorParam) {
          const errorMsg = errorDescription || errorParam;
          throw new Error(`OAuth error: ${errorMsg}`);
        }

        if (!code) {
          throw new Error('Authorization code not received');
        }

        if (!state) {
          throw new Error('State parameter not received');
        }

        const authService = createBFFAuthService();
        const authResponse = await authService.handleCallback(code, state);

        if (!authResponse.success) {
          throw new Error(authResponse.message || 'Authentication failed');
        }

        setStatus('success');
        onSuccess?.(authResponse);

        window.history.replaceState({}, document.title, window.location.pathname);

        setTimeout(() => {
          navigate('/', { replace: true });
        }, 1500);

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown authentication error';
        setError(errorMessage);
        setStatus('error');
        onError?.(err instanceof Error ? err : new Error(errorMessage));
      }
    };

    handleCallback();
  }, [onSuccess, onError]);

  if (status === 'loading') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ maxWidth: '448px', width: '100%', display: 'flex', flexDirection: 'column', gap: '32px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              animation: 'spin 1s linear infinite', 
              borderRadius: '50%', 
              height: '48px', 
              width: '48px', 
              borderBottom: '2px solid #2563eb', 
              margin: '0 auto' 
            }}></div>
            <h2 style={{ marginTop: '24px', fontSize: '30px', fontWeight: '800', color: '#1f2937' }}>
              Completing login...
            </h2>
            <p style={{ marginTop: '8px', fontSize: '14px', color: '#6b7280' }}>
              Processing authentication data
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ maxWidth: '448px', width: '100%', display: 'flex', flexDirection: 'column', gap: '32px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              margin: '0 auto', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              height: '48px', 
              width: '48px', 
              borderRadius: '50%', 
              backgroundColor: '#dcfce7' 
            }}>
              <svg style={{ height: '24px', width: '24px', color: '#16a34a' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h2 style={{ marginTop: '24px', fontSize: '30px', fontWeight: '800', color: '#1f2937' }}>
              Login successful
            </h2>
            <p style={{ marginTop: '8px', fontSize: '14px', color: '#6b7280' }}>
              Redirecting to application...
            </p>
          </div>
        </div>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ maxWidth: '448px', width: '100%', display: 'flex', flexDirection: 'column', gap: '32px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ 
              margin: '0 auto', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center', 
              height: '48px', 
              width: '48px', 
              borderRadius: '50%', 
              backgroundColor: '#fef2f2' 
            }}>
              <svg style={{ height: '24px', width: '24px', color: '#dc2626' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.732 16c-.77.833.192 2.5 1.732 2.5z" />
              </svg>
            </div>
            <h2 style={{ marginTop: '24px', fontSize: '30px', fontWeight: '800', color: '#1f2937' }}>
              Login error
            </h2>
            <p style={{ marginTop: '8px', fontSize: '14px', color: '#6b7280' }}>
              {error}
            </p>
            <div style={{ marginTop: '24px' }}>
              <button
                onClick={() => navigate('/', { replace: true })}
                style={{
                  width: '100%',
                  display: 'flex',
                  justifyContent: 'center',
                  padding: '8px 16px',
                  border: 'none',
                  borderRadius: '6px',
                  boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                  fontSize: '14px',
                  fontWeight: '500',
                  color: 'white',
                  backgroundColor: '#2563eb',
                  cursor: 'pointer'
                }}
                onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#1d4ed8'}
                onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#2563eb'}
              >
                Back to home
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return null;
};
