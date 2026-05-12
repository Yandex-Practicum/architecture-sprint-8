import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportStat {
  date: string;
  total_movements: number;
  avg_signal_quality: number;
  min_battery_level: number;
  calibration_count: number;
}

interface ReportData {
  user_id: string;
  period: {
    from: string;
    to: string;
  };
  stats: ReportStat[];
  message?: string;
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportData, setReportData] = useState<ReportData | null>(null);

  // Состояния для дат
  const [fromDate, setFromDate] = useState(() => {
    const date = new Date();
    date.setMonth(date.getMonth() - 1);
    return date.toISOString().split('T')[0];
  });
  const [toDate, setToDate] = useState(() => {
    return new Date().toISOString().split('T')[0];
  });

  const downloadReport = async () => {
    if (!keycloak?.token) {
      setError('Not authenticated');
      return;
    }

    if (!fromDate || !toDate) {
      setError('Please select both from and to dates');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setReportData(null);

      const username = keycloak.tokenParsed?.preferred_username;

      if (!username) {
        setError('Unable to get user info');
        return;
      }

      const url = `${process.env.REACT_APP_API_URL}/reports/${username}?from_date=${fromDate}&to_date=${toDate}`;

      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Content-Type': 'application/json',
        }
      });

      if (!response.ok) {
        if (response.status === 403) {
          throw new Error('Access denied: you can only request your own reports');
        }
        if (response.status === 401) {
          throw new Error('Session expired. Please login again.');
        }
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setReportData(data);
      setError(null);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh'
      }}>
        <button
          onClick={() => keycloak.login()}
          style={{
            padding: '10px 20px',
            backgroundColor: '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '5px',
            cursor: 'pointer'
          }}
        >
          Login
        </button>
      </div>
    );
  }

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '20px' }}>Usage Reports</h1>

      {/* Форма выбора дат */}
      <div style={{ display: 'flex', gap: '20px', marginBottom: '20px', alignItems: 'flex-end' }}>
        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>From Date:</label>
          <input
            type="date"
            value={fromDate}
            onChange={(e) => setFromDate(e.target.value)}
            style={{ padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
          />
        </div>
        <div>
          <label style={{ display: 'block', marginBottom: '5px', fontWeight: 'bold' }}>To Date:</label>
          <input
            type="date"
            value={toDate}
            onChange={(e) => setToDate(e.target.value)}
            style={{ padding: '8px', border: '1px solid #ccc', borderRadius: '4px' }}
          />
        </div>
        <button
          onClick={downloadReport}
          disabled={loading}
          style={{
            padding: '8px 20px',
            backgroundColor: loading ? '#9ca3af' : '#3b82f6',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer'
          }}
        >
          {loading ? 'Generating Report...' : 'Download Report'}
        </button>
      </div>

      {/* Ошибка */}
      {error && (
        <div style={{
          marginTop: '20px',
          padding: '15px',
          backgroundColor: '#fee2e2',
          color: '#dc2626',
          borderRadius: '5px'
        }}>
          {error}
        </div>
      )}

      {/* Отчёт */}
      {reportData && (
        <div>
          {reportData.stats.length === 0 ? (
            <div style={{
              padding: '20px',
              backgroundColor: '#fef3c7',
              color: '#d97706',
              borderRadius: '5px'
            }}>
              ⚠️ {reportData.message || "No data available for the selected period. Reports are updated daily."}
            </div>
          ) : (
            <div style={{
              marginTop: '20px',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '20px'
            }}>
              <h2 style={{ fontSize: '20px', fontWeight: 'bold', marginBottom: '10px' }}>
                Report for {reportData.user_id}
              </h2>
              <p style={{ color: '#6b7280', marginBottom: '15px' }}>
                Period: {reportData.period.from} — {reportData.period.to}
              </p>

              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ backgroundColor: '#f9fafb' }}>
                    <th style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'left' }}>Date</th>
                    <th style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>Movements</th>
                    <th style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>Signal Quality</th>
                    <th style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>Min Battery</th>
                    <th style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>Calibrations</th>
                  </tr>
                </thead>
                <tbody>
                  {reportData.stats.map((stat) => (
                    <tr key={stat.date}>
                      <td style={{ padding: '10px', border: '1px solid #e5e7eb' }}>{stat.date}</td>
                      <td style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>{stat.total_movements}</td>
                      <td style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>{stat.avg_signal_quality.toFixed(2)}</td>
                      <td style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>{stat.min_battery_level}%</td>
                      <td style={{ padding: '10px', border: '1px solid #e5e7eb', textAlign: 'right' }}>{stat.calibration_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ReportPage;