import React from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak, { KeycloakConfig } from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloakConfig: KeycloakConfig = {
  url: process.env.REACT_APP_KEYCLOAK_URL,
  realm: process.env.REACT_APP_KEYCLOAK_REALM||"",
  clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID||""
};

const keycloak = new Keycloak(keycloakConfig);

const eventLogger = (event: unknown, error: unknown) => {
  console.log('onKeycloakEvent', event, error)
}

const tokenLogger = (tokens: unknown) => {
  console.log('onKeycloakTokens', tokens)
}

// Define init options, including PKCE settings
const initOptions = {
  onLoad: 'check-sso', // or 'login-required'
  pkceMethod: 'S256',  // Explicitly enables PKCE (this is the default in modern versions)
};

const App: React.FC = () => {
  return (
    <ReactKeycloakProvider
        authClient={keycloak}
        initOptions={initOptions}
        onEvent={eventLogger}
        onTokens={tokenLogger}
    >
      <div className="App">
        <ReportPage />
      </div>
    </ReactKeycloakProvider>
  );
};

export default App;