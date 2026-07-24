import React from 'react';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8081';

const LoginPage: React.FC = () => {
  const handleKeycloakLogin = () => {
    window.location.href = `${API_BASE}/auth/login`;
  };

  const handleYandexLogin = () => {
    window.location.href = `${API_BASE}/auth/yandex/login`;
  };

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="bg-white p-8 rounded-lg shadow-md w-96">
        <h1 className="text-2xl font-bold text-center mb-6">BionicPRO</h1>
        <p className="text-center text-gray-600 mb-6">Войдите в систему</p>

        <div className="space-y-3">
          <button
            onClick={handleKeycloakLogin}
            className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 transition"
          >
            Войти через Keycloak
          </button>

          <button
            onClick={handleYandexLogin}
            className="w-full bg-red-600 text-white py-2 rounded hover:bg-red-700 transition"
          >
            Войти через Яндекс
          </button>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;