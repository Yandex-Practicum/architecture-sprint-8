import React, { useState } from 'react';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<string | null>(null);

  const login = () => {
    window.location.href = `${API_URL}/auth/login`;
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReport(null);
      const response = await fetch(`${API_URL}/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setError('Не авторизован. Нажмите Login.');
        return;
      }

      if (!response.ok) {
        throw new Error(`Ошибка ${response.status}`);
      }

      const data = await response.json();
      setReport(JSON.stringify(data, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-xl">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>

        <div className="flex gap-3 mb-4">
          <button
            onClick={login}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Login
          </button>
          <button
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Loading...' : 'Download Report'}
          </button>
        </div>

        {error && (
          <div className="mt-2 p-3 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {report && (
          <div className="mt-3 p-3 bg-gray-50 text-gray-800 rounded break-words">
            {report}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;