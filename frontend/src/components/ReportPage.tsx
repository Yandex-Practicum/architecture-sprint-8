import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

type ReportData = {
  user_id: string;
  full_name: string;
  email: string;
  avg_battery_level: number;
  avg_active_minutes: number;
  total_events: number;
};

const getDefaultDateValue = (daysOffset: number): string => {
  const value = new Date();
  value.setDate(value.getDate() + daysOffset);
  return value.toISOString().slice(0, 10);
};

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [startDate, setStartDate] = useState(getDefaultDateValue(-7));
  const [endDate, setEndDate] = useState(getDefaultDateValue(-1));

  const saveJsonToFile = (data: ReportData) => {
    const fileName = `report_${startDate}_${endDate}.json`;
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();

    window.URL.revokeObjectURL(url);
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

      const params = new URLSearchParams({
        start_date: startDate,
        end_date: endDate
      });

      const response = await fetch(
        `${process.env.REACT_APP_API_URL}/reports?${params.toString()}`,
        {
          headers: {
            Authorization: `Bearer ${keycloak.token}`
          }
        }
      );

      const payload = await response.json().catch(() => null);

      if (!response.ok) {
        const message = payload?.detail || 'Failed to generate report';
        throw new Error(message);
      }

      const report = payload as ReportData;
      setReportData(report);
      saveJsonToFile(report);
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
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <div className="flex flex-col gap-4 mb-6">
          <div>
            <label className="block mb-1 font-medium">Start date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-3 py-2 border rounded"
            />
          </div>

          <div>
            <label className="block mb-1 font-medium">End date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-3 py-2 border rounded"
            />
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

        {reportData && (
          <div className="mt-6 p-4 bg-gray-50 rounded border">
            <h2 className="text-lg font-semibold mb-3">Last report</h2>
            <pre className="text-sm whitespace-pre-wrap">
              {JSON.stringify(reportData, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;