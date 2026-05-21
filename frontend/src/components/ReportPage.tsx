import React, { useState, useEffect } from 'react';

// Описываем интерфейс данных, которые приходят из bionicpro_reports
interface BuyerSummaryReport {
  buyerId: number;
  totalOrders: number;
  totalSpent: number;
  totalDiscount: number;
  avgSensorValue: number;
  maxPower: number;
}

// Задаем константы урлов в зависимости от вашего сборщика (пример для Vite)
const AUTH_SERVICE_URL = process.env.AUTH_SERVICE_URL || 'http://localhost:7000';
const REPORTS_SERVICE_URL = process.env.REPORTS_SERVICE_URL || 'http://localhost:7001';

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  // Добавляем стейт для данных отчета
  const [reportData, setReportData] = useState<BuyerSummaryReport | null>(null);

  // Проверка сессии при загрузке
  useEffect(() => {
    fetch(`${AUTH_SERVICE_URL}/api/auth/token`, { credentials: 'include' })
      .then(response => {
        if (response.ok) {
          setIsAuthenticated(true);
        } else {
          setIsAuthenticated(false);
        }
      })
      .catch(() => setIsAuthenticated(false));
  }, []);

  const handleLogin = () => {
    window.location.href = `${AUTH_SERVICE_URL}/api/auth/login?returnUrl=${encodeURIComponent(window.location.href)}`;
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      const response = await fetch(`${REPORTS_SERVICE_URL}/api/reports/my`, {
        method: 'GET',
        credentials: 'include', // Передает куку сессии reports_session
        headers: {
          'Content-Type': 'application/json'
        }
      });

      if (response.status === 401) {
        setError('Сессия истекла. Пожалуйста, войдите снова.');
        setIsAuthenticated(false);
        return;
      }

      if (response.status === 403) {
        setError('У вас нет прав для просмотра этого отчета.');
        return;
      }

      if (response.status === 404) {
        setError('Данные отчета для вашего аккаунта еще не сформированы в БД.');
        return;
      }

      if (!response.ok) {
        throw new Error(`Ошибка сервера: ${response.status}`);
      }

      const data: BuyerSummaryReport = await response.json();
      setReportData(data); // Сохраняем данные в стейт
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла непредвиденная ошибка');
    } finally {
      setLoading(false);
    }
  };

  if (isAuthenticated === null) {
    return <div className="flex items-center justify-center min-h-screen">Загрузка сессии...</div>;
  }

  if (!isAuthenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md text-center">
          <p className="mb-4 text-gray-600">Для просмотра отчетов необходимо авторизоваться</p>
          <button
            onClick={handleLogin}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
          >
            Войти в систему
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100 p-4">
      <div className="p-8 bg-white rounded-lg shadow-md w-full max-w-md">
        <h1 className="text-2xl font-bold mb-6 text-center">Usage Reports</h1>
        
        <button
          onClick={downloadReport}
          disabled={loading}
          className={`w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors mb-4 ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Получение данных...' : 'Показать мой отчет'}
        </button>

        {error && (
          <div className="p-4 bg-red-100 text-red-700 rounded text-sm break-words mb-4">
            {error}
          </div>
        )}

        {/* ВИЗУАЛИЗАЦИЯ ДАННЫХ ОТЧЕТА */}
        {reportData && (
          <div className="mt-4 p-4 border rounded bg-gray-50 text-gray-800 space-y-2">
            <h2 className="font-semibold text-lg border-b pb-1 mb-2">Ваша статистика (ID: {reportData.buyerId})</h2>
            <div className="flex justify-between text-sm"><span>Всего заказов:</span> <strong>{reportData.totalOrders}</strong></div>
            <div className="flex justify-between text-sm"><span>Потрачено всего:</span> <strong>{reportData.totalSpent} ₽</strong></div>
            <div className="flex justify-between text-sm"><span>Получено скидок:</span> <strong>{reportData.totalDiscount} ₽</strong></div>
            <div className="flex justify-between text-sm"><span>Ср. значение датчиков:</span> <strong>{reportData.avgSensorValue}</strong></div>
            <div className="flex justify-between text-sm"><span>Макс. мощность:</span> <strong>{reportData.maxPower} кВт</strong></div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
