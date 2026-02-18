import React, { useEffect, useState } from 'react';
import { AuthService } from './services/auth.service';
import ReportPage from './components/ReportPage';
import LoginPage from './components/LoginPage';
import LoadingPage from './components/LoadingPage';

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [user, setUser] = useState<any>(null);

  useEffect(() => {
    checkAuthentication();
  }, []);

  const checkAuthentication = async () => {
    try {
      const isAuth = await AuthService.checkAuth();
      setIsAuthenticated(isAuth);

      if (isAuth) {
        const userData = await AuthService.getCurrentUser();
        setUser(userData);
      }
    } catch (error) {
      console.error('Auth check failed:', error);
      setIsAuthenticated(false);
    }
  };

  const handleLogin = () => {
    AuthService.login();
  };

  const handleLogout = async () => {
    await AuthService.logout();
    setIsAuthenticated(false);
    setUser(null);
  };

  // Loading state
  if (isAuthenticated === null) {
    return <LoadingPage />;
  }

  // Not authenticated
  if (!isAuthenticated) {
    return <LoginPage onLogin={handleLogin} />;
  }

  // Authenticated
  return (
    <div className="App">
      <ReportPage user={user} onLogout={handleLogout} />
    </div>
  );
};

export default App;
