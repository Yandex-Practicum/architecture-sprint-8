import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportData {
  date: string;
  device_id: string;
  total_usage_seconds: number;
  total_movements: number;
  avg_sensor_value: number;
  min_sensor_value: number;
  max_sensor_value: number;
  usage_hours: number;
  user_name?: string;
  prosthesis_type?: string;
}

interface ReportResponse {
  user_id: number;
  date_from: string;
  date_to: string;
  data: ReportData[];
  summary: {
    total_usage_seconds: number;
    total_movements: number;
    avg_sensor_value: number;
    min_sensor_value: number;
    max_sensor_value: number;
    total_usage_hours: number;
    days_count: number;
  };
  last_processed_date?: string;
  last_processed_time?: string;
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportResponse | null>(null);
  
  // Значения по умолчанию: последний месяц
  const today = new Date();
  const lastMonth = new Date(today);
  lastMonth.setMonth(today.getMonth() - 1);
  
  const [dateFrom, setDateFrom] = useState(
    lastMonth.toISOString().split('T')[0]
  );
  const [dateTo, setDateTo] = useState(
    today.toISOString().split('T')[0]
  );

  const getReport = async () => {
    if (!keycloak?.token) {
      setError('Необходима авторизация. Пожалуйста, войдите в систему.');
      return;
    }

    // Валидация дат
    if (!dateFrom || !dateTo) {
      setError('Пожалуйста, выберите начальную и конечную даты');
      return;
    }

    if (new Date(dateFrom) > new Date(dateTo)) {
      setError('Начальная дата не может быть больше конечной');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReport(null);

      const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';
      const url = `${apiUrl}/reports?date_from=${dateFrom}&date_to=${dateTo}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        
        if (response.status === 401) {
          setError('Ошибка авторизации. Пожалуйста, войдите в систему снова.');
          keycloak.logout();
          return;
        }
        
        if (response.status === 403) {
          setError('Доступ запрещён. Вы можете запрашивать только свои отчёты.');
          return;
        }
        
        if (response.status === 404) {
          const detail = errorData.detail || errorData;
          if (typeof detail === 'object' && detail.message) {
            setError(
              `${detail.message}. ${
                detail.last_available_date 
                  ? `Последняя доступная дата: ${detail.last_available_date}` 
                  : ''
              }`
            );
          } else {
            setError('Данные за указанный период ещё не обработаны');
          }
          return;
        }
        
        setError(errorData.detail || errorData.message || `Ошибка: ${response.statusText}`);
        return;
      }

      const data: ReportResponse = await response.json();
      setReport(data);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка при получении отчёта');
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
    <div className="min-h-screen bg-gray-100 py-8 px-4">
      <div className="max-w-6xl mx-auto">
        <div className="bg-white rounded-lg shadow-md p-8">
          <h1 className="text-3xl font-bold mb-6 text-gray-800">Отчёты о работе протеза</h1>
          
          {/* Форма выбора дат */}
          <div className="mb-6 grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label htmlFor="dateFrom" className="block text-sm font-medium text-gray-700 mb-2">
                Начальная дата
              </label>
              <input
                id="dateFrom"
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={loading}
              />
            </div>
            
            <div>
              <label htmlFor="dateTo" className="block text-sm font-medium text-gray-700 mb-2">
                Конечная дата
              </label>
              <input
                id="dateTo"
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                disabled={loading}
              />
            </div>
            
            <div className="flex items-end">
              <button
                onClick={getReport}
                disabled={loading}
                className={`w-full px-6 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 transition-colors ${
                  loading ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                {loading ? 'Загрузка...' : 'Получить отчёт'}
              </button>
            </div>
          </div>

          {/* Сообщение об ошибке */}
          {error && (
            <div className="mb-6 p-4 bg-red-50 border border-red-200 text-red-700 rounded-md">
              <p className="font-medium">Ошибка</p>
              <p>{error}</p>
            </div>
          )}

          {/* Отображение отчёта */}
          {report && (
            <div className="mt-6">
              <h2 className="text-2xl font-semibold mb-4 text-gray-800">
                Отчёт за период: {new Date(report.date_from).toLocaleDateString('ru-RU')} - {new Date(report.date_to).toLocaleDateString('ru-RU')}
              </h2>
              
              {/* Сводная статистика */}
              <div className="mb-6 p-4 bg-blue-50 rounded-md">
                <h3 className="text-lg font-semibold mb-3 text-gray-800">Сводная статистика</h3>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                  <div>
                    <p className="text-sm text-gray-600">Общее время использования</p>
                    <p className="text-xl font-bold">{Math.round(report.summary.total_usage_hours * 10) / 10} часов</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Всего движений</p>
                    <p className="text-xl font-bold">{report.summary.total_movements.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Среднее значение датчика</p>
                    <p className="text-xl font-bold">{Math.round(report.summary.avg_sensor_value * 10) / 10}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Минимальное значение</p>
                    <p className="text-xl font-bold">{Math.round(report.summary.min_sensor_value * 10) / 10}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Максимальное значение</p>
                    <p className="text-xl font-bold">{Math.round(report.summary.max_sensor_value * 10) / 10}</p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Дней в отчёте</p>
                    <p className="text-xl font-bold">{report.summary.days_count}</p>
                  </div>
                </div>
              </div>

              {/* Таблица с данными */}
              {report.data.length > 0 ? (
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Дата
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Устройство
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Время использования (ч)
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Движений
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Среднее значение
                        </th>
                        <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                          Мин / Макс
                        </th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {report.data.map((row, index) => (
                        <tr key={index} className="hover:bg-gray-50">
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                            {new Date(row.date).toLocaleDateString('ru-RU')}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                            {row.device_id}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                            {Math.round(row.usage_hours * 10) / 10}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                            {row.total_movements}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                            {Math.round(row.avg_sensor_value * 10) / 10}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                            {Math.round(row.min_sensor_value * 10) / 10} / {Math.round(row.max_sensor_value * 10) / 10}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="p-4 bg-yellow-50 border border-yellow-200 text-yellow-700 rounded-md">
                  Нет данных за выбранный период
                </div>
              )}

              {/* Информация о последней обработке */}
              {report.last_processed_date && (
                <div className="mt-4 text-sm text-gray-500">
                  Последняя обработка данных: {new Date(report.last_processed_date).toLocaleDateString('ru-RU')}
                  {report.last_processed_time && ` в ${new Date(report.last_processed_time).toLocaleTimeString('ru-RU')}`}
                </div>
              )}
            </div>
          )}

          {/* Кнопка выхода */}
          <div className="mt-6 pt-6 border-t border-gray-200">
            <button
              onClick={() => keycloak.logout()}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800"
            >
              Выйти
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ReportPage;