import React from 'react';
import ReportPage from './components/ReportPage';

// The SPA no longer talks to Keycloak directly and holds no tokens.
// Authentication is delegated to the bionicpro-auth BFF, which keeps the
// access/refresh tokens server-side and exposes only an HttpOnly session cookie.
const App: React.FC = () => {
  return (
    <div className="App">
      <ReportPage />
    </div>
  );
};

export default App;
