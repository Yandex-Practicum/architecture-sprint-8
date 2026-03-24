import React, { useState } from 'react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface DailyTelemetry {
  customer_id: string;
  date: string;
  total_events: number;
  avg_signal_strength: number;
  active_hours: number;
  movement_count: number;
}

interface ReportData {
  source: string;
  cdn_url: string;
  report: {
    customer_id: string;
    username: string;
    days: DailyTelemetry[];
  };
}

interface Props {
  authenticated: boolean;
  username: string | null;
  onLogin: () => void;
  onLogout: () => void;
}

const ReportPage: React.FC<Props> = ({ authenticated, username, onLogin, onLogout }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReport(null);

      const response = await fetch(`${API_URL}/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setError('Session expired. Please log in again.');
        return;
      }
      if (response.status === 403) {
        setError('Access denied. Only prosthetic users can view reports.');
        return;
      }
      if (response.status === 404) {
        setError('No report data available yet. Data may not have been processed.');
        return;
      }
      if (!response.ok) {
        setError(`Server error: ${response.status}`);
        return;
      }

      const data: ReportData = await response.json();
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md text-center">
          <h1 className="text-2xl font-bold mb-6">BionicPRO Reports</h1>
          <p className="mb-4 text-gray-600">Please log in to view your reports.</p>
          <button
            onClick={onLogin}
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
            <span className="text-gray-600">Logged in as: <strong>{username}</strong></span>
            <button
              onClick={onLogout}
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

        {report && (
          <div className="mt-6">
            <p className="text-sm text-gray-500 mb-2">
              Source: {report.source} | CDN: <a href={report.cdn_url} className="underline">{report.cdn_url}</a>
            </p>
            <table className="w-full border-collapse border border-gray-300 text-sm">
              <thead>
                <tr className="bg-gray-100">
                  <th className="border border-gray-300 px-3 py-2">Date</th>
                  <th className="border border-gray-300 px-3 py-2">Events</th>
                  <th className="border border-gray-300 px-3 py-2">Avg Signal</th>
                  <th className="border border-gray-300 px-3 py-2">Active Hours</th>
                  <th className="border border-gray-300 px-3 py-2">Movements</th>
                </tr>
              </thead>
              <tbody>
                {report.report.days.map((day, i) => (
                  <tr key={i} className={i % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                    <td className="border border-gray-300 px-3 py-2">{day.date}</td>
                    <td className="border border-gray-300 px-3 py-2">{day.total_events}</td>
                    <td className="border border-gray-300 px-3 py-2">{day.avg_signal_strength.toFixed(2)}</td>
                    <td className="border border-gray-300 px-3 py-2">{day.active_hours.toFixed(1)}</td>
                    <td className="border border-gray-300 px-3 py-2">{day.movement_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <details className="mt-4">
              <summary className="cursor-pointer text-sm text-gray-500">Raw JSON</summary>
              <pre className="mt-2 p-3 bg-gray-100 rounded text-xs overflow-auto max-h-64">
                {JSON.stringify(report, null, 2)}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
