import React, { useState, useEffect } from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig } from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL || 'http://localhost:8080',
  realm: process.env.REACT_APP_KEYCLOAK_REALM || 'reports-realm',
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'reports-frontend',
};

const keycloak = new Keycloak(keycloakConfig);

const initOptions = {
  pkceMethod: 'S256' as const,
  checkLoginIframe: false,
};

/** Показываем загрузку, через 5 сек — подсказку, если Keycloak не ответил */
const KEYCLOAK_LOADING_TIMEOUT_MS = 5000;

const KeycloakLoading: React.FC = () => {
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setTimedOut(true), KEYCLOAK_LOADING_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, []);

  if (timedOut) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-6 text-center">
        <p className="text-lg text-gray-700 mb-2">Сервер авторизации не отвечает</p>
        <p className="text-sm text-gray-500 mb-4">
          Запустите Keycloak: <code className="bg-gray-200 px-1 rounded">docker-compose up -d keycloak</code>
        </p>
        <p className="text-sm text-gray-500 mb-4">
          URL: {keycloakConfig.url} (realm: {keycloakConfig.realm})
        </p>
        <button
          type="button"
          onClick={() => window.location.reload()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Повторить
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <p className="text-gray-600">Загрузка…</p>
    </div>
  );
};

const App: React.FC = () => {
  return (
    <ReactKeycloakProvider
      authClient={keycloak}
      initOptions={initOptions}
      LoadingComponent={<KeycloakLoading />}
    >
      <div className="App">
        <ReportPage />
      </div>
    </ReactKeycloakProvider>
  );
};

export default App;