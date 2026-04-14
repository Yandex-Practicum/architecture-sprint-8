import React, { useEffect, useState } from 'react';
import Keycloak from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloak = new Keycloak({
  url: process.env.REACT_APP_KEYCLOAK_URL || 'http://localhost:8080',
  realm: process.env.REACT_APP_KEYCLOAK_REALM || 'reports-realm',
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'reports-frontend'
});

const App: React.FC = () => {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    keycloak.init({
      onLoad: 'login-required',
      pkceMethod: 'S256',
      checkLoginIframe: false
    })
    .then((auth) => {
      console.log('Authenticated:', auth);
      setAuthenticated(auth);
      setLoading(false);
    })
    .catch((err) => {
      console.error('Init error:', err);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-xl">Загрузка...</div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">Отчёты о работе протеза</h1>
          <p className="mb-4 text-gray-600">Для просмотра отчётов необходимо авторизоваться</p>
          <button
            onClick={() => keycloak.login()}
            className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            Войти
          </button>
        </div>
      </div>
    );
  }

  return <ReportPage keycloak={keycloak} />;
};

export default App;