import React, { useState } from 'react';
import { useAuth } from '../hooks/useAuth';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8000';

interface ReportData {
  download_url?: string;
  reports?: Array<{
    report_date: string;
    device_id: string;
    product_name: string;
    total_usage_hours: number;
    active_movements: number;
    battery_cycles: number;
    avg_signal_strength: number;
    error_count: number;
  }>;
  message?: string;
}

const ReportPage: React.FC = () => {
  const { user, isAuthenticated, isLoading, login, logout } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${AUTH_URL}/api/reports`, {
        credentials: 'include',
      });

      if (!response.ok) {
        if (response.status === 401) {
          login();
          return;
        }
        if (response.status === 403) {
          setError('You do not have permission to access reports.');
          return;
        }
        throw new Error(`Server error: ${response.status}`);
      }

      const data: ReportData = await response.json();
      setReportData(data);

      // If a CDN download URL is provided, trigger download
      if (data.download_url) {
        const a = document.createElement('a');
        a.href = data.download_url;
        a.download = 'report.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-lg text-gray-600">Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md text-center">
          <h1 className="text-2xl font-bold mb-4">BionicPRO Reports</h1>
          <p className="text-gray-600 mb-6">Please log in to access your prosthetic usage reports.</p>
          <button
            onClick={login}
            className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-4xl">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <div className="flex items-center gap-4">
            <span className="text-gray-600">
              {user?.name || user?.username}
            </span>
            <button
              onClick={logout}
              className="px-3 py-1 text-sm bg-gray-200 rounded hover:bg-gray-300"
            >
              Logout
            </button>
          </div>
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

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {reportData?.reports && reportData.reports.length > 0 && (
          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full border-collapse border border-gray-300">
              <thead>
                <tr className="bg-gray-50">
                  <th className="border border-gray-300 px-4 py-2 text-left">Date</th>
                  <th className="border border-gray-300 px-4 py-2 text-left">Device</th>
                  <th className="border border-gray-300 px-4 py-2 text-left">Product</th>
                  <th className="border border-gray-300 px-4 py-2 text-right">Usage (hrs)</th>
                  <th className="border border-gray-300 px-4 py-2 text-right">Movements</th>
                  <th className="border border-gray-300 px-4 py-2 text-right">Battery Cycles</th>
                  <th className="border border-gray-300 px-4 py-2 text-right">Signal Strength</th>
                  <th className="border border-gray-300 px-4 py-2 text-right">Errors</th>
                </tr>
              </thead>
              <tbody>
                {reportData.reports.map((row, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="border border-gray-300 px-4 py-2">{row.report_date}</td>
                    <td className="border border-gray-300 px-4 py-2">{row.device_id}</td>
                    <td className="border border-gray-300 px-4 py-2">{row.product_name}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">{row.total_usage_hours.toFixed(1)}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">{row.active_movements}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">{row.battery_cycles}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">{row.avg_signal_strength.toFixed(2)}</td>
                    <td className="border border-gray-300 px-4 py-2 text-right">{row.error_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {reportData?.message && (
          <div className="mt-4 p-4 bg-yellow-100 text-yellow-800 rounded">
            {reportData.message}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
