import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

type DailyTelemetry = {
  event_date: string;
  prosthesis_id: string;
  events: number;
  err_events: number;
  avg_response_ms: number;
  p95_response_ms: number;
  avg_battery_level: number;
};

type UserReport = {
  customer_id: string;
  full_name: string;
  country: string;
  days: DailyTelemetry[];
};

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<UserReport | null>(null);

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      setReport(null);
      return;
    }

    try {
      setLoading(true);
      setError(null);

      await keycloak.updateToken(30);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        let message = `Request failed with status ${response.status}`;
        try {
          const body = await response.json();
          if (body && typeof body.detail === 'string') {
            message += `: ${body.detail}`;
          }
        } catch {
        }
        throw new Error(message);
      }

      const data = await response.json() as UserReport;
      setReport(data);
    } catch (err) {
      setReport(null);
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    return <div>Loading...</div>;
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
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md max-w-3xl w-full">
          <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

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
                <h2 className="text-xl font-semibold mb-2">
                  Report for {report.full_name} ({report.country}) - customer {report.customer_id}
                </h2>

                <table className="min-w-full text-sm border border-gray-200">
                  <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 border border-gray-200 text-left">Date</th>
                    <th className="px-3 py-2 border border-gray-200 text-left">Prosthesis</th>
                    <th className="px-3 py-2 border border-gray-200 text-right">Events</th>
                    <th className="px-3 py-2 border border-gray-200 text-right">Errors</th>
                    <th className="px-3 py-2 border border-gray-200 text-right">Avg, ms</th>
                    <th className="px-3 py-2 border border-gray-200 text-right">P95, ms</th>
                    <th className="px-3 py-2 border border-gray-200 text-right">Battery, %</th>
                  </tr>
                  </thead>
                  <tbody>
                  {report.days.map((day) => (
                      <tr key={`${day.event_date}-${day.prosthesis_id}`}>
                        <td className="px-3 py-2 border border-gray-200">
                          {day.event_date}
                        </td>
                        <td className="px-3 py-2 border border-gray-200">
                          {day.prosthesis_id}
                        </td>
                        <td className="px-3 py-2 border border-gray-200 text-right">
                          {day.events}
                        </td>
                        <td className="px-3 py-2 border border-gray-200 text-right">
                          {day.err_events}
                        </td>
                        <td className="px-3 py-2 border border-gray-200 text-right">
                          {day.avg_response_ms.toFixed(1)}
                        </td>
                        <td className="px-3 py-2 border border-gray-200 text-right">
                          {day.p95_response_ms.toFixed(1)}
                        </td>
                        <td className="px-3 py-2 border border-gray-200 text-right">
                          {day.avg_battery_level.toFixed(1)}
                        </td>
                      </tr>
                  ))}
                  </tbody>
                </table>

                <pre className="mt-4 text-xs bg-gray-50 p-4 rounded whitespace-pre-wrap">
              {JSON.stringify(report, null, 2)}
            </pre>
              </div>
          )}
        </div>
      </div>
  );
};

export default ReportPage;
