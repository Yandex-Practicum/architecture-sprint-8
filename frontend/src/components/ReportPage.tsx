import React, { useState, useEffect } from 'react';

const AUTH_SERVICE_URL = process.env.REACT_APP_AUTH_SERVICE_URL || 'http://127.0.0.1:5000';

const ReportPage: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      const response = await fetch(`${AUTH_SERVICE_URL}/auth/user`, {
        credentials: 'include'
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        setUser(null);
      }
    } catch (err) {
      console.error('Session check failed:', err);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = () => {
    window.location.href = `${AUTH_SERVICE_URL}/auth/login`;
  };

  const handleLogout = async () => {
    try {
      await fetch(`${AUTH_SERVICE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
      setUser(null);
    } catch (err) {
      setError('Logout failed');
    }
  };

  const downloadReport = async () => {
    try {
      setReportLoading(true);
      setError(null);

      const tokenResponse = await fetch(`${AUTH_SERVICE_URL}/auth/token`, {
        credentials: 'include'
      });

      if (!tokenResponse.ok) {
        throw new Error('Failed to get access token');
      }

      const { access_token } = await tokenResponse.json();

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${access_token}`
        }
      });

      if (!response.ok) {
        throw new Error('Failed to download report');
      }

      alert('Report downloaded successfully!');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setReportLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div>Loading...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">BionicPRO Authentication</h1>
          <p className="mb-4 text-gray-600">Please login to access your reports</p>
          <button
            onClick={handleLogin}
            className="px-6 py-3 bg-blue-500 text-white rounded hover:bg-blue-600 transition"
          >
            Login with Keycloak
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md max-w-md w-full">
        <div className="mb-6">
          <h1 className="text-2xl font-bold mb-2">Usage Reports</h1>
          <div className="text-sm text-gray-600">
            <p>Welcome, {user.preferred_username || user.name}!</p>
            <p className="text-xs mt-1">{user.email}</p>
          </div>
        </div>

        <div className="space-y-3">
          <button
            onClick={downloadReport}
            disabled={reportLoading}
            className={`w-full px-4 py-3 bg-blue-500 text-white rounded hover:bg-blue-600 transition ${
              reportLoading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {reportLoading ? 'Generating Report...' : 'Download Report'}
          </button>

          <button
            onClick={handleLogout}
            className="w-full px-4 py-3 bg-gray-500 text-white rounded hover:bg-gray-600 transition"
          >
            Logout
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded text-sm">
            {error}
          </div>
        )}

        <div className="mt-6 text-xs text-gray-500 border-t pt-4">
          <p className="font-semibold mb-2">Security Features:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>PKCE-protected authentication</li>
            <li>HTTP-only secure session cookies</li>
            <li>No tokens exposed to frontend</li>
            <li>Automatic token refresh</li>
            <li>Session rotation enabled</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default ReportPage;