import React, { useEffect, useState } from 'react';
import ReportPage from './components/ReportPage';
import LoginPage from './components/LoginPage';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8081';

const App: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const checkSession = async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/session`, {
          credentials: 'include',
        });
        setIsAuthenticated(res.ok);
      } catch {
        setIsAuthenticated(false);
      }
    };

    checkSession();
  }, []);

  if (isAuthenticated === null) {
    return <div>Loading...</div>;
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return <ReportPage />;
};

export default App;