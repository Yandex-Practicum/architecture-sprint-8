import React, { useState, useEffect } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface Report {
  user_id: string;
  prosthetic_id: string;
  report_date: string;
  total_usage_minutes: number;
  avg_response_time_ms: number;
  battery_cycles: number;
  movements_count: number;
  successful_movements: number;
  failed_movements: number;
  calibration_count: number;
  data_volume_mb: number;
}

interface ReportListResponse {
  user_id: string;
  reports: Report[];
  total_days: number;
  generated_at: string;
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [reports, setReports] = useState<Report[]>([]);
  const [dateRange, setDateRange] = useState({
    startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
    endDate: new Date().toISOString().split('T')[0]
  });

  const userId = keycloak?.tokenParsed?.sub || keycloak?.tokenParsed?.preferred_username;

  const fetchReports = async (): Promise<void> => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    if (!userId) {
      setError('User ID not found in token');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      // Формируем URL с параметрами дат
      const url = new URL(`${process.env.REACT_APP_REPORT_SERVICE_URL || 'http://localhost:8001'}/reports/${userId}`);
      url.searchParams.append('start_date', dateRange.startDate);
      url.searchParams.append('end_date', dateRange.endDate);

      const response = await fetch(url.toString(), {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Access denied: You can only view your own reports');
        }
        if (response.status === 401) {
          // Токен истек, пробуем обновить
          await keycloak.updateToken(30);
          // Повторяем запрос
          return fetchReports();
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: ReportListResponse = await response.json();
      setReports(data.reports);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      console.error('Error fetching reports:', err);
    } finally {
      setLoading(false);
    }
  };

  const downloadCSV = (): void => {
    if (reports.length === 0) return;

    // Создаем CSV
    const headers = ['Date', 'Usage (min)', 'Avg Response (ms)', 'Movements', 'Success Rate %', 'Calibrations'];
    const rows = reports.map(r => [
      r.report_date,
      r.total_usage_minutes.toFixed(1),
      r.avg_response_time_ms.toFixed(2),
      r.movements_count.toString(),
      ((r.successful_movements / r.movements_count) * 100).toFixed(1),
      r.calibration_count.toString()
    ]);

    const csv = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');

    // Скачиваем
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report_${userId}_${dateRange.startDate}_${dateRange.endDate}.csv`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (!initialized) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl">Loading...</div>
      </div>
    );
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <h1 className="text-2xl font-bold mb-6">BionicPRO Reports</h1>
        <p className="mb-4">Please log in to access your reports</p>
        <button
          onClick={() => keycloak.login()}
          className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
        >
          Login with Keycloak
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16 items-center">
            <h1 className="text-xl font-semibold text-gray-900">BionicPRO Reports</h1>
            <div className="flex items-center space-x-4">
              <span className="text-sm text-gray-600">
                {keycloak.tokenParsed?.preferred_username || keycloak.tokenParsed?.email}
              </span>
              <button
                onClick={() => keycloak.logout()}
                className="px-3 py-2 text-sm text-gray-700 hover:text-gray-900"
              >
                Logout
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <div className="px-4 py-6 sm:px-0">
          <div className="bg-white rounded-lg shadow p-6">
            {/* Фильтры по дате */}
            <div className="mb-6 flex flex-wrap items-end gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Start Date
                </label>
                <input
                  type="date"
                  value={dateRange.startDate}
                  onChange={(e) => setDateRange({ ...dateRange, startDate: e.target.value })}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  End Date
                </label>
                <input
                  type="date"
                  value={dateRange.endDate}
                  onChange={(e) => setDateRange({ ...dateRange, endDate: e.target.value })}
                  className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
              </div>
              <button
                onClick={fetchReports}
                disabled={loading}
                className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
              >
                {loading ? 'Loading...' : 'Load Reports'}
              </button>
              {reports.length > 0 && (
                <button
                  onClick={downloadCSV}
                  className="px-4 py-2 bg-green-500 text-white rounded-md hover:bg-green-600 focus:outline-none focus:ring-2 focus:ring-green-500"
                >
                  Download CSV
                </button>
              )}
            </div>

            {/* Ошибки */}
            {error && (
              <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded-md">
                {error}
              </div>
            )}

            {/* Таблица отчётов */}
            {reports.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Usage (min)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Avg Response (ms)</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Movements</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Success Rate</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Calibrations</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Data (MB)</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {reports.map((report) => (
                      <tr key={report.report_date} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {new Date(report.report_date).toLocaleDateString()}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {report.total_usage_minutes.toFixed(1)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {report.avg_response_time_ms.toFixed(2)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {report.movements_count}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm">
                          <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                            (report.successful_movements / report.movements_count) > 0.9
                              ? 'bg-green-100 text-green-800'
                              : (report.successful_movements / report.movements_count) > 0.7
                              ? 'bg-yellow-100 text-yellow-800'
                              : 'bg-red-100 text-red-800'
                          }`}>
                            {((report.successful_movements / report.movements_count) * 100).toFixed(1)}%
                          </span>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {report.calibration_count}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {report.data_volume_mb.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              !loading && !error && (
                <div className="text-center py-12 text-gray-500">
                  No reports found for the selected period.
                  <button
                    onClick={fetchReports}
                    className="ml-2 text-blue-500 hover:text-blue-600 underline"
                  >
                    Try again
                  </button>
                </div>
              )
            )}
          </div>
        </div>
      </main>
    </div>
  );
};

export default ReportPage;