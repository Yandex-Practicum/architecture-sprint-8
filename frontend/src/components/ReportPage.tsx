import React, { useEffect, useState } from 'react';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8000';

interface ReportResponse {
  report_url: string | null;
  etl_date?: string;
  cached?: boolean;
  message?: string;
}

const ReportPage: React.FC = () => {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [reportMeta, setReportMeta] = useState<{ etl_date?: string; cached?: boolean } | null>(null);

  // Check authentication status via BFF session cookie (no tokens in JS)
  useEffect(() => {
    fetch(`${AUTH_URL}/auth/status`, { credentials: 'include' })
      .then(res => res.json())
      .then(data => setAuthenticated(data.authenticated))
      .catch(() => setAuthenticated(false));
  }, []);

  const fetchReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReportUrl(null);
      setReportMeta(null);

      // Session cookie is sent automatically via credentials: 'include'.
      // BFF validates session, injects Bearer token internally, proxies to Reports API.
      const response = await fetch(`${AUTH_URL}/api/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setAuthenticated(false);
        return;
      }

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data: ReportResponse = await response.json();

      if (!data.report_url) {
        setError(data.message || 'Report not available yet. Please try again after the nightly ETL run.');
        return;
      }

      setReportUrl(data.report_url);
      setReportMeta({ etl_date: data.etl_date, cached: data.cached });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await fetch(`${AUTH_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setAuthenticated(false);
  };

  if (authenticated === null) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <p className="mb-4 text-gray-600">Please log in to access your reports.</p>
        <a
          href={`${AUTH_URL}/auth/login`}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </a>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <button
          onClick={fetchReport}
          disabled={loading}
          className={`w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Get Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">{error}</div>
        )}

        {reportUrl && (
          <div className="mt-4 p-4 bg-green-50 rounded border border-green-200">
            {reportMeta && (
              <p className="text-xs text-gray-500 mb-2">
                Data as of: <span className="font-medium">{reportMeta.etl_date}</span>
                {reportMeta.cached !== undefined && (
                  <span className="ml-2 px-1 py-0.5 bg-gray-100 rounded text-gray-400">
                    {reportMeta.cached ? 'cached' : 'freshly generated'}
                  </span>
                )}
              </p>
            )}
            <a
              href={reportUrl}
              download
              className="block text-center px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
            >
              Download CSV
            </a>
          </div>
        )}

        <button
          onClick={handleLogout}
          className="mt-6 text-sm text-gray-400 hover:text-gray-600 underline block"
        >
          Logout
        </button>
      </div>
    </div>
  );
};

export default ReportPage;
