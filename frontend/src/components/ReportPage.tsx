import React, { useEffect, useState } from 'react';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8000';
const REPORTS_URL = process.env.REACT_APP_REPORTS_URL || 'http://localhost:8001';

interface User {
  sub: string;
  username: string;
  roles: string[];
}

const ReportPage: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Токены фронтенду недоступны — во всех запросах идёт сессионная cookie (credentials: 'include').
  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await fetch(`${AUTH_URL}/auth/me`, {
          credentials: 'include',
        });
        if (response.ok) {
          setUser(await response.json());
        }
      } catch {
      } finally {
        setInitialized(true);
      }
    };
    checkSession();
  }, []);

  const login = () => {
    window.location.href = `${AUTH_URL}/auth/login`;
  };

  const logout = async () => {
    await fetch(`${AUTH_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setUser(null);
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${REPORTS_URL}/reports`, {
        credentials: 'include',
      });

      if (response.status === 404) {
        throw new Error('Report is not ready yet — data is still being processed');
      }
      if (!response.ok) {
        throw new Error(`Failed to load report: ${response.status}`);
      }

      // Сервис отдаёт ссылку на CDN — сам файл скачиваем уже оттуда
      const { report_url: reportUrl } = await response.json();
      const fileResponse = await fetch(reportUrl);
      const blob = await fileResponse.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `report-${user?.username ?? 'me'}.json`;
      link.click();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!user) {
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
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <button onClick={logout} className="text-sm text-gray-500 hover:text-gray-800">
            Logout ({user.username})
          </button>
        </div>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">{error}</div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
