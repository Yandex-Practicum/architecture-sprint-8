import React, { useEffect, useState } from 'react';

type User = {
  id: string;
  username: string;
  email?: string;
  roles: string[];
};

type Report = {
  userId: string;
  userName: string;
  prosthesisId: string;
  periodStart: string;
  periodEnd: string;
  eventsCount: number;
  avgReactionMs: number;
  minBatteryLevel: number;
  lastPreparedAt: string;
};

const browserHost = window.location.hostname || 'localhost';
const AUTH_URL = process.env.REACT_APP_AUTH_URL || `http://${browserHost}:8000`;
const API_URL = process.env.REACT_APP_API_URL || `http://${browserHost}:8001`;

const ReportPage: React.FC = () => {
  const [user, setUser] = useState<User | null>(null);
  const [initialized, setInitialized] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [cacheStatus, setCacheStatus] = useState<string | null>(null);
  const [storageKey, setStorageKey] = useState<string | null>(null);

  useEffect(() => {
    const loadSession = async () => {
      try {
        const response = await fetch(`${AUTH_URL}/auth/me`, {
          credentials: 'include'
        });

        if (response.ok) {
          const data = await response.json();
          setUser(data.user);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load session');
      } finally {
        setInitialized(true);
      }
    };

    loadSession();
  }, []);

  const login = () => {
    window.location.href = `${AUTH_URL}/auth/login`;
  };

  const logout = async () => {
    await fetch(`${AUTH_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include'
    });
    setUser(null);
    setReportUrl(null);
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReportUrl(null);
      setReport(null);
      setCacheStatus(null);
      setStorageKey(null);

      const response = await fetch(`${API_URL}/reports`, {
        credentials: 'include'
      });

      if (!response.ok) {
        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
          const data = await response.json();
          throw new Error(data.message || data.error || `Report request failed: ${response.status}`);
        }

        throw new Error(response.status === 401 ? 'Not authenticated' : `Report request failed: ${response.status}`);
      }

      const contentType = response.headers.get('content-type') || '';
      if (contentType.includes('application/json')) {
        const data = await response.json();
        setReport(data.report || null);
        setReportUrl(data.url || data.reportUrl || null);
        setCacheStatus(data.cacheStatus || null);
        setStorageKey(data.storageKey || null);
        return;
      }

      const blob = await response.blob();
      setReportUrl(URL.createObjectURL(blob));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    return <div className="flex items-center justify-center min-h-screen bg-gray-100">Loading...</div>;
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
        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <div className="flex items-center justify-between gap-6 mb-6">
          <div>
            <h1 className="text-2xl font-bold">Usage Reports</h1>
            <p className="text-sm text-gray-600">{user.username}</p>
          </div>
          <button
            onClick={logout}
            className="px-3 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
          >
            Logout
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

        {reportUrl && (
          <div className="mt-4">
            <a
              href={reportUrl}
              target="_blank"
              rel="noreferrer"
              className="text-blue-700 underline"
            >
              Open report from CDN
            </a>
            {cacheStatus && (
              <div className="mt-2 text-xs text-gray-500">
                Cache: {cacheStatus}
              </div>
            )}
            {storageKey && (
              <div className="mt-1 text-xs text-gray-500 break-all">
                S3 key: {storageKey}
              </div>
            )}
          </div>
        )}

        {report && (
          <div className="mt-6 text-sm text-gray-800">
            <div className="font-semibold mb-2">Prepared report</div>
            <dl className="grid grid-cols-2 gap-x-6 gap-y-2">
              <dt className="text-gray-500">User</dt>
              <dd>{report.userName}</dd>
              <dt className="text-gray-500">Prosthesis</dt>
              <dd>{report.prosthesisId}</dd>
              <dt className="text-gray-500">Period</dt>
              <dd>{report.periodStart} - {report.periodEnd}</dd>
              <dt className="text-gray-500">Events</dt>
              <dd>{report.eventsCount}</dd>
              <dt className="text-gray-500">Avg reaction</dt>
              <dd>{report.avgReactionMs} ms</dd>
              <dt className="text-gray-500">Min battery</dt>
              <dd>{report.minBatteryLevel}%</dd>
            </dl>
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
