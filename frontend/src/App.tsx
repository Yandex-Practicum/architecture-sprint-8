// App.tsx — упрощён: убрана прямая интеграция с Keycloak через keycloak-js.
// Аутентификация теперь полностью управляется bionicpro-auth (BFF).
// Фронтенд не знает о токенах, работает только с session cookie.

import React from 'react';
import ReportPage from './components/ReportPage';

const App: React.FC = () => {
  return (
    <div className="App">
      <ReportPage />
    </div>
  );
};

export default App;
