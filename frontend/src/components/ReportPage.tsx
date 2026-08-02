import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface DailyMetric {
  metric_date: string;
  avg_response_time_ms: number;
  max_response_time_ms: number;
  signals_count: number;
  battery_avg_level: number;
}

interface ReportData {
  username: string;
  email: string;
  prosthetic_id: string;
  period_from: string;
  period_to: string;
  metrics: DailyMetric[];
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReport(null);

      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/reports`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data: ReportData = await response.json();
      setReport(data);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4">
      <div className="p-8 bg-white rounded-lg shadow-md max-w-4xl w-full">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>
        
        <div className="flex gap-4 mb-6">
          <button
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Generating Report...' : 'Download Report'}
          </button>
          
          {report && (
            <button
              onClick={() => setReport(null)}
              className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
            >
              Clear Report
            </button>
          )}
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {loading && (
          <div className="mb-4 p-4 bg-blue-50 text-blue-700 rounded">
            Loading report...
          </div>
        )}

        {report && (
          <div className="mt-4 border-t pt-4">
            <h2 className="text-xl font-semibold mb-4">Report for {report.username}</h2>
            
            <div className="grid grid-cols-2 gap-2 mb-4 text-sm bg-gray-50 p-3 rounded">
              <div><span className="font-medium">Email:</span> {report.email}</div>
              <div><span className="font-medium">Prosthetic ID:</span> {report.prosthetic_id}</div>
              <div><span className="font-medium">Period:</span> {report.period_from} to {report.period_to}</div>
              <div><span className="font-medium">Total records:</span> {report.metrics.length}</div>
            </div>

            {report.metrics.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border border-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="border p-2 text-left">Date</th>
                      <th className="border p-2 text-right">Avg Response (ms)</th>
                      <th className="border p-2 text-right">Max Response (ms)</th>
                      <th className="border p-2 text-right">Signals</th>
                      <th className="border p-2 text-right">Battery %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {report.metrics.map((metric, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="border p-2">{metric.metric_date}</td>
                        <td className="border p-2 text-right">
                          <span className={metric.avg_response_time_ms > 100 ? 'text-red-600 font-medium' : ''}>
                            {metric.avg_response_time_ms.toFixed(1)}
                          </span>
                        </td>
                        <td className="border p-2 text-right">{metric.max_response_time_ms}</td>
                        <td className="border p-2 text-right">{metric.signals_count}</td>
                        <td className="border p-2 text-right">{metric.battery_avg_level}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="text-gray-500 text-center py-4">
                No metrics found for the selected period.
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;