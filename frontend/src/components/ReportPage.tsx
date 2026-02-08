import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportItem {
  event_date: string;
  customer_id: number;
  user_external_id: string;
  full_name: string;
  prosthesis_id: number;
  events_cnt: number;
  avg_response_ms: number;
  err_cnt: number;
  battery_avg: number;
  // Дополнительные метрики
  min_response_ms: number;
  max_response_ms: number;
  p95_response_ms: number;
  min_battery: number;
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [items, setItems] = useState<ReportItem[]>([]);
  const [fromDate, setFromDate] = useState<string>('');
  const [toDate, setToDate] = useState<string>('');
  const [prosthesisId, setProsthesisId] = useState<string>('');
  const [showDetails, setShowDetails] = useState(false);

  const fetchReport = async () => {
    if (!keycloak?.token || !keycloak?.tokenParsed) {
      setError('Not authenticated');
      return;
    }

    const subject = (keycloak.tokenParsed as any)['sub'] || (keycloak.tokenParsed as any)['preferred_username'];
    if (!subject) {
      setError('User id not found in token');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setItems([]);

      const params = new URLSearchParams();
      params.set('user_external_id', subject);
      if (fromDate) params.set('from_date', fromDate);
      if (toDate) params.set('to_date', toDate);
      if (prosthesisId) params.set('prosthesis_id', prosthesisId);

      const response = await fetch(`${process.env.REACT_APP_API_URL}/reports?${params.toString()}`, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Accept': 'application/json'
        }
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(`${response.status} ${response.statusText}: ${text}`);
      }

      const data = await response.json();
      setItems(data.items || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Функция для определения цвета индикатора производительности
  const getPerformanceColor = (avgResponseMs: number): string => {
    if (avgResponseMs < 80) return 'text-green-600';
    if (avgResponseMs < 100) return 'text-yellow-600';
    return 'text-red-600';
  };

  const getBatteryColor = (batteryAvg: number): string => {
    if (batteryAvg > 50) return 'text-green-600';
    if (batteryAvg > 20) return 'text-yellow-600';
    return 'text-red-600';
  };

  if (!initialized) {
    return <div className="flex items-center justify-center min-h-screen">Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-4">BionicPRO Reports</h1>
          <p className="mb-4 text-gray-600">Please login to view your prosthesis telemetry reports</p>
          <button
            onClick={() => keycloak.login()}
            className="px-6 py-3 bg-blue-500 text-white rounded-lg hover:bg-blue-600 transition"
          >
            Login with Keycloak
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100 py-8">
      <div className="container mx-auto px-4">
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-800">Prosthesis Telemetry Reports</h1>
              <p className="text-gray-600 mt-1">
                User: {(keycloak.tokenParsed as any)?.preferred_username || 'Unknown'}
              </p>
            </div>
            <button
              onClick={() => keycloak.logout()}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300 transition"
            >
              Logout
            </button>
          </div>

          {/* Фильтры */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">From Date</label>
              <input
                type="date"
                value={fromDate}
                onChange={e => setFromDate(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">To Date</label>
              <input
                type="date"
                value={toDate}
                onChange={e => setToDate(e.target.value)}
                className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Prosthesis ID</label>
              <input
                type="number"
                value={prosthesisId}
                onChange={e => setProsthesisId(e.target.value)}
                placeholder="All"
                className="w-full border border-gray-300 rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={fetchReport}
                disabled={loading}
                className={`w-full px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition ${
                  loading ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                {loading ? 'Loading...' : 'Get Report'}
              </button>
            </div>
            <div className="flex items-end">
              <button
                onClick={() => setShowDetails(!showDetails)}
                className="w-full px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 transition"
              >
                {showDetails ? 'Hide Details' : 'Show Details'}
              </button>
            </div>
          </div>

          {/* Ошибки */}
          {error && (
            <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
              <strong>Error:</strong> {error}
            </div>
          )}

          {/* Статистика */}
          {items.length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-blue-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600">Total Events</div>
                <div className="text-2xl font-bold text-blue-600">
                  {items.reduce((sum, item) => sum + item.events_cnt, 0).toLocaleString()}
                </div>
              </div>
              <div className="bg-green-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600">Avg Response Time</div>
                <div className="text-2xl font-bold text-green-600">
                  {(items.reduce((sum, item) => sum + item.avg_response_ms, 0) / items.length).toFixed(1)} ms
                </div>
              </div>
              <div className="bg-red-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600">Total Errors</div>
                <div className="text-2xl font-bold text-red-600">
                  {items.reduce((sum, item) => sum + item.err_cnt, 0)}
                </div>
              </div>
              <div className="bg-yellow-50 p-4 rounded-lg">
                <div className="text-sm text-gray-600">Avg Battery</div>
                <div className="text-2xl font-bold text-yellow-600">
                  {(items.reduce((sum, item) => sum + item.battery_avg, 0) / items.length).toFixed(1)}%
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Таблица данных */}
        <div className="bg-white rounded-lg shadow-md overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Prosthesis</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Events</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Avg Response</th>
                  {showDetails && (
                    <>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Min/Max</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">P95</th>
                    </>
                  )}
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Errors</th>
                  <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Battery Avg</th>
                  {showDetails && (
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">Min Battery</th>
                  )}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {items.length === 0 && (
                  <tr>
                    <td colSpan={showDetails ? 9 : 6} className="px-4 py-8 text-center text-gray-500">
                      {loading ? 'Loading data...' : 'No data available. Please select filters and click "Get Report".'}
                    </td>
                  </tr>
                )}
                {items.map((item, idx) => (
                  <tr key={idx} className="hover:bg-gray-50 transition">
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">{item.event_date}</td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded text-xs font-medium">
                        {item.prosthesis_id}
                      </span>
                    </td>
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-900">
                      {item.events_cnt.toLocaleString()}
                    </td>
                    <td className={`px-4 py-3 whitespace-nowrap text-sm text-right font-medium ${getPerformanceColor(item.avg_response_ms)}`}>
                      {item.avg_response_ms.toFixed(2)} ms
                    </td>
                    {showDetails && (
                      <>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-600">
                          {item.min_response_ms.toFixed(1)} / {item.max_response_ms.toFixed(1)}
                        </td>
                        <td className="px-4 py-3 whitespace-nowrap text-sm text-right text-gray-600">
                          {item.p95_response_ms.toFixed(2)} ms
                        </td>
                      </>
                    )}
                    <td className="px-4 py-3 whitespace-nowrap text-sm text-right">
                      {item.err_cnt > 0 ? (
                        <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs font-medium">
                          {item.err_cnt}
                        </span>
                      ) : (
                        <span className="text-gray-400">0</span>
                      )}
                    </td>
                    <td className={`px-4 py-3 whitespace-nowrap text-sm text-right font-medium ${getBatteryColor(item.battery_avg)}`}>
                      {item.battery_avg.toFixed(1)}%
                    </td>
                    {showDetails && (
                      <td className={`px-4 py-3 whitespace-nowrap text-sm text-right ${getBatteryColor(item.min_battery)}`}>
                        {item.min_battery.toFixed(1)}%
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Footer */}
        {items.length > 0 && (
          <div className="mt-4 text-center text-sm text-gray-500">
            Showing {items.length} record{items.length !== 1 ? 's' : ''}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
