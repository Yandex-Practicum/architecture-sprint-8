import React, { useState, useEffect } from 'react';

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);


  // При загрузке страницы проверяем, жива ли кука-сессия
  useEffect(() => {
    fetch(`${process.env.AUTH_SERVER_URL}/api/Auth/token`, { credentials: 'include' })
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
    // Отправляем пользователя на ваш эндпоинт входа. 
    // После авторизации в Keycloak ваш сервер вернет его обратно на фронтенд.
    window.location.href = `${process.env.AUTH_SERVER_URL}/api/Auth/login?returnUrl=${window.location.href}`;
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);

      // Запрос идет на ваш сервер. Токен Bearer больше не нужен!
      const response = await fetch(`${process.env.AUTH_SERVER_URL}/api/Reports/common`, {
        method: 'GET',
        // КРИТИЧЕСКИ ВАЖНО: заставляет браузер автоматически прикрепить куку reports_session
        credentials: 'include', 
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
        setError('Ошибка 403: У вас нет прав (роли) для скачивания этого отчета.');
        return;
      }

      if (!response.ok) {
        throw new Error(`Ошибка сервера: ${response.status}`);
      }

      // Обработка успешного скачивания (например, парсинг файла или JSON)
      const data = await response.json();
      console.log('Данные успешно получены через куку:', data);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Произошла непредвиденная ошибка');
    } finally {
      setLoading(false);
    }
  };

  // Состояние загрузки проверки сессии при первом открытии
  if (isAuthenticated === null) {
    return <div className="flex items-center justify-center min-h-screen">Загрузка сессии...</div>;
  }

  // Если куки нет — показываем кнопку входа, которая ведет на BFF-сервер
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

  // Если пользователь успешно авторизован по куке
  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md w-96">
        <h1 className="text-2xl font-bold mb-6 text-center">Usage Reports</h1>
        
        <button
          onClick={downloadReport}
          disabled={loading}
          className={`w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors ${
            loading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {loading ? 'Генерация отчета...' : 'Скачать отчет'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded text-sm break-words">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
