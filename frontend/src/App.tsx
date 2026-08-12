import React from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig, KeycloakInitOptions } from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL,
  realm: process.env.REACT_APP_KEYCLOAK_REALM || "",
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || ""
};

const keycloak = new Keycloak(keycloakConfig);

// ВАЖНО: этот блок должен быть
const initOptions: KeycloakInitOptions = {
  onLoad: 'login-required',
  pkceMethod: 'S256',
  checkLoginIframe: false,
};

const App: React.FC = () => {
  return (
    <ReactKeycloakProvider 
      authClient={keycloak}
      initOptions={initOptions}  // ВАЖНО: передать сюда
    >
      <div className="App">
        <ReportPage />
      </div>
    </ReactKeycloakProvider>
  );
};

export default App;