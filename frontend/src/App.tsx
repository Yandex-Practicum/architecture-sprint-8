import React from 'react';
import { OidcProvider } from '@axa-fr/react-oidc';
import ReportPage from './components/ReportPage';

const oidcConfig = {
  client_id: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'reports-frontend',
  redirect_uri: window.location.origin + '/authentication/callback',
  scope: 'openid profile email',
  authority: `${process.env.REACT_APP_KEYCLOAK_URL}/realms/${process.env.REACT_APP_KEYCLOAK_REALM}`,
  authority_configuration: {
    authorization_endpoint: `${process.env.REACT_APP_KEYCLOAK_URL}/realms/${process.env.REACT_APP_KEYCLOAK_REALM}/protocol/openid-connect/auth`,
    token_endpoint: 'http://localhost:8081/auth/callback',
    userinfo_endpoint: 'http://localhost:8081/auth/me',
    end_session_endpoint: 'http://localhost:8081/auth/session',
  },
  service_worker_only: false,
};

const App: React.FC = () => {
  return (
    <OidcProvider configuration={oidcConfig}>
      <div className="App">
        <ReportPage />
      </div>
    </OidcProvider>
  );
};

export default App;