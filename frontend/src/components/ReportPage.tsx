import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const BFF_URL = process.env.REACT_APP_BFF_URL || 'http://localhost:4000';

const ReportPage: React.FC = () => {
  const { isAuthenticated, user, loading: authLoading, login, logout } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      console.log('User object:', user);
      console.log('User object keys:', Object.keys(user || {}));

      const userId = (user as any)?.user_id;
      console.log('Extracted user_id:', userId);
      
      if (!userId) {
        throw new Error(`User ID not found in user profile. Available fields: ${Object.keys(user || {}).join(', ')}. Please re-login.`);
      }

      const period = `${year}-${String(month).padStart(2, '0')}`;

      const url = `${BFF_URL}/api/reports?user_id=${userId}&period=${period}`;
      console.log('Fetching report:', url);

      const response = await fetch(url, {
        credentials: 'include',
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || `HTTP ${response.status}`);
      }

      const data = await response.json();
      setSuccess('Report downloaded successfully!');
      console.log('Report data:', data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (authLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-xl">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6 text-center">BionicPRO Reports</h1>
          <p className="mb-6 text-gray-600 text-center">
            Please log in to access your prosthesis reports
          </p>
          <button
            onClick={login}
            className="w-full px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            Login with SSO
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <div className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-900">BionicPRO Reports</h1>
            <div className="flex items-center gap-4">
              <span className="text-sm text-gray-600">
                {user?.preferred_username || user?.email || 'User'}
              </span>
              <button
                onClick={logout}
                className="px-4 py-2 text-sm bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition-colors"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h2 className="text-xl font-semibold mb-4">Usage Reports</h2>
          <p className="text-gray-600 mb-6">
            Download your prosthesis usage report with telemetry data
          </p>

          {/* Period Selector */}
          <div className="mb-6 flex items-center gap-4">
            <label className="text-sm font-medium text-gray-700">Select Period:</label>
            <select
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
                <option key={m} value={m}>
                  {new Date(2000, m - 1).toLocaleString('default', { month: 'long' })}
                </option>
              ))}
            </select>
            <input
              type="number"
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              min={2020}
              max={2030}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 w-24"
            />
          </div>

          <button
            onClick={downloadReport}
            disabled={loading}
            className={`px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Generating Report...' : 'Download Report'}
          </button>

          {error && (
            <div className="mt-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
              <strong>Error:</strong> {error}
            </div>
          )}

          {success && (
            <div className="mt-4 p-4 bg-green-100 border border-green-400 text-green-700 rounded">
              <strong>Success:</strong> {success}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ReportPage;