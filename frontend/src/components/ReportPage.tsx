import React, { useCallback, useEffect, useState } from 'react';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8181';
const API_URL = process.env.REACT_APP_API_URL || AUTH_URL;

type ProfileStatus = {
  needsConsent: boolean;
  consentAccepted?: boolean;
  preview?: { email: string; displayName: string };
};

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionInfo, setSessionInfo] = useState<{ authenticated: boolean; subject?: string } | null>(null);
  const [profileStatus, setProfileStatus] = useState<ProfileStatus | null>(null);
  const [profileError, setProfileError] = useState<string | null>(null);
  const [consentLoading, setConsentLoading] = useState(false);
  const [reportPayload, setReportPayload] = useState<Record<string, unknown> | null>(null);

  const checkSession = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/session`, {
        credentials: 'include',
      });
      if (res.ok) {
        const data = await res.json();
        setSessionInfo({ authenticated: true, subject: data.subject as string });
      } else {
        setSessionInfo({ authenticated: false });
      }
    } catch {
      setSessionInfo({ authenticated: false });
    }
  }, []);

  const loadProfileStatus = useCallback(async () => {
    setProfileError(null);
    try {
      const res = await fetch(`${API_URL}/api/profile/status`, { credentials: 'include' });
      if (res.ok) {
        const data = (await res.json()) as ProfileStatus;
        setProfileStatus(data);
      } else {
        setProfileStatus(null);
        setProfileError(`Не удалось загрузить статус согласия (${res.status})`);
      }
    } catch (e) {
      setProfileStatus(null);
      setProfileError(e instanceof Error ? e.message : 'Ошибка сети');
    }
  }, []);

  useEffect(() => {
    void checkSession();
  }, [checkSession]);

  useEffect(() => {
    if (sessionInfo?.authenticated) {
      void loadProfileStatus();
    } else {
      setProfileStatus(null);
      setProfileError(null);
    }
  }, [sessionInfo?.authenticated, loadProfileStatus]);

  const login = () => {
    window.location.href = `${AUTH_URL}/oauth2/authorization/keycloak`;
  };

  const logout = async () => {
    await fetch(`${API_URL}/api/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setSessionInfo({ authenticated: false });
    setProfileStatus(null);
    setProfileError(null);
  };

  const submitConsent = async (accept: boolean) => {
    try {
      setConsentLoading(true);
      setError(null);
      const res = await fetch(`${API_URL}/api/profile/consent`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accept }),
      });
      if (!res.ok) {
        const t = await res.text();
        setError(t || `Ошибка ${res.status}`);
        return;
      }
      if (!accept) {
        await logout();
        return;
      }
      await loadProfileStatus();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setConsentLoading(false);
    }
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReportPayload(null);

      const response = await fetch(`${API_URL}/api/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setError('Сессия недействительна. Войдите снова.');
        setSessionInfo({ authenticated: false });
        return;
      }

      if (!response.ok) {
        const t = await response.text();
        setError(t || `Ошибка: ${response.status}`);
        return;
      }

      const envelope = (await response.json()) as Record<string, unknown>;
      if (envelope.cacheStatus === 'hit' && typeof envelope.reportUrl === 'string') {
        const r2 = await fetch(envelope.reportUrl);
        if (!r2.ok) {
          setError(`Не удалось загрузить отчёт с CDN (${r2.status})`);
          return;
        }
        const report = (await r2.json()) as Record<string, unknown>;
        setReportPayload({ ...envelope, ...report });
      } else {
        setReportPayload(envelope);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (sessionInfo === null) {
    return <div className="flex items-center justify-center min-h-screen bg-gray-100">Загрузка...</div>;
  }

  if (!sessionInfo.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <p className="mb-4 text-gray-600 text-center max-w-md">
          Войдите через Keycloak. Для входа через Яндекс выберите кнопку «Яндекс» на странице входа Keycloak (после
          настройки Identity Provider).
        </p>
        <button
          type="button"
          onClick={login}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Войти через Keycloak
        </button>
      </div>
    );
  }

  if (profileStatus === null && profileError === null) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        Проверка согласия на данные профиля…
      </div>
    );
  }

  if (profileError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 gap-4 p-4">
        <p className="text-red-700 text-center max-w-md">{profileError}</p>
        <button
          type="button"
          onClick={() => void loadProfileStatus()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Повторить
        </button>
        <button type="button" onClick={() => void logout()} className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300">
          Выйти
        </button>
      </div>
    );
  }

  const showConsent =
    profileStatus?.needsConsent === true &&
    profileStatus?.consentAccepted !== true;

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      {showConsent && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="bg-white rounded-lg shadow-lg max-w-md w-full p-6">
            <h2 className="text-lg font-semibold mb-2">Согласие на обработку данных</h2>
            <p className="text-sm text-gray-600 mb-4">
              Сервис протезирования использует данные профиля из Яндекс ID (имя, email и др.) для оказания услуг.
              Разрешите сохранение профиля в системе или откажитесь — тогда вы будете выведены из аккаунта.
            </p>
            <p className="text-xs text-gray-500 mb-4">
              Предпросмотр: {profileStatus.preview?.displayName || '—'} · {profileStatus.preview?.email || '—'}
            </p>
            <div className="flex gap-2 justify-end">
              <button
                type="button"
                disabled={consentLoading}
                onClick={() => void submitConsent(false)}
                className="px-3 py-2 bg-gray-200 rounded hover:bg-gray-300"
              >
                Отказаться
              </button>
              <button
                type="button"
                disabled={consentLoading}
                onClick={() => void submitConsent(true)}
                className="px-3 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                {consentLoading ? 'Сохранение...' : 'Согласиться'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-lg">
        <p className="text-sm text-gray-600 mb-4">
          Пользователь: <strong>{sessionInfo.subject}</strong>
        </p>
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <div className="flex gap-2 mb-4">
          <button
            type="button"
            onClick={downloadReport}
            disabled={loading || showConsent}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading || showConsent ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Запрос...' : 'Получить отчёт (cookie)'}
          </button>
          <button
            type="button"
            onClick={() => void logout()}
            className="px-4 py-2 bg-gray-200 rounded hover:bg-gray-300"
          >
            Выйти
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {reportPayload && (
          <div className="mt-6">
            <h2 className="text-lg font-semibold mb-2">Отчёт по протезу (OLAP)</h2>
            {reportPayload.cacheStatus != null && (
              <p className="text-xs text-gray-500 mb-2">
                Кэш: {String(reportPayload.cacheStatus)}
                {typeof reportPayload.reportUrl === 'string' && (
                  <>
                    {' '}
                    ·{' '}
                    <a
                      href={reportPayload.reportUrl}
                      className="text-blue-600 underline break-all"
                      target="_blank"
                      rel="noreferrer"
                    >
                      ссылка CDN
                    </a>
                  </>
                )}
              </p>
            )}
            {typeof reportPayload.coverageHint === 'string' && (
              <p className="text-sm text-gray-700 mb-2 border-l-4 border-blue-200 pl-3 py-1 bg-blue-50/50 rounded-r">
                {reportPayload.coverageHint}
              </p>
            )}
            <p className="text-sm text-gray-600 mb-2">
              Данные из витрины; при отсутствии строк для вашего пользователя в ETL — укажите свой "sub": {' '}
              <code className="bg-gray-100 px-1 rounded break-all">
                {reportPayload.userSubject != null ? String(reportPayload.userSubject) : '—'}
              </code>{' '}
              в CSV или выполните DAG в Airflow после входа.
            </p>
            <pre className="text-xs bg-gray-50 border rounded p-3 overflow-auto max-h-96 whitespace-pre-wrap">
              {JSON.stringify(reportPayload, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
