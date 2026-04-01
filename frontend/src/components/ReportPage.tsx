import React, { useState, useEffect } from 'react';

const AUTH_URL = process.env.REACT_APP_AUTH_URL ?? 'http://localhost:8001';

const ReportPage: React.FC = () => {
  const [loading,      setLoading]      = useState(false);
  const [error,        setError]        = useState<string | null>(null);
  const [reportUrl,    setReportUrl]    = useState<string | null>(null);
  const [user,         setUser]         = useState<{ username: string } | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  useEffect(() => {
    fetch(`${AUTH_URL}/auth/userinfo`, {
      credentials: 'include',
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => { if (data) setUser(data); })
      .finally(() => setCheckingAuth(false));
  }, []);

  const handleLogin = () => {
    window.location.href = `${AUTH_URL}/auth/login`;
  };

  const handleLogout = () => {
    window.location.href = `${AUTH_URL}/auth/logout`;
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReportUrl(null);

      const response = await fetch(`${AUTH_URL}/api/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setUser(null);
        setError('Сессия истекла. Войдите снова.');
        return;
      }
      if (response.status === 403) {
        setError('Доступ запрещён.');
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(body.error ?? 'Ошибка при получении отчёта');
        return;
      }

      const data = await response.json();
      setReportUrl(data.cdn_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Сетевая ошибка');
    } finally {
      setLoading(false);
    }
  };

  if (checkingAuth) {
    return <div className="flex items-center justify-center min-h-screen">Загрузка...</div>;
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md text-center">
          <h1 className="text-2xl font-bold mb-4">BionicPRO</h1>
          <p className="text-gray-600 mb-6">Войдите, чтобы получить отчёт о протезе</p>
          <button
            onClick={handleLogin}
            className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Войти через Keycloak
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-md">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <div className="text-right">
            <p className="text-sm text-gray-500">{user.username}</p>
            <button onClick={handleLogout} className="text-xs text-red-500 hover:underline">
              Выйти
            </button>
          </div>
        </div>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Генерация отчёта...' : 'Скачать отчёт о протезе'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded text-sm">{error}</div>
        )}

        {reportUrl && (
          <div className="mt-4 p-4 bg-green-100 rounded">
            <p className="text-sm text-green-800 mb-2">Отчёт готов:</p>
            <a
              href={reportUrl}
              target="_blank"
              rel="noreferrer"
              className="text-blue-600 hover:underline text-sm break-all"
            >
              {reportUrl}
            </a>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;