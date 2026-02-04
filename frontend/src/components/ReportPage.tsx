import React, { useState, useEffect } from 'react';
import { useKeycloak } from '@react-keycloak/web';

const INIT_LOADING_TIMEOUT_MS = 5000;

// Только origin (без пути), чтобы всегда получался корректный /api/reports/me
const API_ORIGIN = (process.env.REACT_APP_API_URL || 'http://localhost:8000')
  .replace(/\/api\/reports.*$/, '')
  .replace(/\/$/, '');

/** Ответ API отчёта (поля витрины OLAP) */
interface ReportData {
  userId?: string;
  deviceId?: string;
  customerName?: string;
  customerEmail?: string;
  contractDate?: string;
  prosthesisModel?: string;
  deliveryDate?: string;
  sessionCount?: number;
  totalUsageSeconds?: number;
  totalUsageMinutes?: number;
  eventCount?: number;
  errorCount?: number;
  calibrationCount?: number;
  periodStart?: string;
  periodEnd?: string;
  lastActivityUtc?: string;
  updatedAt?: string;
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);
  const [initTimedOut, setInitTimedOut] = useState(false);

  useEffect(() => {
    if (initialized) {
      setInitTimedOut(false);
      return;
    }
    const t = setTimeout(() => setInitTimedOut(true), INIT_LOADING_TIMEOUT_MS);
    return () => clearTimeout(t);
  }, [initialized]);

  const getReport = async () => {
    if (!keycloak?.token) {
      setError('Необходима авторизация');
      return;
    }

    const doFetch = async (token: string) => {
      const url = `${API_ORIGIN}/api/reports/me`;
      return fetch(url, {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });
    };

    try {
      setLoading(true);
      setError(null);
      setReport(null);

      let response = await doFetch(keycloak.token);
      if ((response.status === 401 || response.status === 403) && keycloak.updateToken) {
        try {
          await keycloak.updateToken(30);
          if (keycloak.token) response = await doFetch(keycloak.token);
        } catch {
          // ignore refresh error
        }
      }

      if (!response.ok) {
        if (response.status === 401) setError('Требуется авторизация');
        else if (response.status === 403) setError('Доступ запрещён (403). Выйдите и войдите снова (user1 / password123), затем обновите страницу (Ctrl+F5).');
        else if (response.status === 404) setError('Отчёт по вашему пользователю пока не сформирован');
        else setError(`Ошибка ${response.status}`);
        return;
      }

      const data: ReportData = await response.json();
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка запроса');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    if (initTimedOut) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-6 text-center">
          <p className="text-lg text-gray-700 mb-2">Сервер авторизации не отвечает</p>
          <p className="text-sm text-gray-500 mb-4">
            Запустите Keycloak: <code className="bg-gray-200 px-1 rounded">docker-compose up -d keycloak</code>
          </p>
          <p className="text-sm text-gray-500 mb-4">URL: http://localhost:8080 (realm: reports-realm)</p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Повторить
          </button>
        </div>
      );
    }
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        <p className="text-gray-600">Загрузка…</p>
      </div>
    );
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
      <div className="p-8 bg-white rounded-lg shadow-md max-w-2xl w-full">
        <h1 className="text-2xl font-bold mb-6">Отчёты по использованию протеза</h1>

        {!report && (
          <button
            onClick={getReport}
            disabled={loading}
            className="px-5 py-2.5 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {loading ? 'Загрузка отчёта…' : 'Получить отчёт'}
          </button>
        )}

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {report && (
          <div className="mt-6 p-4 bg-slate-50 rounded-lg border border-slate-200 text-left">
            <h2 className="text-lg font-semibold mb-3">Ваш отчёт</h2>
            <dl className="grid gap-2 text-sm">
              {report.customerName != null && (
                <>
                  <dt className="text-slate-500">Клиент</dt>
                  <dd className="font-medium">{report.customerName}</dd>
                </>
              )}
              {report.prosthesisModel != null && (
                <>
                  <dt className="text-slate-500">Модель протеза</dt>
                  <dd>{report.prosthesisModel}</dd>
                </>
              )}
              {report.sessionCount != null && (
                <>
                  <dt className="text-slate-500">Сессий за период</dt>
                  <dd>{report.sessionCount}</dd>
                </>
              )}
              {report.totalUsageMinutes != null && (
                <>
                  <dt className="text-slate-500">Время использования, мин</dt>
                  <dd>{report.totalUsageMinutes}</dd>
                </>
              )}
              {report.eventCount != null && (
                <>
                  <dt className="text-slate-500">Событий</dt>
                  <dd>{report.eventCount}</dd>
                </>
              )}
              {report.errorCount != null && report.errorCount > 0 && (
                <>
                  <dt className="text-slate-500">Ошибок</dt>
                  <dd>{report.errorCount}</dd>
                </>
              )}
              {report.calibrationCount != null && (
                <>
                  <dt className="text-slate-500">Калибровок</dt>
                  <dd>{report.calibrationCount}</dd>
                </>
              )}
              {report.periodStart != null && report.periodEnd != null && (
                <>
                  <dt className="text-slate-500">Период</dt>
                  <dd>
                    {new Date(report.periodStart).toLocaleDateString()} — {new Date(report.periodEnd).toLocaleDateString()}
                  </dd>
                </>
              )}
            </dl>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;