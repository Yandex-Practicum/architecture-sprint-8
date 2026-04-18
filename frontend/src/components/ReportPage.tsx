import React, { useCallback, useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

type MartRow = {
  report_date: string;
  keycloak_sub: string;
  customer_id: number;
  prosthesis_id: number;
  serial_number: string;
  model: string;
  orders_count: number;
  orders_sum: number;
  telemetry_events: string | number;
  avg_signal_quality: number;
  loaded_at: string;
};

type MartResponse = {
  sub: string;
  rows: MartRow[];
  row_count: number;
  mart_total_rows?: number;
};

const apiBase = process.env.REACT_APP_API_URL || '';

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<MartResponse | null>(null);

  const loadReport = useCallback(async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      await keycloak.updateToken(60);
      const token = keycloak.token;
      if (!token) {
        setError('Token unavailable');
        return;
      }

      const res = await fetch(`${apiBase}/reports/mart`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!res.ok) {
        const text = await res.text();
        setData(null);
        setError(text || `HTTP ${res.status}`);
        return;
      }

      const json = (await res.json()) as MartResponse;
      setData(json);
    } catch (err) {
      setData(null);
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  }, [keycloak]);

  if (!initialized) {
    return <div className="p-6 text-gray-600">Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-slate-100">
        <button
          type="button"
          onClick={() => keycloak.login()}
          className="px-5 py-2.5 bg-indigo-600 text-white rounded-lg shadow hover:bg-indigo-700"
        >
          Login
        </button>
      </div>
    );
  }

  const who =
    keycloak.tokenParsed?.preferred_username ||
    keycloak.tokenParsed?.sub ||
    'пользователь';

  return (
    <div className="min-h-screen bg-slate-100 py-10 px-4">
      <div className="max-w-6xl mx-auto bg-white rounded-xl shadow-md p-8">
        <h1 className="text-2xl font-semibold text-slate-800 mb-1">
          Отчёт по протезам
        </h1>
        <p className="text-sm text-slate-500 mb-6">
          Данные из витрины ClickHouse · <strong>{String(who)}</strong>
        </p>

        <div className="flex gap-3 mb-6">
          <button
            type="button"
            onClick={loadReport}
            disabled={loading}
            className={`px-4 py-2 rounded-lg text-white font-medium ${
              loading
                ? 'bg-indigo-400 cursor-not-allowed'
                : 'bg-indigo-600 hover:bg-indigo-700'
            }`}
          >
            {loading ? 'Загрузка…' : 'Загрузить отчёт'}
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-50 text-red-800 rounded-lg text-sm border border-red-100">
            {error}
          </div>
        )}

        {data && (
          <div className="space-y-3">
            <p className="text-sm text-slate-600">
              Найдено строк: <strong>{data.row_count}</strong>
              {data.mart_total_rows !== undefined && data.mart_total_rows >= 0 && (
                <>
                  {' '}
                  (в витрине всего: <strong>{data.mart_total_rows}</strong>)
                </>
              )}
            </p>

            {data.mart_total_rows === 0 && (
              <p className="text-sm text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                Витрина пуста — поднимите стек <code className="text-xs">dags/</code> и
                прогоните DAG <code className="text-xs">bionicpro_crm_telemetry_to_clickhouse</code>
                .
              </p>
            )}

            {data.rows.length === 0 &&
              (data.mart_total_rows ?? 0) > 0 && (
                <p className="text-sm text-amber-800 bg-amber-50 border border-amber-100 rounded-lg px-3 py-2">
                  Для этого пользователя нет строк. Демо: войдите как{' '}
                  <strong>prothetic1</strong> / <strong>prothetic123</strong> (см. README).
                </p>
              )}

            {data.rows.length > 0 ? (
              <div className="overflow-x-auto rounded-lg border border-slate-200">
                <table className="min-w-full text-sm text-left">
                  <thead className="bg-slate-50 text-slate-600 font-medium">
                    <tr>
                      <th className="px-3 py-2">Дата</th>
                      <th className="px-3 py-2">Протез</th>
                      <th className="px-3 py-2">Серийный №</th>
                      <th className="px-3 py-2">Модель</th>
                      <th className="px-3 py-2 text-right">Заказы</th>
                      <th className="px-3 py-2 text-right">Сумма</th>
                      <th className="px-3 py-2 text-right">Телеметрия</th>
                      <th className="px-3 py-2 text-right">Сигнал</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {data.rows.map((r) => (
                      <tr key={`${r.report_date}-${r.prosthesis_id}`} className="hover:bg-slate-50">
                        <td className="px-3 py-2 whitespace-nowrap">{r.report_date}</td>
                        <td className="px-3 py-2">{r.prosthesis_id}</td>
                        <td className="px-3 py-2 font-mono text-xs">{r.serial_number}</td>
                        <td className="px-3 py-2">{r.model}</td>
                        <td className="px-3 py-2 text-right">{r.orders_count}</td>
                        <td className="px-3 py-2 text-right">{r.orders_sum}</td>
                        <td className="px-3 py-2 text-right">{r.telemetry_events}</td>
                        <td className="px-3 py-2 text-right">
                          {Number(r.avg_signal_quality).toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
