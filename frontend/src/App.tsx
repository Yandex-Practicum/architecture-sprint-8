import React from 'react';
import ReportPage from './components/ReportPage';

// BFF-паттерн: фронтенд НЕ знает про Keycloak.
// Нет keycloak-js, нет @react-keycloak/web, нет токенов в браузере.
// Вся аутентификация — через cookie от bionicpro-auth (BFF).

const App: React.FC = () => {
  return (
    <div className="App">
      <ReportPage />
    </div>
  );
};

export default App;
