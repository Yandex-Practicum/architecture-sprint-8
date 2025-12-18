import React, { useState, useEffect } from 'react';
import { createBFFAuthService } from '../auth/BFFAuthService';

interface BFFAuthGuardProps {
  children: React.ReactNode;
  fallback?: React.ReactNode;
}

export const BFFAuthGuard: React.FC<BFFAuthGuardProps> = ({ children, fallback }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const authService = createBFFAuthService();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const authenticated = await authService.isAuthenticated();
        setIsAuthenticated(authenticated);
      } catch (error) {
        console.error('Auth check failed:', error);
        setIsAuthenticated(false);
      }
    };

    checkAuth();
  }, []);

  if (isAuthenticated === null) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ 
            animation: 'spin 1s linear infinite', 
            borderRadius: '50%', 
            height: '48px', 
            width: '48px', 
            borderBottom: '2px solid #2563eb', 
            margin: '0 auto' 
          }}></div>
          <p style={{ marginTop: '16px', color: '#6b7280' }}>Checking authentication...</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated) {
    return <>{children}</>;
  }

  return <>{fallback}</>;
};

export default BFFAuthGuard;
