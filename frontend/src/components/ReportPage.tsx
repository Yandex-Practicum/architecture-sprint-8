import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface Report {
  user_id: string;
  processed_up_to: string | null;
  rows: unknown[];
}

const saveReport = (report: Report) => {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
  );
  const link = document.createElement('a');
  link.href = url;
  link.download = `report-${report.user_id}-${report.processed_up_to}.json`;
  link.click();
  URL.revokeObjectURL(url);
};

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReport(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (response.status === 401) {
        setError('Your session has expired, please log in again');
        return;
      }
      if (response.status === 403) {
        setError('Your account has no access to prosthesis reports');
        return;
      }
      if (!response.ok) {
        throw new Error(`Report request failed with status ${response.status}`);
      }

      const report: Report = await response.json();
      setReport(report);

      if (report.rows.length > 0) {
        saveReport(report);
      }
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

        {report && report.rows.length === 0 && (
          <div className="mt-4 p-4 bg-yellow-100 text-yellow-800 rounded">
            {report.processed_up_to
              ? `No data for the requested period: Airflow has processed data up to ${report.processed_up_to}`
              : 'The report is not ready yet: Airflow has not loaded any data into OLAP'}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;