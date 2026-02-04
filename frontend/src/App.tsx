import React from 'react';
import { ReactKeycloakProvider } from '@react-keycloak/web';
import Keycloak from 'keycloak-js';
import ReportPage from './components/ReportPage';

const keycloak = new Keycloak({
    url: 'http://localhost:8080',
    realm: 'reports-realm',
    clientId: 'reports-frontend',
});

const App: React.FC = () => {
    return (
        <ReactKeycloakProvider
            authClient={keycloak}
            initOptions={{
                flow: 'standard',
                pkceMethod: 'S256',
                checkLoginIframe: false,
            }}
        >
            <ReportPage />
        </ReactKeycloakProvider>
    );
};

export default App;
