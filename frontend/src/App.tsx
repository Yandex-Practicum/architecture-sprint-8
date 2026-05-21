import React from 'react';
import ReportPage from './components/ReportPage';
import CallbackPage from './components/CallbackPage';

const App: React.FC = () => {
  if (window.location.pathname === '/authentication/callback') {
    return <CallbackPage />;
  }

  return (
    <div className="App">
      <ReportPage />
    </div>
  );
};

export default App;
