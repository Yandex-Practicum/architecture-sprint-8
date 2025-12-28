import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

// Типы данных
interface ReportData {
  user_id: string;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  prosthetic_model: string;
  report_date: string;
  total_usage_hours: number;
  movement_count: number;
  avg_response_time_ms: number;
  battery_cycles: number;
  calibration_count: number;
  last_sync_at: string;
  etl_processed_at: string;
}

interface ReportResponse {
  success: boolean;
  user_id: string;
  reports: ReportData[];
  total_count: number;
  message?: string;
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportResponse | null>(null);
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  const fetchReport = async () => {
    if (!keycloak?.token) {
      setError('Необходима аутентификация');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReportData(null);

      // Формирование URL с параметрами
      const params = new URLSearchParams();
      if (dateFrom) params.append('date_from', dateFrom);
      if (dateTo) params.append('date_to', dateTo);
      
      const queryString = params.toString();
      const url = `${process.env.REACT_APP_API_URL}/reports${queryString ? `?${queryString}` : ''}`;

      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('Сессия истекла. Пожалуйста, войдите снова.');
        }
        throw new Error(`Ошибка сервера: ${response.status}`);
      }

      const data: ReportResponse = await response.json();
      setReportData(data);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
    } finally {
      setLoading(false);
    }
  };

  const downloadAsJson = () => {
    if (!reportData) return;
    
    const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report_${reportData.user_id}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (!initialized) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <div className="text-lg text-gray-600">Загрузка...</div>
      </div>
    );
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md text-center">
          <h1 className="text-2xl font-bold mb-4">BionicPRO Reports</h1>
          <p className="text-gray-600 mb-6">Войдите для просмотра отчётов о работе вашего протеза</p>
          <button
            onClick={() => keycloak.login()}
            className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition-colors"
          >
            Войти
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 py-8">
      <div className="max-w-4xl mx-auto px-4">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-2xl font-bold text-gray-800">Отчёты о работе протеза</h1>
              <p className="text-gray-600 mt-1">
                Пользователь: {keycloak.tokenParsed?.preferred_username}
              </p>
            </div>
            <button
              onClick={() => keycloak.logout()}
              className="px-4 py-2 text-gray-600 hover:text-gray-800 border border-gray-300 rounded hover:bg-gray-50"
            >
              Выйти
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <h2 className="text-lg font-semibold mb-4">Фильтры</h2>
          <div className="flex flex-wrap gap-4 items-end">
            <div>
              <label className="block text-sm text-gray-600 mb-1">Дата с</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">Дата по</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button
              onClick={fetchReport}
              disabled={loading}
              className={`px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors ${
                loading ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {loading ? 'Загрузка...' : 'Получить отчёт'}
            </button>
            {reportData && reportData.reports.length > 0 && (
              <button
                onClick={downloadAsJson}
                className="px-6 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors"
              >
                Скачать JSON
              </button>
            )}
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
            {error}
          </div>
        )}

        {/* Results */}
        {reportData && (
          <div className="bg-white rounded-lg shadow-md p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-lg font-semibold">
                Результаты ({reportData.total_count} записей)
              </h2>
              {reportData.message && (
                <span className="text-sm text-gray-500">{reportData.message}</span>
              )}
            </div>

            {reportData.reports.length === 0 ? (
              <p className="text-gray-600 text-center py-8">
                Нет данных за выбранный период
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Дата</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Модель</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Часы работы</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Движения</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Время отклика</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Циклы батареи</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Калибровки</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {reportData.reports.map((report, index) => (
                      <tr key={index} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{report.report_date}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{report.prosthetic_model}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{report.total_usage_hours.toFixed(1)} ч</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{report.movement_count.toLocaleString()}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{report.avg_response_time_ms.toFixed(1)} мс</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{report.battery_cycles}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{report.calibration_count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Initial State */}
        {!reportData && !loading && !error && (
          <div className="bg-white rounded-lg shadow-md p-8 text-center">
            <p className="text-gray-600">
              Нажмите "Получить отчёт" для загрузки данных о работе вашего протеза
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
