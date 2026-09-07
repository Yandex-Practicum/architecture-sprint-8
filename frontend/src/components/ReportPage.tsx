import React, { useState, useEffect } from 'react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<any | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [loginForm, setLoginForm] = useState({ username: '', password: '' });

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    try {
      const response = await fetch(`${API_URL}/auth/me`, {
        credentials: 'include'
      });
      if (response.ok) {
        const data = await response.json();
        setUsername(data.username);
      }
    } catch (err) {
      // не авторизован
    }
  };

  const handleLogin = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(loginForm)
      });

      if (!response.ok) {
        throw new Error('Invalid credentials');
      }

      await checkAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = async () => {
    await fetch(`${API_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include'
    });
    setUsername(null);
    setReportData(null);
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_URL}/reports`, {
        method: 'GET',
        credentials: 'include'
      });

      if (response.status === 401) {
        setError('Not authenticated. Please login again.');
        setUsername(null);
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to get report');
      }

      const data = await response.json();
      setReportData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!username) {
    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
          <div className="p-8 bg-white rounded-lg shadow-md w-80">
            <h1 className="text-2xl font-bold mb-6">Login</h1>

            <input
                type="text"
                placeholder="Username"
                value={loginForm.username}
                onChange={e => setLoginForm({ ...loginForm, username: e.target.value })}
                className="w-full mb-3 px-3 py-2 border rounded"
            />

            <input
                type="password"
                placeholder="Password"
                value={loginForm.password}
                onChange={e => setLoginForm({ ...loginForm, password: e.target.value })}
                className="w-full mb-4 px-3 py-2 border rounded"
            />

            <button
                onClick={handleLogin}
                disabled={loading}
                className="w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>

            {error && (
                <div className="mt-4 p-3 bg-red-100 text-red-700 rounded">
                  {error}
                </div>
            )}
          </div>
        </div>
    );
  }

  return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>
          <p className="mb-4 text-gray-600">Welcome, {username}</p>

          <button
              onClick={downloadReport}
              disabled={loading}
              className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
                  loading ? 'opacity-50 cursor-not-allowed' : ''
              }`}
          >
            {loading ? 'Generating Report...' : 'Download Report'}
          </button>

          {reportData && (
              <div className="mt-4 p-4 bg-green-100 rounded">
                <p className="font-bold">Report for {reportData.username}:</p>
                <p>Prosthesis ID: {reportData.data.prosthesis_id}</p>
                <p>Usage hours: {reportData.data.usage_hours}</p>
                <p>Battery cycles: {reportData.data.battery_cycles}</p>
                <p>Movements: {reportData.data.movements_count}</p>
              </div>
          )}

          {error && (
              <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
                {error}
              </div>
          )}

          <button
              onClick={handleLogout}
              className="mt-4 px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            Logout
          </button>
        </div>
      </div>
  );
};

export default ReportPage;