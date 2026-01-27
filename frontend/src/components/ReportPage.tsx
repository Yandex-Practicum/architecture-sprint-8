import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface Report {
  user_id: string;
  username: string;
  prosthesis_id: string;
  date: string;
  total_movements: number;
  avg_reaction_time: number;
  min_reaction_time: number;
  max_reaction_time: number;
  customer_name: string;
  customer_email: string;
  order_date: string | null;
  prosthesis_type: string;
}

interface ReportResponse {
  username: string;
  last_processed_date: string | null;
  reports: Report[];
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportResponse | null>(null);

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Требуется авторизация');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReportData(null);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      if (response.status === 200) {
        const data: ReportResponse = await response.json();
        setReportData(data);
      } else if (response.status === 401) {
        setError('Требуется авторизация');
      } else if (response.status === 403) {
        setError('Доступ запрещён');
      } else if (response.status === 404) {
        setError('Данные не найдены');
      } else if (response.status === 422) {
        const errorData = await response.json();
        setError(errorData.detail || 'Данные за запрошенный период ещё не обработаны');
      } else {
        const errorData = await response.json();
        setError(errorData.detail || 'Произошла ошибка при получении отчёта');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
    } finally {
      setLoading(false);
    }
  };

  const downloadReportAsFile = () => {
    if (!reportData) return;

    const content = JSON.stringify(reportData, null, 2);
    const blob = new Blob([content], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `report_${reportData.username}_${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
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
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-4xl">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>
        
        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Загрузка отчёта...' : 'Получить отчёт'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {reportData && (
          <div className="mt-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">Отчёт для пользователя: {reportData.username}</h2>
              {reportData.last_processed_date && (
                <p className="text-sm text-gray-600">
                  Последняя обработанная дата: {reportData.last_processed_date}
                </p>
              )}
              <button
                onClick={downloadReportAsFile}
                className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
              >
                Скачать JSON
              </button>
            </div>
            
            <div className="overflow-x-auto">
              <table className="min-w-full border-collapse border border-gray-300">
                <thead>
                  <tr className="bg-gray-200">
                    <th className="border border-gray-300 px-4 py-2">Дата</th>
                    <th className="border border-gray-300 px-4 py-2">ID протеза</th>
                    <th className="border border-gray-300 px-4 py-2">Всего движений</th>
                    <th className="border border-gray-300 px-4 py-2">Среднее время реакции (мс)</th>
                    <th className="border border-gray-300 px-4 py-2">Мин. время (мс)</th>
                    <th className="border border-gray-300 px-4 py-2">Макс. время (мс)</th>
                    <th className="border border-gray-300 px-4 py-2">Тип протеза</th>
                  </tr>
                </thead>
                <tbody>
                  {reportData.reports.map((report, index) => (
                    <tr key={index} className="hover:bg-gray-50">
                      <td className="border border-gray-300 px-4 py-2">{report.date}</td>
                      <td className="border border-gray-300 px-4 py-2">{report.prosthesis_id}</td>
                      <td className="border border-gray-300 px-4 py-2">{report.total_movements}</td>
                      <td className="border border-gray-300 px-4 py-2">{report.avg_reaction_time.toFixed(2)}</td>
                      <td className="border border-gray-300 px-4 py-2">{report.min_reaction_time.toFixed(2)}</td>
                      <td className="border border-gray-300 px-4 py-2">{report.max_reaction_time.toFixed(2)}</td>
                      <td className="border border-gray-300 px-4 py-2">{report.prosthesis_type || '-'}</td>
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