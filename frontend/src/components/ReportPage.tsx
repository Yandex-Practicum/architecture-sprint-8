import React, { useCallback, useEffect, useState } from 'react';

const API_BASE = "http://localhost:8443";

type Me = { user_id: string; username: string } | null;

const ReportPage: React.FC = () => {
  const [me, setMe] = useState<Me>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/me`, {
          method: 'GET',
          credentials: 'include',
        });
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json();
          setMe({ user_id: data.user_id, username: data.username });
        } else if (res.status === 401) {
          setMe(null);
        } else {
          setError(`Failed to check session: ${res.status}`);
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Network error');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(() => {
    window.location.href = `${API_BASE}/auth/login`;
  }, []);

  const logout = useCallback(async () => {
    await fetch(`${API_BASE}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setMe(null);
  }, []);

  const downloadReport = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const res = await fetch(`${API_BASE}/reports`, {
        method: 'GET',
        credentials: 'include',
      });
      if (res.status === 401) {
        setMe(null);
        setError('Сессия истекла, войдите снова');
        return;
      }
      if (!res.ok) {
        const body = await res.text();
        setError(`Ошибка отчёта: ${res.status} ${body}`);
        return;
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'report.csv';
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error');
    } finally {
      setLoading(false);
    }
  }, []);

  if (me === null && error === null) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={login}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-2">Usage Reports</h1>
        <p className="text-sm text-gray-600 mb-6">
          Signed in as <span className="font-mono">{me?.username}</span> ({me?.user_id})
        </p>

        <div className="flex gap-3">
          <button
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Generating Report...' : 'Download Report'}
          </button>
          <button
            onClick={logout}
            className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
          >
            Logout
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">{error}</div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;