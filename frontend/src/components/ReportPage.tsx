import React, {useEffect, useState} from 'react';

const ReportPage: React.FC = () => {
  const [authState, setAuthState] = useState('loading');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
      async function checkAuthStatus() {
          const response = await fetch(`${process.env.REACT_APP_API_URL}/status`, {
              credentials: 'include'
          });
          const body = await response.json();

          if (body.authenticated) {
              setAuthState('authenticated');
          } else {
              setAuthState('guest');
          }
      }

      checkAuthStatus();
  }, [])

  const downloadReport = async () => {
    if (authState !== 'authenticated') {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports?date=${new Date().toISOString().split('T')[0]}`, {
        credentials: 'include'
      });
      if (response.status === 404) {
        setError('No report available');
        return;
      } else if (!response.ok) {
        setError('Failed to download report');
        return;
      }

      const reportUrl = await response.text();
      const reportResponse = await fetch(reportUrl);
      if (!reportResponse.ok) {
        setError('Failed to download report from CDN');
        return;
      }

      const reportBlob = await reportResponse.blob();
      const reportA = document.createElement('a');
      reportA.href = URL.createObjectURL(reportBlob);
      reportA.download = 'report.json';
      reportA.click();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (authState === 'loading') {
    return <div>Loading...</div>;
  }

  if (authState === 'guest') {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <a
          href={`${process.env.REACT_APP_API_URL}/oauth2/authorization/reports`}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </a>
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