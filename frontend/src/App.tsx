import React from 'react';
import { AuthProvider } from './context/AuthContext';
import ReportPage from './components/ReportPage';

const App: React.FC = () => {
  return (
    <AuthProvider>
      <div className="App">
        <ReportPage />
      </div>
    </AuthProvider>
  );
};

export default App;
