import React, { useEffect, useState } from 'react';

type SessionResponse = {
  authenticated: boolean;
};

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkSession = async () => {
      try {
        const response = await fetch(`${process.env.REACT_APP_AUTH_URL}/api/session`, {
          method: 'GET',
          credentials: 'include',
          headers: {
            'Accept': 'application/json'
          }
        });

        if (!response.ok) {
          setAuthenticated(false);
          return;
        }

        const sessionResponse: SessionResponse = await response.json();
        setAuthenticated(sessionResponse.authenticated);
      } catch {
        setAuthenticated(false);
      } finally {
        setCheckingAuth(false);
      }
    };

    checkSession();
  }, []);

  const login = () => {
    const returnTo = encodeURIComponent(window.location.href);
    window.location.href = `${process.env.REACT_APP_AUTH_URL}/auth/login?return_to=${returnTo}`;
  };

  const logout = async () => {
    try {
      await fetch(`${process.env.REACT_APP_AUTH_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
    } finally {
      window.location.reload();
    }
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      params.set(
        'from',
        new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().slice(0, 10)
      );
      params.set('to', new Date().toISOString().slice(0, 10));

      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/reports/me?${params.toString()}`,
        {
          method: 'GET',
          credentials: 'include',
        }
      );

      if (response.status === 401) {
        setAuthenticated(false);
        setError('Session expired');
        return;
      }

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      // берём имя файла из Content-Disposition, если есть
      const disposition = response.headers.get('Content-Disposition');
      let filename = 'usage-report.md';
      if (disposition) {
        const match = /filename="?(.*?)"?$/i.exec(disposition);
        if (match && match[1]) {
          filename = match[1];
        }
      }

      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (checkingAuth) {
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
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        <button onClick={logout}>
          Logout
        </button>


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
