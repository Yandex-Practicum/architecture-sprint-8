import React, { useEffect } from 'react';
import { ReactKeycloakProvider, useKeycloak } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig } from 'keycloak-js';
import ReportPage from './components/ReportPage';

// Конфигурация Keycloak
const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL,
  realm: process.env.REACT_APP_KEYCLOAK_REALM || '',
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || '',
};

// Инициализация клиента Keycloak
const keycloak = new Keycloak(keycloakConfig);

const AppContent: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();

  useEffect(() => {
    if (initialized && keycloak.authenticated) {
      console.log('✅ Keycloak initialized and authenticated');
      console.log('Access token:', keycloak.token);
      console.log('Parsed token:', keycloak.tokenParsed);
    }
  }, [initialized, keycloak]);

  return <ReportPage />;
};

// Основной компонент приложения
const App: React.FC = () => {
  return (
    <ReactKeycloakProvider
      authClient={keycloak}
      initOptions={{
        onLoad: 'login-required',  // Авто-редирект на login
        pkceMethod: 'S256',        // Включаем PKCE
        checkLoginIframe: false,   // Опционально: отключает iframe-проверку сессии
      }}
    >
      <AppContent />
    </ReactKeycloakProvider>
  );
};

export default App;
