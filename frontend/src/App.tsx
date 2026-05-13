import React from 'react';
import ReportPage from './components/ReportPage';

// Token handling has been moved to the BFF (bionicpro-auth).
// The frontend only works with HTTP-only session cookies — no tokens in JS.
const App: React.FC = () => (
  <div className="App">
    <ReportPage />
  </div>
);

export default App;