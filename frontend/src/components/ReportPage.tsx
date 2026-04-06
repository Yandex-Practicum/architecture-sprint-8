import React, { useState, useEffect } from 'react';

const AUTH_SERVICE_URL = process.env.REACT_APP_AUTH_SERVICE_URL || 'http://127.0.0.1:5000';
const REPORTS_API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

interface ProstheticReport {
  buyer_id: number;
  full_name: string;
  email: string;
  prosthetic_type: string;
  serial_number: string;
  total_usage_hours: number;
  total_movements: number;
  total_errors: number;
  avg_battery_level: number;
  last_telemetry_date: string;
  report_period_start: string;
  report_period_end: string;
}

interface ReportApiResponse {
  reports: ProstheticReport[];
  cdn_url: string;
  generated_at: string;
  cached: boolean;
  cache_key: string;
}

const ReportPage: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [reports, setReports] = useState<ProstheticReport[]>([]);
  const [showReports, setShowReports] = useState(false);
  const [reportMeta, setReportMeta] = useState<{ cached: boolean; cdn_url: string } | null>(null);

  useEffect(() => {
    checkSession();
  }, []);

  const checkSession = async () => {
    try {
      const response = await fetch(`${AUTH_SERVICE_URL}/auth/user`, {
        credentials: 'include'
      });

      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        setUser(null);
      }
    } catch (err) {
      console.error('Session check failed:', err);
      setUser(null);
    } finally {
      setLoading(false);
    }
  };

  const handleLogin = () => {
    window.location.href = `${AUTH_SERVICE_URL}/auth/login`;
  };

  const handleLogout = async () => {
    try {
      await fetch(`${AUTH_SERVICE_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include'
      });
      setUser(null);
      setReports([]);
      setShowReports(false);
      setReportMeta(null);
    } catch (err) {
      setError('Logout failed');
    }
  };

  const fetchReports = async () => {
    try {
      setReportLoading(true);
      setError(null);

      const tokenResponse = await fetch(`${AUTH_SERVICE_URL}/auth/token`, {
        credentials: 'include'
      });

      if (!tokenResponse.ok) {
        throw new Error('Failed to get access token');
      }

      const { access_token } = await tokenResponse.json();

      const response = await fetch(`${REPORTS_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${access_token}`
        }
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => null);
        throw new Error(errorData?.detail || 'Failed to fetch reports');
      }

      const body = await response.json();
      const data = body as ReportApiResponse | ProstheticReport[];
      if (Array.isArray(data)) {
        setReports(data);
        setReportMeta(null);
      } else {
        setReports(data.reports ?? []);
        setReportMeta({
          cached: data.cached,
          cdn_url: data.cdn_url,
        });
      }
      setShowReports(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
      setReports([]);
      setReportMeta(null);
    } finally {
      setReportLoading(false);
    }
  };

  const downloadReportAsJSON = () => {
    if (reports.length === 0) return;

    const dataStr = JSON.stringify(reports, null, 2);
    const dataUri = 'data:application/json;charset=utf-8,'+ encodeURIComponent(dataStr);
    
    const exportFileDefaultName = `bionicpro-report-${new Date().toISOString().split('T')[0]}.json`;
    
    const linkElement = document.createElement('a');
    linkElement.setAttribute('href', dataUri);
    linkElement.setAttribute('download', exportFileDefaultName);
    linkElement.click();
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div>Loading...</div>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">BionicPRO Authentication</h1>
          <p className="mb-4 text-gray-600">Please login to access your reports</p>
          <button
            onClick={handleLogin}
            className="px-6 py-3 bg-blue-500 text-white rounded hover:bg-blue-600 transition"
          >
            Login with Keycloak
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4">
      <div className="p-8 bg-white rounded-lg shadow-md max-w-4xl w-full">
        <div className="mb-6">
          <h1 className="text-2xl font-bold mb-2">Отчеты о работе протезов</h1>
          <div className="text-sm text-gray-600">
            <p>Добро пожаловать, {user.preferred_username || user.name}!</p>
            <p className="text-xs mt-1">{user.email}</p>
          </div>
        </div>

        <div className="space-y-3 mb-6">
          <button
            onClick={fetchReports}
            disabled={reportLoading}
            className={`w-full px-4 py-3 bg-blue-500 text-white rounded hover:bg-blue-600 transition ${
              reportLoading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {reportLoading ? 'Загрузка отчетов...' : 'Получить отчеты'}
          </button>

          {reports.length > 0 && (
            <button
              onClick={downloadReportAsJSON}
              className="w-full px-4 py-3 bg-green-500 text-white rounded hover:bg-green-600 transition"
            >
              Скачать отчеты (JSON)
            </button>
          )}

          <button
            onClick={handleLogout}
            className="w-full px-4 py-3 bg-gray-500 text-white rounded hover:bg-gray-600 transition"
          >
            Выйти
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded text-sm">
            {error}
          </div>
        )}

        {reportMeta && (
          <div className="mt-4 p-3 bg-slate-100 text-slate-700 rounded text-sm">
            <p>
              Источник:{' '}
              {reportMeta.cached
                ? 'кеш S3 (ClickHouse не запрашивался)'
                : 'сгенерировано из ClickHouse и записано в S3'}
            </p>
            <p className="text-xs mt-1 break-all">
              CDN: <a className="text-blue-600 underline" href={reportMeta.cdn_url} target="_blank" rel="noreferrer">{reportMeta.cdn_url}</a>
            </p>
          </div>
        )}

        {showReports && reports.length === 0 && !reportLoading && (
          <div className="mt-4 p-4 bg-yellow-100 text-yellow-700 rounded text-sm">
            Отчеты не найдены. Возможно, данные еще не обработаны системой аналитики.
          </div>
        )}

        {reports.length > 0 && (
          <div className="mt-6">
            <h2 className="text-xl font-semibold mb-4">Ваши отчеты</h2>
            <div className="space-y-4">
              {reports.map((report, index) => (
                <div key={index} className="border rounded-lg p-4 bg-gray-50">
                  <div className="flex justify-between items-start mb-3">
                    <div>
                      <h3 className="font-semibold text-lg">{report.prosthetic_type}</h3>
                      <p className="text-sm text-gray-600">S/N: {report.serial_number}</p>
                    </div>
                    <div className="text-right text-sm text-gray-600">
                      <p>Период:</p>
                      <p className="font-mono">
                        {new Date(report.report_period_start).toLocaleDateString()} - 
                        {new Date(report.report_period_end).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3">
                    <div className="bg-white p-3 rounded shadow-sm">
                      <p className="text-xs text-gray-500 mb-1">Часы использования</p>
                      <p className="text-lg font-semibold text-blue-600">
                        {report.total_usage_hours.toFixed(1)}ч
                      </p>
                    </div>

                    <div className="bg-white p-3 rounded shadow-sm">
                      <p className="text-xs text-gray-500 mb-1">Движений</p>
                      <p className="text-lg font-semibold text-green-600">
                        {report.total_movements.toLocaleString()}
                      </p>
                    </div>

                    <div className="bg-white p-3 rounded shadow-sm">
                      <p className="text-xs text-gray-500 mb-1">Ошибок</p>
                      <p className="text-lg font-semibold text-red-600">
                        {report.total_errors}
                      </p>
                    </div>

                    <div className="bg-white p-3 rounded shadow-sm">
                      <p className="text-xs text-gray-500 mb-1">Средний заряд</p>
                      <p className="text-lg font-semibold text-purple-600">
                        {report.avg_battery_level.toFixed(1)}%
                      </p>
                    </div>
                  </div>

                  <div className="mt-3 text-xs text-gray-500">
                    Последние данные: {new Date(report.last_telemetry_date).toLocaleString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="mt-6 text-xs text-gray-500 border-t pt-4">
          <p className="font-semibold mb-2">Меры безопасности:</p>
          <ul className="list-disc list-inside space-y-1">
            <li>PKCE-защищенная аутентификация</li>
            <li>HTTP-only secure session cookies</li>
            <li>Токены не передаются на фронтенд</li>
            <li>Автоматическое обновление токенов</li>
            <li>Ротация сессий</li>
            <li>Доступ только к собственным отчетам</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default ReportPage;