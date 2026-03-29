import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

type ReportItem = {
  keycloak_username: string;
  full_name: string;
  email: string;
  country_code: string;
  prosthesis_code: string;
  model_name: string;
  activated_at: string;
  telemetry_from: string;
  telemetry_to: string;
  total_events: number;
  total_active_minutes: number;
  total_grip_actions: number;
  avg_signal: number;
  avg_battery_level: number;
  report_generated_at: string;
};

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reports, setReports] = useState<ReportItem[]>([]);

  const downloadJson = (data: ReportItem[]) => {
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'bionicpro-report.json';
    link.click();
    URL.revokeObjectURL(url);
  };

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await keycloak.updateToken(30);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (!response.ok) {
        throw new Error(`Failed to download report: ${response.status}`);
      }

      const payload = await response.json();
      const reportItems = payload.reports ?? [];
      setReports(reportItems);
      downloadJson(reportItems);
    } catch (err) {
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
          onClick={() => keycloak.login({ redirectUri: `${window.location.origin}/` })}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="w-full max-w-5xl p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-2">Usage Reports</h1>
        <p className="mb-6 text-sm text-gray-600">
          Signed in as <span className="font-medium">{keycloak.tokenParsed?.preferred_username as string}</span>
        </p>
        
        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition ${
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

        {reports.length > 0 && (
          <div className="mt-8 space-y-4">
            {reports.map((report) => (
              <div key={report.prosthesis_code} className="border rounded-lg p-5 bg-slate-50">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h2 className="text-lg font-semibold">{report.full_name}</h2>
                    <p className="text-sm text-gray-600">
                      {report.model_name} / {report.prosthesis_code}
                    </p>
                  </div>
                  <div className="text-sm text-gray-500">
                    Generated: {new Date(report.report_generated_at).toLocaleString()}
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-sm">
                  <div className="p-3 bg-white rounded border">
                    <div className="font-medium">Telemetry period</div>
                    <div>{new Date(report.telemetry_from).toLocaleString()} - {new Date(report.telemetry_to).toLocaleString()}</div>
                  </div>
                  <div className="p-3 bg-white rounded border">
                    <div className="font-medium">Customer</div>
                    <div>{report.email} / {report.country_code}</div>
                  </div>
                  <div className="p-3 bg-white rounded border">
                    <div className="font-medium">Total events</div>
                    <div>{report.total_events}</div>
                  </div>
                  <div className="p-3 bg-white rounded border">
                    <div className="font-medium">Active minutes</div>
                    <div>{report.total_active_minutes}</div>
                  </div>
                  <div className="p-3 bg-white rounded border">
                    <div className="font-medium">Grip actions</div>
                    <div>{report.total_grip_actions}</div>
                  </div>
                  <div className="p-3 bg-white rounded border">
                    <div className="font-medium">Average battery level</div>
                    <div>{report.avg_battery_level.toFixed(2)}%</div>
                  </div>
                  <div className="p-3 bg-white rounded border">
                    <div className="font-medium">Average signal</div>
                    <div>{report.avg_signal.toFixed(3)}</div>
                  </div>
                  <div className="p-3 bg-white rounded border">
                    <div className="font-medium">Activated at</div>
                    <div>{new Date(report.activated_at).toLocaleDateString()}</div>
                  </div>
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
