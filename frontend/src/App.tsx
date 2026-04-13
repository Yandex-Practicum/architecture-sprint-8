import React, { useEffect, useState } from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig } from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL || 'http://localhost:8080',
  realm: process.env.REACT_APP_KEYCLOAK_REALM || 'reports-realm',
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'reports-frontend'
};

const keycloak = new Keycloak(keycloakConfig);

const App: React.FC = () => {
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    keycloak.init({
      onLoad: 'login-required',
      pkceMethod: 'S256',
      checkLoginIframe: false,
      silentCheckSsoRedirectUri: window.location.origin + '/silent-check-sso.html'
    })
    .then(() => setInitialized(true))
    .catch((err: Error) => {
      console.error(err);
      setInitialized(true);
    });
  }, []);

  if (!initialized) return <div>Загрузка...</div>;

  return (
    <ReactKeycloakProvider authClient={keycloak}>
      <ReportPage />
    </ReactKeycloakProvider>
  );
};

export default App;