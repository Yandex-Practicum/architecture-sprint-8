import React from 'react';
import ReportPage from './components/ReportPage';

// Прямая интеграция с Keycloak убрана: фронт работает только с сессионной cookie от bionicpro-auth.
const App: React.FC = () => {
  return (
    <div className="App">
      <ReportPage />
    </div>
  );
};

export default App;
