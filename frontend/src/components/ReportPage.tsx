import React, { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

const BFF_URL = process.env.REACT_APP_BFF_URL || 'http://localhost:4000';

const ReportPage: React.FC = () => {
  const { isAuthenticated, user, loading: authLoading, login, logout } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      const response = await fetch(`${BFF_URL}/api/reports`, {
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