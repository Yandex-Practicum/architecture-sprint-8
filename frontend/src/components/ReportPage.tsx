import React, { useEffect, useState } from 'react';

const authPrefix = process.env.REACT_APP_AUTH_PREFIX ?? '';

const loginUrl = `${authPrefix}/auth/login`;
const logoutUrl = `${authPrefix}/auth/logout`;

const apiBase = process.env.REACT_APP_API_URL ?? '';

const reportsUrl = apiBase ? `${apiBase.replace(/\/$/, '')}/reports` : '/reports';

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [checked, setChecked] = useState(false);
  const [authenticated, setAuthenticated] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get('login') === 'error') {
      setError('Login failed');
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, []);

  const checkSession = async () => {
    try {
      const res = await fetch(`${authPrefix}/auth/me`, { credentials: 'include' });
      setAuthenticated(res.ok);
    } catch {
      setAuthenticated(false);
    } finally {
      setChecked(true);
    }
  };

  useEffect(() => {
    void checkSession();
  }, []);

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await fetch(reportsUrl, { credentials: 'include' });
      if (response.status === 401) {
        setError('Session expired — please sign in again');
        setAuthenticated(false);
        return;
      }
      if (!response.ok) {
        setError(await response.text());
        return;
      }
      const data = await response.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'report.json';
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!checked) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <a
          href={loginUrl}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login (Keycloak via bionicpro-auth, PKCE)
        </a>
        {error && <p className="mt-4 text-red-600">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>
        <div className="flex gap-3 mb-4">
          <button
            type="button"
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Generating Report...' : 'Download Report'}
          </button>
          <a
            href={logoutUrl}
            className="px-4 py-2 border border-gray-300 rounded text-gray-700 hover:bg-gray-50"
          >
            Logout
          </a>
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
