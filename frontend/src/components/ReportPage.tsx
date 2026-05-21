import React, { useState, useEffect } from 'react';

const BFF_URL = 'http://localhost:8081';

interface User {
  sub: string | null;
  name: string | null;
  email: string | null;
  roles: string[];
}

const ReportPage: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${BFF_URL}/auth/me`, { credentials: 'include' })
      .then(res => (res.ok ? res.json() : Promise.reject()))
      .then(data => setUser(data.user))
      .catch(() => setUser(null))
      .finally(() => setAuthLoading(false));
  }, []);

  const login = () => {
    fetch(`${BFF_URL}/auth/login`, { credentials: 'include' })
      .then(res => res.json())
      .then(data => { window.location.href = data.authorization_url; });
  };

  const logout = () => {
    fetch(`${BFF_URL}/auth/session`, { method: 'DELETE', credentials: 'include' })
      .finally(() => setUser(null));
  };

  const downloadReport = async () => {
    try {
      setReportLoading(true);
      setError(null);

      const res = await fetch(`${BFF_URL}/api/reports`, { credentials: 'include' });

      if (!res.ok) throw new Error(`BFF returned error status: ${res.status}`);

      const data = await res.json();
      console.log('Report generated:', data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setReportLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <p className="text-gray-600">Loading...</p>
      </div>
    );
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
        {error && <p className="mt-4 text-red-600">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <button
            onClick={logout}
            className="px-3 py-1 text-sm bg-gray-500 text-white rounded hover:bg-gray-600"
          >
            Logout
          </button>
        </div>

        <p className="mb-4 text-gray-600">Welcome, {user.name ?? user.email ?? user.sub}</p>

        <button
          onClick={downloadReport}
          disabled={reportLoading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            reportLoading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {reportLoading ? 'Generating Report...' : 'Download Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">{error}</div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
