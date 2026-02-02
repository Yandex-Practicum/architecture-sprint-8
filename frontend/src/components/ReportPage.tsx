import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>('');

  // Функция для форматирования даты из YYYY-MM-DD в DD-MM-YYYY
  const formatDateToDisplay = (dateString: string): string => {
    if (!dateString) return '';
    const [year, month, day] = dateString.split('-');
    return `${day}-${month}-${year}`;
  };

  // Функция для преобразования даты из DD-MM-YYYY в YYYY-MM-DD
  const formatDisplayToApi = (displayDate: string): string => {
    if (!displayDate) return '';
    const [day, month, year] = displayDate.split('-');
    return `${year}-${month}-${day}`;
  };

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    if (!selectedDate) {
      setError('Please select a date');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReportData(null);

      // Получаем username из токена (это будет client_001, client_002 и т.д.)
      const username = keycloak.tokenParsed?.preferred_username || '';
      
      // Проверяем, что пользователь имеет корректный формат имени
      if (!username.startsWith('client_')) {
        setError('Access denied: You are not authorized to access reports');
        return;
      }

      // Обновляем токен, если он скоро истечет
      await keycloak.updateToken(30);

      // Преобразуем выбранную дату в формат API (YYYY-MM-DD)
      const apiDate = formatDisplayToApi(selectedDate);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/report?client_id=${username}&report_date=${apiDate}`, {
        method: 'GET',
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Accept': 'application/json',
        }
      });

      if (!response.ok) {
        let errorMessage = '';

        try {
          const errorData = await response.json();
          // Пытаемся взять detail из ответа
          errorMessage = errorData.detail || errorData.message || response.statusText;
        } catch (jsonError) {
          // Если ответ не JSON (например, HTML), используем текст по умолчанию
          errorMessage = `${response.status} ${response.statusText}`;
        }

        // Более понятные сообщения в зависимости от кода
        if (response.status === 400) {
          throw new Error(`Invalid request: ${errorMessage}`);
        } else if (response.status === 401) {
          throw new Error('Authentication failed. Please log in again.');
        } else if (response.status === 403) {
          throw new Error(`Access denied: ${errorMessage}`);
        } else if (response.status === 404) {
          throw new Error(`Not found: ${errorMessage}`);
        } else if (response.status === 500) {
          throw new Error(`Server error: ${errorMessage}`);
        } else {
          throw new Error(`Request failed: ${errorMessage}`);
        }
      }

      // Получаем данные в формате JSON
      const data = await response.json();
      
      // Отображаем отформатированный JSON
      setReportData(JSON.stringify(data, null, 2));
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    keycloak.logout();
  };

  if (!initialized) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">Please Login</h1>
          <button
            onClick={() => keycloak.login()}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Login with Keycloak
          </button>
        </div>
      </div>
    );
  }

  // Получаем имя пользователя из токена
  const username = keycloak.tokenParsed?.preferred_username || '';

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-4xl">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <div className="flex gap-2">
            <span className="text-gray-600">Welcome, {username}</span>
            <button
              onClick={handleLogout}
              className="px-3 py-1 bg-gray-500 text-white text-sm rounded hover:bg-gray-600"
            >
              Logout
            </button>
          </div>
        </div>
        
        <div className="mb-6">
          <label htmlFor="report-date" className="block text-sm font-medium text-gray-700 mb-2">
            Select Report Date (DD-MM-YYYY)
          </label>
          <input
            type="text"
            id="report-date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            placeholder="dd-mm-yyyy"
            className="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
            pattern="\d{2}-\d{2}-\d{4}"
            title="Please enter date in DD-MM-YYYY format"
          />
          <p className="mt-1 text-sm text-gray-500">
            Enter date in format DD-MM-YYYY (e.g., 01-02-2026 for February 1, 2026)
          </p>
        </div>

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

        {reportData && (
          <div className="mt-6">
            <h2 className="text-xl font-semibold mb-2">Report Data:</h2>
            <pre className="bg-gray-50 p-4 rounded overflow-auto max-h-96">
              {reportData}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
