import React, { useCallback, useEffect, useState } from 'react';

// Base URL of the bionicpro-auth BFF. All auth and API traffic goes through it;
// the browser sends the session cookie automatically (credentials: 'include').
const AUTH_URL =
  process.env.REACT_APP_AUTH_URL || process.env.REACT_APP_API_URL || 'http://localhost:8000';

interface Me {
  username: string;
  email: string;
  roles: string[];
}

interface DailyMetric {
  date: string;
  telemetry_events: number;
  avg_response_ms: number;
  max_response_ms: number;
  avg_signal_quality: number;
  total_movements: number;
  avg_battery_pct: number;
}

interface Report {
  username: string;
  full_name?: string;
  prosthesis_serial?: string;
  region?: string;
  latest_processed_date: string;
  requested_from?: string;
  requested_to?: string;
  notice?: string;
  days: DailyMetric[];
  summary: {
    days: number;
    total_telemetry_events: number;
    total_movements: number;
    avg_response_ms: number;
  };
}

const ReportPage: React.FC = () => {
  const [me, setMe] = useState<Me | null>(null);
  const [checking, setChecking] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<Report | null>(null);
  const [cdn, setCdn] = useState<{ url: string; cached: boolean } | null>(null);
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');

  const loadMe = useCallback(async () => {
    try {
      const res = await fetch(`${AUTH_URL}/auth/me`, { credentials: 'include' });
      setMe(res.ok ? await res.json() : null);
    } catch {
      setMe(null);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  const login = () => {
    window.location.href = `${AUTH_URL}/auth/login`;
  };

  const logout = async () => {
    await fetch(`${AUTH_URL}/auth/logout`, { method: 'POST', credentials: 'include' });
    setMe(null);
    setReport(null);
  };

  // Calls the reports API through the BFF. The report is always the caller's own
  // (the backend derives the user from the token — no user id is sent).
  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      const params = new URLSearchParams();
      if (from) params.set('from', from);
      if (to) params.set('to', to);
      const qs = params.toString() ? `?${params.toString()}` : '';
      const res = await fetch(`${AUTH_URL}/api/reports${qs}`, { credentials: 'include' });
      if (res.status === 401) {
        setMe(null);
        setError('Session expired, please log in again');
        return;
      }
      if (!res.ok) {
        throw new Error(`Request failed: ${res.status}`);
      }
      const payload = await res.json();
      // When the S3 + CDN cache is enabled the API returns a link to the report
      // on the CDN instead of the body. Fetch the actual report from the CDN.
      if (payload && payload.report_url) {
        setCdn({ url: payload.report_url, cached: !!payload.cached });
        const cres = await fetch(payload.report_url);
        if (!cres.ok) {
          throw new Error(`CDN fetch failed: ${cres.status}`);
        }
        setReport(await cres.json());
      } else {
        setCdn(null);
        setReport(payload);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const saveToFile = () => {
    if (!report) return;
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `prosthesis-report-${report.username}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (checking) {
    return <div className="flex items-center justify-center min-h-screen bg-gray-100">Loading...</div>;
  }

  if (!me) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button onClick={login} className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center min-h-screen bg-gray-100 py-10">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-3xl">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Prosthesis Usage Report</h1>
          <div className="text-sm text-gray-600">
            {me.username}
            <button onClick={logout} className="ml-3 text-blue-600 hover:underline">
              Logout
            </button>
          </div>
        </div>

        <div className="flex flex-wrap items-end gap-3 mb-4">
          <label className="text-sm text-gray-700">
            From
            <input type="date" value={from} onChange={(e) => setFrom(e.target.value)}
              className="block border rounded px-2 py-1" />
          </label>
          <label className="text-sm text-gray-700">
            To
            <input type="date" value={to} onChange={(e) => setTo(e.target.value)}
              className="block border rounded px-2 py-1" />
          </label>
          <button
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Generating…' : 'Get Report'}
          </button>
        </div>

        {error && <div className="mb-4 p-3 bg-red-100 text-red-700 rounded">{error}</div>}

        {report && (
          <div>
            <div className="text-sm text-gray-700 mb-3">
              <div><b>{report.full_name}</b> · S/N {report.prosthesis_serial} · {report.region}</div>
              <div>Data processed up to: <b>{report.latest_processed_date || '—'}</b></div>
            </div>

            {cdn && (
              <div className="mb-3 p-2 bg-green-50 text-green-800 rounded text-xs">
                Served via CDN {cdn.cached ? '(cache hit — OLAP not queried)' : '(freshly generated & cached)'}:{' '}
                <a href={cdn.url} target="_blank" rel="noreferrer" className="underline break-all">{cdn.url}</a>
              </div>
            )}

            {report.notice && (
              <div className="mb-3 p-3 bg-yellow-100 text-yellow-800 rounded text-sm">{report.notice}</div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  <tr className="bg-gray-100 text-left">
                    <th className="p-2">Date</th>
                    <th className="p-2">Events</th>
                    <th className="p-2">Avg resp, ms</th>
                    <th className="p-2">Max resp, ms</th>
                    <th className="p-2">Signal</th>
                    <th className="p-2">Movements</th>
                    <th className="p-2">Battery %</th>
                  </tr>
                </thead>
                <tbody>
                  {report.days.map((d) => (
                    <tr key={d.date} className="border-t">
                      <td className="p-2">{d.date}</td>
                      <td className="p-2">{d.telemetry_events}</td>
                      <td className="p-2">{d.avg_response_ms}</td>
                      <td className="p-2">{d.max_response_ms}</td>
                      <td className="p-2">{d.avg_signal_quality}</td>
                      <td className="p-2">{d.total_movements}</td>
                      <td className="p-2">{d.avg_battery_pct}</td>
                    </tr>
                  ))}
                  {report.days.length === 0 && (
                    <tr><td className="p-2 text-gray-500" colSpan={7}>No data for the selected period.</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            <div className="mt-3 text-sm text-gray-700">
              Summary: {report.summary.days} day(s), {report.summary.total_telemetry_events} events,{' '}
              {report.summary.total_movements} movements, avg response{' '}
              {report.summary.avg_response_ms.toFixed(1)} ms.
            </div>

            <button onClick={saveToFile} className="mt-3 text-blue-600 hover:underline">
              Save to file
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
