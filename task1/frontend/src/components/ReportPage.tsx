import React, { useState, useEffect } from 'react';

const ReportPage: React.FC = () => {
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    checkAuthStatus();
  }, []);

  const checkAuthStatus = async () => {
    try {
      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/protected`, {
        credentials: 'include'
      });
      if (response.ok) {
        setAuthenticated(true);
      } else {
        setAuthenticated(false);
      }
    } catch (err) {
      setAuthenticated(false);
    }
  };

  const login = () => {
    window.location.href = `${process.env.REACT_APP_API_URL}/auth/login`;
  };

  const logout = async () => {
    try {
      await fetch(`${process.env.REACT_APP_API_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
      setAuthenticated(false);
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/api/reports`, {
        credentials: 'include'
      });

      if (!response.ok) {
        if (response.status === 401) {
          setAuthenticated(false);
          throw new Error('Session expired. Please login again.');
        }
        throw new Error('Failed to download report');
      }

      const data = await response.json();
      console.log('Reports:', data);
      // Handle report data
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">BionicPRO Reports</h1>
          <p className="mb-4 text-gray-600">Please login to access reports</p>
          <button
            onClick={login}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Login
          </button>
        </div>
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
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            Logout
          </button>
        </div>
        <button
          onClick={downloadReport}
          disabled={loading}
          className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Download Report'}
        </button>
        {error && <p className="text-red-500 mt-4">{error}</p>}
      </div>
    </div>
  );
};

export default ReportPage;