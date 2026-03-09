import React, { useEffect, useState } from 'react';

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [user, setUser] = useState<any>(null);

  // Проверка сессии при загрузке
  useEffect(() => {
    fetch(`${process.env.REACT_APP_AUTH_URL}/auth/me`, {
      credentials: 'include', // обязательно для передачи куки
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => setUser(data))
      .catch(() => setUser(null));
  }, []);

  const login = (provider: string = 'keycloak') => {
    if (provider === 'yandex') {
      window.location.href = `${process.env.REACT_APP_AUTH_URL}/auth/login/yandex`;
    } else {
      window.location.href = `${process.env.REACT_APP_AUTH_URL}/auth/login`;
    }
  };

  const logout = () => {
    fetch(`${process.env.REACT_APP_AUTH_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    }).finally(() => {
      window.location.href = '/'; // или на страницу логина
    });
  };

  const downloadReport = async () => {
    if (!user) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch(
        `${process.env.REACT_APP_AUTH_URL}/api/proxy/reports`,
        {
          credentials: 'include', // передаём куку
        }
      );

      if (!response.ok) {
        throw new Error(`Failed to download report: ${response.statusText}`);
      }

      const data = await response.json();

      if (data.reportUrl) {
        // Способ 1: открыть в новой вкладке (может сразу начать скачивание, если сервер отдаёт PDF с заголовком Content-Disposition)
        window.open(data.reportUrl, '_blank');
      } else {
        throw new Error('Report URL not received');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!user) {
    return (
      <div className='flex flex-col items-center justify-center min-h-screen bg-gray-100'>
        <button
          onClick={() => login('keycloak')}
          className='px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600'
        >
          Login with BionicPRO
        </button>

        <button
          onClick={() => login('yandex')}
          className='px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600'
        >
          Login with Яндекс ID
        </button>
      </div>
    );
  }

  return (
    <div className='flex flex-col items-center justify-center min-h-screen bg-gray-100'>
      <div className='p-8 bg-white rounded-lg shadow-md'>
        <h1 className='text-2xl font-bold mb-6'>Usage Reports</h1>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>

        {error && (
          <div className='mt-4 p-4 bg-red-100 text-red-700 rounded'>
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
