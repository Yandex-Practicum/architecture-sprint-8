import React, { useState, useEffect } from 'react';

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<any>(null);
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [userInfo, setUserInfo] = useState<any>(null);

  const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await fetch(`${apiUrl}/auth/me`, {
        credentials: 'include',
      });

      if (response.ok) {
        const data = await response.json();
        setAuthenticated(true);
        setUserInfo(data);
      } else {
        setAuthenticated(false);
      }
    } catch (err) {
      setAuthenticated(false);
    }
  };

  const handleLogin = () => {
    window.location.href = `${apiUrl}/auth/login`;
  };

  const handleLogout = () => {
    window.location.href = `${apiUrl}/auth/logout`;
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReportData(null);

      const response = await fetch(`${apiUrl}/api/reports`, {
        credentials: 'include',
      });

      if (!response.ok) {
        if (response.status === 401) {
          setError('Сессия истекла или cookie не передаётся. Войдите снова (используйте тот же адрес, что и для входа: localhost или 127.0.0.1).');
          setAuthenticated(false);
          return;
        }
        if (response.status === 404) {
          const data = await response.json().catch(() => ({}));
          setError(data.message || 'Данные за обработанный период ещё не готовы. Отчёт формируется по расписанию.');
          return;
        }
        const data = await response.json().catch(() => ({}));
        const msg = data.message || data.error;
        setError(msg ? `${msg} (${response.status})` : `Ошибка сервера (${response.status}). Проверьте, что запущены reports-api и olap_db.`);
        return;
      }

      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const data = await response.json();
        if (data.url && !data.summary) {
          const reportResp = await fetch(data.url);
          if (reportResp.ok) {
            const report = await reportResp.json();
            setReportData(report);
          } else {
            setReportData({ ...data, summary: { period_from: data.period_from, period_to: data.period_to } });
          }
        } else {
          setReportData(data);
        }
      } else {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'report.pdf';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (authenticated === null) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={handleLogin}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <button
            onClick={handleLogout}
            className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600"
          >
            Logout
          </button>
        </div>

        {userInfo && (
          <div className="mb-4 text-sm text-gray-600 space-y-1">
            <div>Logged in as: {userInfo.email || userInfo.username || 'User'}</div>
            {userInfo.sub && (
              <div className="text-xs text-gray-500 mt-1">
                User ID для отчётов: <code className="bg-gray-100 px-1 rounded">{userInfo.sub}</code>
              </div>
            )}
          </div>
        )}
        
        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Загрузка...' : 'Получить отчёт'}
        </button>

        {reportData && (
          <div className="mt-4 p-4 bg-green-50 text-gray-800 rounded text-sm">
            <div className="font-semibold mb-2">Отчёт за период {reportData.period_from} — {reportData.period_to}</div>
            <pre className="whitespace-pre-wrap">{JSON.stringify(reportData.summary || reportData, null, 2)}</pre>
          </div>
        )}

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