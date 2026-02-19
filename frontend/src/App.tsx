import React, { useEffect, useState } from 'react';
// import { ReactKeycloakProvider } from '@react-keycloak/web';
// import Keycloak, { KeycloakConfig } from 'keycloak-js';
// import ReportPage from './components/ReportPage';
import { UserCard } from './components/UserCard';

// const keycloakConfig: KeycloakConfig = {
//   url: process.env.REACT_APP_KEYCLOAK_URL,
//   realm: process.env.REACT_APP_KEYCLOAK_REALM || "",
//   clientId: process.env.REACT_APP_KEYCLOAK_CLIENT_ID || "",
// };

// const keycloak = new Keycloak(keycloakConfig);

// const initOptions = {
//   pkceMethod: "S256",
// };


const App: React.FC = () => {

  const login = () => {
    window.location.replace(`${process.env.REACT_APP_API_URL}/auth/login`);
  };

  const [userinfo, setUserinfo] = useState(null);


  const fetchMe = async () => {
    // const response = await fetch(`${process.env.REACT_APP_API_URL}/auth/me`, {
    //   credentials: "include"
    // });
    const response = await fetch(`${process.env.REACT_APP_API_URL}/auth/userinfo`, {
      credentials: "include"
    });
    if (response.status === 401) {
      login();
      return;
    }
    response.json().then(data => setUserinfo(data))
  }

  useEffect(() => {
    fetchMe()
  }, [])

  return (
    // <ReactKeycloakProvider authClient={keycloak} initOptions={initOptions}>
    <div className="App">
      {userinfo && <UserCard userinfo={userinfo} />}
      {/* <ReportPage /> */}
    </div>
    // </ReactKeycloakProvider>
  );
};

export default App;