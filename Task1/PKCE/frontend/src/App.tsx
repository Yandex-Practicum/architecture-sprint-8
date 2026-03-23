import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig } from 'keycloak-js';
import React from 'react';
import ReportPage from './components/ReportPage';

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL,
  realm: process.env.REACT_APP_KEYCLOAK_REALM || '',
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || '',
};

export const initOptions = {
  onLoad: 'check-sso', // perform a silent session
  flow: 'standard', // use the OIDC Authorization Code Flow
  pkceMethod: 'S256', // enforce PKCE for extra SPA security
  silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
  checkLoginIframe: true, // enable the hidden iframe for silent token refresh
  checkLoginIframeInterval: 30, // polling interval in seconds
  enableLogging: true, // turn on adapter debug logging
};

const keycloak = new Keycloak(keycloakConfig);

const App: React.FC = () => {
  return (
    <ReactKeycloakProvider authClient={keycloak} initOptions={initOptions}>
      <div className='App'>
        <ReportPage />
      </div>
    </ReactKeycloakProvider>
  );
};

export default App;
