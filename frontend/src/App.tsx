import React from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig, KeycloakInitOptions } from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL,
  realm: process.env.REACT_APP_KEYCLOAK_REALM || "",
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || ""
};

const keycloakInitOpt: KeycloakInitOptions = {
  pkceMethod: 'S256'
};

const keycloak = new Keycloak(keycloakConfig);

// Логирование для проверки PKCE (можно удалить после проверки)
if (process.env.NODE_ENV === 'development') {
  // Перехватываем создание URL для авторизации
  const originalLogin = keycloak.login;
  keycloak.login = function(options?: any) {
    console.log('PKCE Verification:');
    console.log(' - Init Options:', keycloakInitOpt);
    console.log(' - PKCE Method:', keycloakInitOpt.pkceMethod);
    return originalLogin.call(this, options);
  };
}

const App: React.FC = () => {
  return (
    <ReactKeycloakProvider 
      authClient={keycloak}
      initOptions={keycloakInitOpt}
      onEvent={(eventType, error) => {
        if (eventType === 'onReady') {
          console.log('Keycloak PKCE Configuration:', {
            pkceMethod: keycloakInitOpt.pkceMethod,
            flow: 'standard (authorization code with PKCE)',
            clientId: keycloakConfig.clientId
          });
          console.log('PKCE is enabled!');
        }
      }}
    >
      <div className="App">
        <ReportPage />
      </div>
    </ReactKeycloakProvider>
  );
};

export default App;