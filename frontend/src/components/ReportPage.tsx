import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportRow {
  user_id: string;
  username: string;
  first_name: string;
  last_name: string;
  prosthesis_id: string;
  prosthesis_type: string;
  report_date: string;
  total_movements: number;
  avg_signal_strength: number;
  avg_battery_level: number;
  avg_response_time_ms: number;
  most_common_movement: string;
}

interface ReportData {
  user_id: string;
  report: ReportRow[];
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const [data, setData]           = useState<ReportData | null>(null);

  const fetchReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setData(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: { Authorization: `Bearer ${keycloak.token}` },
      });

      if (response.status === 404) {
        setError('No report data available yet. Please wait for the next scheduled ETL run.');
        return;
      }
      if (response.status === 403) {
        setError('Access denied: your account does not have the prosthesis user role.');
        return;
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        setError(body.detail ?? `Request failed with status ${response.status}`);
        return;
      }

      const reportData: ReportData = await response.json();
      setData(reportData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const downloadJson = () => {
    if (!data) return;
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `report_${data.user_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!initialized) return <div className="flex items-center justify-center min-h-screen">Loading...</div>;

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
    <div className="flex flex-col items-center min-h-screen bg-gray-100 p-8">
      <div className="w-full max-w-5xl bg-white rounded-lg shadow-md p-8">
        <h1 className="text-2xl font-bold mb-2">Prosthesis Usage Report</h1>
        <p className="text-gray-500 mb-6 text-sm">
          Logged in as: <span className="font-medium">{keycloak.tokenParsed?.preferred_username}</span>
        </p>

        <div className="flex gap-4 mb-6">
          <button
            onClick={fetchReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
          >
            {loading ? 'Loading...' : 'Get Report'}
          </button>

          {data && (
            <button
              onClick={downloadJson}
              className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
            >
              Download JSON
            </button>
          )}
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-100 text-red-700 rounded">{error}</div>
        )}

        {data && data.report.length > 0 && (
          <div className="overflow-x-auto">
            <p className="text-sm text-gray-500 mb-2">
              Prosthesis: <span className="font-medium">{data.report[0].prosthesis_type}</span>
              {' '}({data.report[0].prosthesis_id}) — last {data.report.length} day(s)
            </p>
            <table className="min-w-full text-sm border-collapse">
              <thead>
                <tr className="bg-gray-100 text-gray-700">
                  <th className="px-3 py-2 border text-left">Date</th>
                  <th className="px-3 py-2 border text-right">Movements</th>
                  <th className="px-3 py-2 border text-right">Avg Signal %</th>
                  <th className="px-3 py-2 border text-right">Avg Battery %</th>
                  <th className="px-3 py-2 border text-right">Avg Response ms</th>
                  <th className="px-3 py-2 border text-left">Top Movement</th>
                </tr>
              </thead>
              <tbody>
                {data.report.map((row) => (
                  <tr key={row.report_date} className="hover:bg-gray-50">
                    <td className="px-3 py-2 border">{row.report_date}</td>
                    <td className="px-3 py-2 border text-right">{row.total_movements}</td>
                    <td className="px-3 py-2 border text-right">{row.avg_signal_strength.toFixed(1)}</td>
                    <td className="px-3 py-2 border text-right">{row.avg_battery_level.toFixed(1)}</td>
                    <td className="px-3 py-2 border text-right">{row.avg_response_time_ms.toFixed(0)}</td>
                    <td className="px-3 py-2 border capitalize">{row.most_common_movement}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
