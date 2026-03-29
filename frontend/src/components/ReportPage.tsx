import React, { useCallback, useEffect, useState } from 'react';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8181';
const API_URL = process.env.REACT_APP_API_URL || AUTH_URL;

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<{ authenticated: boolean; subject?: string } | null>(null);

  const checkSession = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/session`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setSessionInfo({ authenticated: true, subject: data.subject as string });
      } else {
        setSessionInfo({ authenticated: false });
      }
    } catch {
      setSessionInfo({ authenticated: false });
    }
  }, []);

  useEffect(() => {
    void checkSession();
  }, [checkSession]);

  const login = () => {
    window.location.href = `${AUTH_URL}/oauth2/authorization/keycloak`;
  };

  const logout = async () => {
    await fetch(`${API_URL}/api/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setSessionInfo({ authenticated: false });
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/api/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setError('Сессия недействительна. Войдите снова.');
        setSessionInfo({ authenticated: false });
        return;
      }

      if (!response.ok) {
        setError(`Ошибка: ${response.status}`);
        return;
      }

      await response.json();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (sessionInfo === null) {
    return <div className="flex items-center justify-center min-h-screen bg-gray-100">Загрузка...</div>;
  }

  if (!sessionInfo.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          type="button"
          onClick={login}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Войти через Keycloak
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-lg">
        <p className="text-sm text-gray-600 mb-4">
          Пользователь: <strong>{sessionInfo.subject}</strong>
        </p>
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <div className="flex gap-2 mb-4">
          <button
            type="button"
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Запрос...' : 'Получить отчёт (cookie)'}
          </button>
          <button
            type="button"
            onClick={() => void logout()}
            className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
          >
            Выйти
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
