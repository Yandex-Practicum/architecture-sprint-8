import React, { useState, useEffect } from 'react';
import { useKeycloak } from '@react-keycloak/web';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8081';

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isYandexAuth, setIsYandexAuth] = useState(false);
  const [isCheckingYandex, setIsCheckingYandex] = useState(true);

  useEffect(() => {
    const checkYandexSession = async () => {
      try {
        const response = await fetch(`${API_BASE}/auth/session`, {
          credentials: 'include',
        });

        if (response.ok) {
          const data = await response.json();
          setIsYandexAuth(data.authenticated === true);
        } else {
          setIsYandexAuth(false);
        }
      } catch {
        setIsYandexAuth(false);
      } finally {
        setIsCheckingYandex(false);
      }
    };

    checkYandexSession();
  }, []);

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const userId = keycloak.tokenParsed?.sub;
      if (!userId) {
        setError('User ID not found');
        return;
      }

      const response = await fetch(`${API_BASE}/api/reports/${userId}`, {
        headers: {
          Authorization: `Bearer ${keycloak.token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 403) {
          setError('You can only access your own reports');
          return;
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      console.log('Report data:', data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized || isCheckingYandex) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!keycloak.authenticated && !isYandexAuth) {
    window.location.href = '/';
    return null;
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold text-center mb-6">Usage Reports</h1>

        <button
          onClick={downloadReport}
          disabled={loading}
          className={`w-full px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Генерация отчёта...' : 'Скачать отчёт'}
        </button>

        {error && (
          <div className="mt-4 p-3 bg-red-100 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;