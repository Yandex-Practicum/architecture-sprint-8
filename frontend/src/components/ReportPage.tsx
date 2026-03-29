import React, { useEffect, useState } from 'react';

const apiUrl = (process.env.REACT_APP_API_URL || '').replace(/\/$/, '');

const ReportPage: React.FC = () => {
  const [sessionLoading, setSessionLoading] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${apiUrl}/reports`, { credentials: 'include' });
        if (cancelled) return;
        if (res.ok) {
          setAuthenticated(true);
        } else if (res.status === 401) {
          setAuthenticated(false);
        } else {
          setError(`Unexpected status: ${res.status}`);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Network error');
        }
      } finally {
        if (!cancelled) {
          setSessionLoading(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const goToLogin = () => {
    window.location.href = `${apiUrl}/auth/login`;
  };

  const downloadReport = async () => {
    try {
      setDownloadLoading(true);
      setError(null);

      const response = await fetch(`${apiUrl}/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setAuthenticated(false);
        setError('Not authenticated. Please log in.');
        return;
      }

      if (!response.ok) {
        setError(`Request failed: ${response.status}`);
        return;
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setDownloadLoading(false);
    }
  };

  if (sessionLoading) {
    return <div>Loading...</div>;
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          type="button"
          onClick={goToLogin}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded max-w-md text-center">
            {error}
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <button
          type="button"
          onClick={downloadReport}
          disabled={downloadLoading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            downloadLoading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {downloadLoading ? 'Generating Report...' : 'Download Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">{error}</div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
