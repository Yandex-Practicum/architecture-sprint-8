import React, { useState } from 'react';
import { useAuth, AUTH_URL } from '../auth/AuthContext';

const ReportPage: React.FC = () => {
  const { loading, authenticated, username, login, logout } = useAuth();
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  const downloadReport = async () => {
    try {
      setReportLoading(true);
      setError(null);
      setReportUrl(null);

      // Браузер хранит только cookie bpro_session. bionicpro-auth
      // подставляет access_token на сервере перед проксированием этого вызова.
      const response = await fetch(`${AUTH_URL}/api/reports`, {
        credentials: 'include',
      });

      if (response.status === 404) {
        throw new Error('No report has been generated for this period yet');
      }
      if (!response.ok) {
        throw new Error(`Report request failed: ${response.status}`);
      }

      const data = await response.json();
      // reports-api отдаёт ссылку на объектное хранилище/CDN, когда она
      // доступна (Задание 3); до этого возвращает тело отчёта напрямую.
      if (data.url) {
        setReportUrl(data.url);
      } else {
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        setReportUrl(URL.createObjectURL(blob));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setReportLoading(false);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={login}
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
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <button onClick={logout} className="ml-6 text-sm text-gray-500 hover:underline">
            Logout ({username})
          </button>
        </div>

        <button
          onClick={downloadReport}
          disabled={reportLoading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            reportLoading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {reportLoading ? 'Generating Report...' : 'Download Report'}
        </button>

        {reportUrl && (
          <div className="mt-4">
            <a href={reportUrl} target="_blank" rel="noreferrer" className="text-blue-600 underline">
              Open report
            </a>
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
