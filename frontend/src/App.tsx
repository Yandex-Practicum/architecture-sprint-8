import React, { useEffect } from 'react';
import { AuthProvider } from './contexts/AuthContext';
import ReportPage from './components/ReportPage';

const App: React.FC = () => {
  // Handle OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const authenticated = params.get('authenticated');
    const error = params.get('error');

    if (authenticated === 'true') {
      // Clear URL parameters and reload
      window.history.replaceState({}, document.title, '/');
      window.location.reload();
    } else if (error) {
      console.error('Authentication error:', error);
      alert(`Authentication failed: ${error}`);
      window.history.replaceState({}, document.title, '/');
    }
  }, []);

  return (
    <AuthProvider>
      <div className="App">
        <ReportPage />
      </div>
    </AuthProvider>
  );
};

export default App;