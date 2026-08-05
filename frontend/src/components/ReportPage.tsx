import React, { useEffect, useState } from 'react';
import { SessionInfo, fetchSession, loginUrl, logout } from '../auth';

interface ReportData {
  username: string;
  firstName: string;
  lastName: string;
  prostheticId: string;
  country: string;
  periodStart: string;
  periodEnd: string;
  eventsCount: number;
  avgLatencyMs: number;
  avgSignalQuality: number;
}

function saveAsFile(data: ReportData): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `report-${data.username}-${data.periodStart.replace(/[: ]/g, '-')}.json`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

const ReportPage: React.FC = () => {
  const [session, setSession] = useState<SessionInfo | null | undefined>(undefined);
  const [report, setReport] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notReady, setNotReady] = useState(false);

  useEffect(() => {
    fetchSession()
      .then(setSession)
      .catch((err) => setError(err instanceof Error ? err.message : 'An error occurred'));
  }, []);

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setNotReady(false);
      setReport(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setSession(null);
        return;
      }
      if (response.status === 404) {
        setNotReady(true);
        return;
      }
      if (!response.ok) {
        throw new Error(`Report request failed: ${response.status}`);
      }

      const { reportUrl } = await response.json();
      const reportResponse = await fetch(reportUrl);
      if (!reportResponse.ok) {
        throw new Error(`Fetching report from CDN failed: ${reportResponse.status}`);
      }
      const data: ReportData = await reportResponse.json();
      setReport(data);
      saveAsFile(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (session === undefined) {
    return <div>Loading...</div>;
  }

  if (session === null) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <a
          href={loginUrl}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </a>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <button onClick={logout} className="text-sm text-gray-500 hover:text-gray-700">
            Logout
          </button>
        </div>

        <p className="mb-4 text-sm text-gray-600">Signed in as {session.username}</p>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        {notReady && (
          <div className="mt-4 p-4 bg-yellow-100 text-yellow-800 rounded">
            Отчёт ещё не готов: за этот период данные ещё не обработаны.
          </div>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {report && (
          <div className="mt-4 p-4 bg-gray-50 rounded text-sm text-gray-700 space-y-1">
            <p><strong>Протез:</strong> {report.prostheticId} ({report.country})</p>
            <p><strong>Период:</strong> {report.periodStart} — {report.periodEnd}</p>
            <p><strong>Событий:</strong> {report.eventsCount}</p>
            <p><strong>Средняя задержка:</strong> {report.avgLatencyMs.toFixed(1)} мс</p>
            <p><strong>Среднее качество сигнала:</strong> {(report.avgSignalQuality * 100).toFixed(1)}%</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
