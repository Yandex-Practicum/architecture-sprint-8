import React, { useState, useEffect } from 'react';
import { ApiService, Report, ReportData } from '../services/api.service';
import { AuthService } from '../services/auth.service';

interface ReportPageProps {
  user: any;
  onLogout: () => void;
}

const ReportPage: React.FC<ReportPageProps> = ({ user, onLogout }) => {
  const [reports, setReports] = useState<Report[]>([]);
  const [reportData, setReportData] = useState<ReportData | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoMessage, setInfoMessage] = useState<string | null>(null);

  useEffect(() => {
    loadReports();
  }, []);

  const loadReports = async () => {
    try {
      setLoading(true);
      setError(null);
      setInfoMessage(null);

      const data = await ApiService.getReports();
      setReports(data.reports);
      if (data.report_data) {
        setReportData(data.report_data);
      }
      if (data.message) {
        setInfoMessage(data.message);
      }
    } catch (err: any) {
      if (err.message === 'UNAUTHORIZED') {
        setError('Сессия истекла. Выполняется повторная авторизация...');
        setTimeout(() => {
          AuthService.login();
        }, 2000);
      } else {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить отчёты');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateReport = async () => {
    try {
      setGenerating(true);
      setError(null);
      setInfoMessage(null);

      const data = await ApiService.generateReport();
      setReportData(data.report);
      setInfoMessage('Отчёт успешно сгенерирован из OLAP базы данных.');

      // Обновляем список отчётов
      await loadReports();
    } catch (err: any) {
      if (err.message === 'UNAUTHORIZED') {
        setError('Сессия истекла. Выполняется повторная авторизация...');
        setTimeout(() => {
          AuthService.login();
        }, 2000);
      } else if (err.message === 'DATA_NOT_READY') {
        setError('Данные ещё не обработаны ETL-процессом Airflow. Попробуйте позже.');
      } else {
        setError(err instanceof Error ? err.message : 'Не удалось сгенерировать отчёт');
      }
    } finally {
      setGenerating(false);
    }
  };

  const handleDownload = async (reportId: number, reportName: string) => {
    try {
      setLoading(true);
      const blob = await ApiService.downloadReport(reportId);

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${reportName}.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError('Не удалось скачать отчёт');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8 flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              BionicPRO Reports
            </h1>
            {user && (
              <p className="text-sm text-gray-600 mt-1">
                Добро пожаловать, {user.preferred_username || user.name || 'User'}
              </p>
            )}
          </div>
          <button
            onClick={onLogout}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600 transition-colors"
          >
            Выйти
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="bg-white rounded-lg shadow-md p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-xl font-semibold text-gray-800">
              Ваши отчёты по использованию протезов
            </h2>
            <div className="flex gap-3">
              {/* Кнопка генерации отчёта — Задача 5 */}
              <button
                onClick={handleGenerateReport}
                disabled={generating || loading}
                className={`px-4 py-2 bg-indigo-600 text-white rounded hover:bg-indigo-700 transition-colors ${
                  generating || loading ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                {generating ? 'Генерация...' : 'Сгенерировать отчёт'}
              </button>
              <button
                onClick={loadReports}
                disabled={loading}
                className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors ${
                  loading ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                {loading ? 'Обновление...' : 'Обновить'}
              </button>
            </div>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
              <p className="font-medium">Ошибка</p>
              <p className="text-sm">{error}</p>
            </div>
          )}

          {/* Info Message */}
          {infoMessage && !error && (
            <div className="mb-4 p-4 bg-yellow-50 border border-yellow-300 text-yellow-800 rounded">
              <p className="text-sm">{infoMessage}</p>
            </div>
          )}

          {/* Loading State */}
          {loading && reports.length === 0 && (
            <div className="text-center py-8">
              <div className="animate-spin rounded-full h-12 w-12 border-b-4 border-blue-500 mx-auto mb-4"></div>
              <p className="text-gray-600">Загрузка отчётов...</p>
            </div>
          )}

          {/* Reports List */}
          {!loading && reports.length === 0 && !error && (
            <div className="text-center py-8 text-gray-500">
              <p>Отчёты не найдены. Нажмите "Сгенерировать отчёт" для создания отчёта из OLAP.</p>
            </div>
          )}

          {reports.length > 0 && (
            <div className="space-y-3">
              {reports.map((report) => (
                <div
                  key={report.id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div>
                    <h3 className="font-medium text-gray-900">
                      {report.name}
                    </h3>
                    <p className="text-sm text-gray-600">{report.date}</p>
                  </div>
                  <button
                    onClick={() => handleDownload(report.id, report.name)}
                    disabled={loading}
                    className={`px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 transition-colors ${
                      loading ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                  >
                    Скачать
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Generated Report Details */}
        {reportData && (
          <div className="mt-6 bg-white rounded-lg shadow-md p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">
              Детали отчёта: {reportData.customer_name}
            </h2>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
              <div className="bg-gray-50 p-3 rounded">
                <p className="text-sm text-gray-500">Email</p>
                <p className="font-medium">{reportData.email}</p>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <p className="text-sm text-gray-500">Страна</p>
                <p className="font-medium">{reportData.country}</p>
              </div>
              <div className="bg-gray-50 p-3 rounded">
                <p className="text-sm text-gray-500">Дата генерации</p>
                <p className="font-medium">
                  {new Date(reportData.report_generated_at).toLocaleString('ru-RU')}
                </p>
              </div>
            </div>

            {reportData.telemetry_summary && reportData.telemetry_summary.length > 0 && (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Тип протеза</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Мышечная группа</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Всего сигналов</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Ср. частота</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Ср. амплитуда</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Мин. амплитуда</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Макс. амплитуда</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Период данных</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {reportData.telemetry_summary.map((item, idx) => (
                      <tr key={idx} className="hover:bg-gray-50">
                        <td className="px-4 py-3 text-sm text-gray-900">{item.prosthesis_type}</td>
                        <td className="px-4 py-3 text-sm text-gray-900">{item.muscle_group}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{item.total_signals}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{item.avg_signal_frequency}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{item.avg_signal_amplitude}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{item.min_signal_amplitude}</td>
                        <td className="px-4 py-3 text-sm text-gray-900 text-right">{item.max_signal_amplitude}</td>
                        <td className="px-4 py-3 text-sm text-gray-600">
                          {item.first_signal_time} — {item.last_signal_time}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {reportData.datamart_last_updated && (
              <p className="mt-4 text-sm text-gray-500">
                Последнее обновление витрины Airflow: {reportData.datamart_last_updated}
              </p>
            )}
          </div>
        )}

        {/* Info Section */}
        <div className="mt-6 bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg
                className="h-5 w-5 text-blue-400"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <p className="text-sm text-blue-700">
                <strong>Защищённая сессия:</strong> Соединение защищено HTTP-only cookies
                с автоматическим обновлением токенов. Отчёты генерируются из OLAP-витрины,
                подготовленной ETL-процессом Airflow. Вы можете видеть только свои данные.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
};

export default ReportPage;
