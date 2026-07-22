import React, { useState, useEffect } from 'react';
import { useKeycloak } from '@react-keycloak/web';

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const handleYandexLogin = () => {
    window.location.href = 'http://localhost:8081/auth/yandex/login';
  };
  const [isYandexAuth, setIsYandexAuth] = useState(false);
  const [isCheckingYandex, setIsCheckingYandex] = useState(true);

  useEffect(() => {
    const checkYandexSession = async () => {
      try {
        const response = await fetch('http://localhost:8081/auth/session', {
          credentials: 'include' 
        });
        
        if (response.ok) {
          const data = await response.json();
          if (data.authenticated === true) {
            setIsYandexAuth(true);
          } else {
            setIsYandexAuth(false);
          }
        } else {
          setIsYandexAuth(false);
        }
      } catch (error) {
        console.error('Yandex session check failed:', error);
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

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`
        }
      });

      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized || isCheckingYandex) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated && !isYandexAuth) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={() => keycloak.login()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login
        </button>
        <button
          onClick={() => handleYandexLogin()}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-red-600"
        >
          Яндекс ID
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>
        
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
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;