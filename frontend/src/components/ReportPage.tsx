import React, { useState } from 'react';
import { useAuth } from 'react-oidc-context';

const API_URL = process.env.REACT_APP_API_URL;

const ReportPage: React.FC = () => {
  const auth = useAuth();
  const [generating, setGenerating] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [generated, setGenerated] = useState<string | null>(null);
  const [downloaded, setDownloaded] = useState(false);

  const getToken = (): string | null => auth.user?.access_token ?? null;

  const generateReport = async () => {
    const token = getToken();
    if (!token) return;

    setGenerating(true);
    setError(null);
    setGenerated(null);

    try {
      const response = await fetch(`${API_URL}/reports/generate`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error ?? `Ошибка генерации: ${response.statusText}`);
      }

      const data = await response.json();
      setGenerated(`Отчёт сгенерирован за ${data.report_date}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
    } finally {
      setGenerating(false);
    }
  };

  const downloadReport = async () => {
    const token = getToken();
    if (!token) return;

    setDownloading(true);
    setError(null);
    setDownloaded(false);

    try {
      const response = await fetch(`${API_URL}/reports`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (response.status === 404) {
        throw new Error('Отчёт ещё не сформирован. Нажмите «Сгенерировать отчёт».');
      }
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        throw new Error(body.error ?? `Ошибка: ${response.statusText}`);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
      setDownloaded(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла ошибка');
    } finally {
      setDownloading(false);
    }
  };

  if (auth.isLoading) {
    return (
      <div style={styles.center}>
        <p style={{ color: '#6b7280' }}>Загрузка...</p>
      </div>
    );
  }

  if (auth.error) {
    return (
      <div style={styles.center}>
        <p style={{ color: '#b91c1c' }}>Ошибка аутентификации: {auth.error.message}</p>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div style={styles.center}>
        <div style={styles.card}>
          <h1 style={styles.title}>Usage Reports</h1>
          <p style={{ color: '#6b7280', marginBottom: '24px' }}>
            Войдите, чтобы получить доступ к отчётам
          </p>
          <button
            onClick={() => auth.signinRedirect()}
            style={styles.buttonPrimary}
          >
            Войти
          </button>
        </div>
      </div>
    );
  }

  const userName =
    auth.user?.profile?.name ??
    auth.user?.profile?.preferred_username ??
    auth.user?.profile?.email ??
    'Пользователь';

  return (
    <div style={styles.center}>
      <div style={styles.card}>
        {/* Заголовок и пользователь */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
          <div>
            <h1 style={styles.title}>Usage Reports</h1>
            <p style={{ color: '#6b7280', fontSize: '14px', marginTop: '4px' }}>
              Вы вошли как <strong>{userName}</strong>
            </p>
          </div>
          <button
            onClick={() => auth.signoutRedirect()}
            style={styles.buttonSecondary}
          >
            Выйти
          </button>
        </div>

        {/* Кнопка генерации */}
        <button
          onClick={generateReport}
          disabled={generating || downloading}
          style={{
            ...styles.buttonPrimary,
            backgroundColor: generating ? '#6ee7b7' : '#10b981',
            cursor: generating || downloading ? 'not-allowed' : 'pointer',
            width: '100%',
            marginBottom: '10px',
          }}
        >
          {generating ? '⏳ Генерация...' : '⚙️ Сгенерировать отчёт'}
        </button>

        {/* Кнопка скачивания */}
        <button
          onClick={downloadReport}
          disabled={generating || downloading}
          style={{
            ...styles.buttonPrimary,
            backgroundColor: downloading ? '#93c5fd' : '#3b82f6',
            cursor: generating || downloading ? 'not-allowed' : 'pointer',
            width: '100%',
          }}
        >
          {downloading ? '⏳ Загрузка...' : '📥 Скачать отчёт'}
        </button>

        {/* Успех генерации */}
        {generated && !error && (
          <div style={styles.success}>{generated}</div>
        )}

        {/* Успех скачивания */}
        {downloaded && !error && (
          <div style={styles.success}>Отчёт успешно скачан.</div>
        )}

        {/* Ошибка */}
        {error && (
          <div style={styles.errorBox}>{error}</div>
        )}

        <p style={{ marginTop: '16px', fontSize: '12px', color: '#9ca3af' }}>
          Сначала сгенерируйте отчёт, затем скачайте его в формате CSV.
        </p>
      </div>
    </div>
  );
};

const styles: Record<string, React.CSSProperties> = {
  center: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: '100vh',
    backgroundColor: '#f3f4f6',
  },
  card: {
    padding: '32px',
    backgroundColor: '#fff',
    borderRadius: '12px',
    boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
    width: '420px',
    maxWidth: '90vw',
  },
  title: {
    fontSize: '22px',
    fontWeight: 'bold',
    color: '#111827',
    margin: 0,
  },
  buttonPrimary: {
    padding: '10px 20px',
    backgroundColor: '#3b82f6',
    color: '#fff',
    border: 'none',
    borderRadius: '8px',
    fontSize: '15px',
    cursor: 'pointer',
    fontWeight: '500',
  },
  buttonSecondary: {
    padding: '6px 14px',
    backgroundColor: 'transparent',
    color: '#6b7280',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
    fontSize: '13px',
    cursor: 'pointer',
  },
  success: {
    marginTop: '16px',
    padding: '12px 16px',
    backgroundColor: '#d1fae5',
    color: '#065f46',
    borderRadius: '8px',
    fontSize: '14px',
  },
  errorBox: {
    marginTop: '16px',
    padding: '12px 16px',
    backgroundColor: '#fee2e2',
    color: '#b91c1c',
    borderRadius: '8px',
    fontSize: '14px',
  },
};

export default ReportPage;
