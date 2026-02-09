import React, { useState } from 'react';

const AUTH_BASE = process.env.REACT_APP_AUTH_URL || ''; // например http://localhost:8081
const API_BASE = process.env.REACT_APP_API_URL || '';   // например http://localhost:8082

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const login = () => {
    // bionicpro-auth сделает redirect на Keycloak и вернёт cookie-сессию
    window.location.href = `${AUTH_BASE}/auth/login`;
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${API_BASE}/reports`, {
        method: 'GET',
        credentials: 'include' // <-- ВАЖНО: отправляем сессионную cookie
      });

      if (response.status === 401) {
        // нет сессии или она протухла
        login();
        return;
      }

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      // Если /reports отдаёт файл:
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;

      // можно взять имя из Content-Disposition, но для простоты:
      a.download = 'report.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <div className="flex gap-3">
          <button
            onClick={login}
            className="px-4 py-2 bg-gray-700 text-white rounded hover:bg-gray-800"
          >
            Login
          </button>

          <button
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Generating Report...' : 'Download Report'}
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;