import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportRow {
  client_name: string;
  prosthesis_id: string;
  prosthesis_model: string;
  report_date: string;
  total_movements: number;
  avg_response_time_ms: number;
  avg_signal_strength: number;
  avg_battery_level: number;
  active_minutes: number;
  anomaly_count: number;
}

interface ReportResponse {
  user: string;
  client_id: string;
  total_records: number;
  available_period: { from: string; to: string } | null;
  warning?: string;
  reports: ReportRow[];
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);

  const fetchReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || `Error ${response.status}`);
      }

      const data: ReportResponse = await response.json();
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setReport(null);
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
        <h1 className="text-2xl font-bold mb-4">BionicPRO Reports</h1>
        <button
          onClick={() => keycloak.login()}
          className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <div className="max-w-5xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Отчёты о работе протеза</h1>
          <button
            onClick={() => keycloak.logout()}
            className="px-4 py-2 bg-gray-300 text-gray-700 rounded hover:bg-gray-400"
          >
            Logout
          </button>
        </div>

        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <button
            onClick={fetchReport}
            disabled={loading}
            className={`px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Загрузка...' : 'Получить отчёт'}
          </button>

          {error && (
            <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
              {error}
            </div>
          )}
        </div>

        {report && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="mb-4 text-sm text-gray-600">
              Пользователь: <strong>{report.reports[0]?.client_name}</strong> |
              Записей: <strong>{report.total_records}</strong>
              {report.available_period && (
                <> | Данные обработаны за период: <strong>{report.available_period.from}</strong> — <strong>{report.available_period.to}</strong></>
              )}
            </div>

            {report.warning && (
              <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 text-yellow-800 rounded text-sm">
                {report.warning}
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-sm text-left">
                <thead className="bg-gray-50 text-gray-600 uppercase text-xs">
                  <tr>
                    <th className="px-4 py-3">Дата</th>
                    <th className="px-4 py-3">Протез</th>
                    <th className="px-4 py-3">Модель</th>
                    <th className="px-4 py-3">Движения</th>
                    <th className="px-4 py-3">Ср. отклик (мс)</th>
                    <th className="px-4 py-3">Ср. сигнал</th>
                    <th className="px-4 py-3">Ср. батарея %</th>
                    <th className="px-4 py-3">Мин. активности</th>
                    <th className="px-4 py-3">Аномалии</th>
                  </tr>
                </thead>
                <tbody>
                  {report.reports.map((row, i) => (
                    <tr key={i} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-3">{row.report_date}</td>
                      <td className="px-4 py-3">{row.prosthesis_id}</td>
                      <td className="px-4 py-3">{row.prosthesis_model}</td>
                      <td className="px-4 py-3">{row.total_movements}</td>
                      <td className="px-4 py-3">{row.avg_response_time_ms.toFixed(1)}</td>
                      <td className="px-4 py-3">{row.avg_signal_strength.toFixed(3)}</td>
                      <td className="px-4 py-3">{row.avg_battery_level.toFixed(1)}</td>
                      <td className="px-4 py-3">{row.active_minutes}</td>
                      <td className="px-4 py-3">
                        <span className={row.anomaly_count > 0 ? 'text-red-600 font-semibold' : ''}>
                          {row.anomaly_count}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
