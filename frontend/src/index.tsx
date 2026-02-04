import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);

// StrictMode в dev дважды монтирует компоненты — из-за этого страница может мигать.
// Раскомментируйте StrictMode для проверки побочных эффектов.
root.render(<App />);