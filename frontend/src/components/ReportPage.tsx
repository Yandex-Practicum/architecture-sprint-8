import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface Report {
  customer_id: string;
  customer_name: string;
  customer_email: string | null;
  keycloak_username: string | null;
  prosthesis_model: string;
  region: string | null;
  purchase_date: string | null;
  warranty_end_date: string | null;
  warranty_status: string | null;
  total_usage_hours: number;
  avg_daily_usage_minutes: number;
  total_sessions: number;
  total_movements: number;
  avg_movements_per_session: number;
  total_errors: number;
  errors_per_session: number;
  last_active_date: string | null;
  battery_health_avg: number;
  most_common_movement: string;
  data_as_of_date: string | null;
}

interface ReportList {
  count: number;
  reports: Report[];
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [reports, setReports] = useState<Report[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReports(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.detail || `HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.reports) {
        setReports((data as ReportList).reports);
      } else {
        setReports([data as Report]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    return <div className="flex items-center justify-center min-h-screen bg-gray-100 text-gray-500">Loading...</div>;
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
    <div className="min-h-screen bg-gray-100 p-6">
      <div className="max-w-5xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-500">{keycloak.tokenParsed?.preferred_username}</span>
            <button
              onClick={() => keycloak.logout()}
              className="px-3 py-1 text-sm bg-gray-300 rounded hover:bg-gray-400"
            >
              Logout
            </button>
          </div>
        </div>

        <button
          onClick={fetchReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Loading...' : 'Get Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {reports && reports.length > 0 && (
          <div className="mt-6 space-y-6">
            {reports.length > 1 && (
              <p className="text-gray-600">{reports.length} report(s) found</p>
            )}
            {reports.map((report) => (
              <div key={report.customer_id} className="bg-white rounded-lg shadow-md p-6">
                <h2 className="text-xl font-semibold mb-4">{report.customer_name}</h2>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div><span className="font-medium">Customer ID:</span> {report.customer_id}</div>
                  <div><span className="font-medium">Email:</span> {report.customer_email || '—'}</div>
                  <div><span className="font-medium">Keycloak User:</span> {report.keycloak_username || '—'}</div>
                  <div><span className="font-medium">Prosthesis Model:</span> {report.prosthesis_model}</div>
                  <div><span className="font-medium">Region:</span> {report.region || '—'}</div>
                  <div>
                    <span className="font-medium">Warranty:</span>{' '}
                    <span className={report.warranty_status === 'active' ? 'text-green-600' : 'text-red-600'}>
                      {report.warranty_status || '—'}
                    </span>
                  </div>
                  <div><span className="font-medium">Purchase Date:</span> {report.purchase_date || '—'}</div>
                  <div><span className="font-medium">Warranty End:</span> {report.warranty_end_date || '—'}</div>
                </div>

                <h3 className="text-lg font-semibold mt-6 mb-3">Usage Statistics</h3>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div className="bg-blue-50 p-3 rounded">
                    <div className="text-2xl font-bold text-blue-700">{report.total_usage_hours}</div>
                    <div className="text-gray-500">Total Hours</div>
                  </div>
                  <div className="bg-green-50 p-3 rounded">
                    <div className="text-2xl font-bold text-green-700">{report.avg_daily_usage_minutes}</div>
                    <div className="text-gray-500">Avg Daily Min</div>
                  </div>
                  <div className="bg-purple-50 p-3 rounded">
                    <div className="text-2xl font-bold text-purple-700">{report.total_sessions}</div>
                    <div className="text-gray-500">Total Sessions</div>
                  </div>
                  <div className="bg-indigo-50 p-3 rounded">
                    <div className="text-2xl font-bold text-indigo-700">{report.total_movements}</div>
                    <div className="text-gray-500">Total Movements</div>
                  </div>
                  <div className="bg-yellow-50 p-3 rounded">
                    <div className="text-2xl font-bold text-yellow-700">{report.avg_movements_per_session}</div>
                    <div className="text-gray-500">Movements/Session</div>
                  </div>
                  <div className="bg-red-50 p-3 rounded">
                    <div className="text-2xl font-bold text-red-700">{report.total_errors}</div>
                    <div className="text-gray-500">Total Errors</div>
                  </div>
                  <div className="bg-pink-50 p-3 rounded">
                    <div className="text-2xl font-bold text-pink-700">{report.errors_per_session}</div>
                    <div className="text-gray-500">Errors/Session</div>
                  </div>
                  <div className="bg-teal-50 p-3 rounded">
                    <div className="text-2xl font-bold text-teal-700">{report.battery_health_avg}</div>
                    <div className="text-gray-500">Battery Drain</div>
                  </div>
                  <div className="bg-gray-50 p-3 rounded">
                    <div className="text-sm font-medium">{report.most_common_movement}</div>
                    <div className="text-gray-500">Most Common Movement</div>
                  </div>
                </div>

                <div className="mt-4 text-xs text-gray-400">
                  Last active: {report.last_active_date || '—'} | Data as of: {report.data_as_of_date || '—'}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
