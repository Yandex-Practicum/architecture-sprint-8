import React, { useState } from 'react';
import { createBFFAuthService } from '../auth/BFFAuthService';

interface LoginButtonProps {
  className?: string;
  children?: React.ReactNode;
  onLoginStart?: () => void;
  onLoginError?: (error: Error) => void;
}

export const LoginButton: React.FC<LoginButtonProps> = ({ 
  className = '',
  children,
  onLoginStart,
  onLoginError
}) => {
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async () => {
    setIsLoading(true);
    onLoginStart?.();

    try {
      const authService = createBFFAuthService();
      await authService.initiateLogin();
    } catch (error) {
      const authError = error instanceof Error ? error : new Error('Login failed');
      console.error('Login initiation failed:', authError);
      onLoginError?.(authError);
      setIsLoading(false);
    }
  };

  return (
    <button
      onClick={handleLogin}
      disabled={isLoading}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        padding: '12px 24px',
        border: 'none',
        fontSize: '16px',
        fontWeight: '500',
        borderRadius: '6px',
        color: 'white',
        backgroundColor: '#2563eb',
        cursor: isLoading ? 'not-allowed' : 'pointer',
        opacity: isLoading ? 0.5 : 1,
        transition: 'background-color 0.2s'
      }}
      onMouseOver={(e) => !isLoading && ((e.target as HTMLElement).style.backgroundColor = '#1d4ed8')}
      onMouseOut={(e) => !isLoading && ((e.target as HTMLElement).style.backgroundColor = '#2563eb')}
    >
      {isLoading ? (
        <>
          <svg 
            style={{ 
              animation: 'spin 1s linear infinite', 
              marginRight: '12px', 
              height: '20px', 
              width: '20px', 
              color: 'white' 
            }}
            xmlns="http://www.w3.org/2000/svg" 
            fill="none" 
            viewBox="0 0 24 24"
          >
            <circle 
              style={{ opacity: 0.25 }}
              cx="12" 
              cy="12" 
              r="10" 
              stroke="currentColor" 
              strokeWidth="4"
            />
            <path 
              style={{ opacity: 0.75 }}
              fill="currentColor" 
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
          Logging in...
        </>
      ) : (
        children || 'Login to BionicPRO'
      )}
    </button>
  );
};

export const PilotLoginButton: React.FC<Omit<LoginButtonProps, 'children'>> = (props) => (
  <LoginButton {...props}>
    Login as Prosthesis Pilot
  </LoginButton>
);

export const BuyerLoginButton: React.FC<Omit<LoginButtonProps, 'children'>> = (props) => (
  <LoginButton {...props}>
    Login as Buyer
  </LoginButton>
);

export const OperatorLoginButton: React.FC<Omit<LoginButtonProps, 'children'>> = (props) => (
  <LoginButton {...props}>
    Login as Operator
  </LoginButton>
);

export const MLEngineerLoginButton: React.FC<Omit<LoginButtonProps, 'children'>> = (props) => (
  <LoginButton {...props}>
    Login as ML Engineer
  </LoginButton>
);
