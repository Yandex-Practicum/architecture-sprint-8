import React from 'react';
import { AuthProvider } from "react-oidc-context";
import ReportPage from './components/ReportPage';


export const AUTH_AUTHORITY = `${process.env.REACT_APP_KEYCLOAK_URL}/realms/${process.env.REACT_APP_KEYCLOAK_REALM}`
export const AUTH_CLIENT_ID = process.env.REACT_APP_KEYCLOAK_CLIENT_ID

//По умолчанию oidc-client-ts автоматически использует PKCE если сервер его поддерживает — ничего дополнительно настраивать не нужно.
export const oidcConfig = {
  authority: AUTH_AUTHORITY,
  client_id: AUTH_CLIENT_ID,
  redirect_uri: window.location.origin + "/callback",
  post_logout_redirect_uri: window.location.origin,
  response_type: "code",
  scope: "openid profile email",
  // Автоматическое обновление токена
  automaticSilentRenew: true,
  silent_redirect_uri: window.location.origin + "/silent-renew.html",
};

const App: React.FC = () => {
  return (
    <AuthProvider {...oidcConfig}>
      <div className="App">
        <ReportPage />
      </div>
    </AuthProvider>
  );
};

export default App;
