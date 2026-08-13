import React, { useState } from 'react';
import { useKeycloak } from '@react-keycloak/web';

interface ReportData {
  user_id: string;
  prosthesis_id: string;
  recorded_at: string;
  movement_type: string;
  battery_level: number;
  crm_user_name: string;
  crm_region: string;
}

interface ReportResponse {
  user_id: string;
  prosthesis_id: string;
  reports: ReportData[];
  generated_at: string;
}

const ReportPage: React.FC = () => {
  const { keycloak, initialized } = useKeycloak();
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchReport = async () => {
    if (!initialized || !keycloak.authenticated) {
      setError('Not authenticated');
      return;
    }

    setLoading(true);
    setError(null);
    setReport(null);

    try {
      const tokenPayload = keycloak.tokenParsed;
      const userId = tokenPayload?.preferred_username || tokenPayload?.sub;

      if (!userId) {
        throw new Error('Cannot extract user ID from token');
      }

      const response = await fetch(
        `http://localhost:8000/api/reports/${userId}`,
        {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${keycloak.token}`,
            'Content-Type': 'application/json',
          },
        }
      );

      if (response.status === 404) {
        throw new Error('No reports found. Data may not be processed by ETL yet.');
      }

      if (response.status === 403) {
        throw new Error('Access denied: you can only view your own reports');
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: ReportResponse = await response.json();
      setReport(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const downloadReport = async () => {
    if (!initialized || !keycloak.authenticated) {
      setError('Not authenticated');
      return;
    }

    try {
      const tokenPayload = keycloak.tokenParsed;
      const userId = tokenPayload?.preferred_username || tokenPayload?.sub;

      if (!userId) {
        throw new Error('Cannot extract user ID from token');
      }

      const response = await fetch(
        `http://localhost:8000/api/reports/${userId}/download`,
        {
          method: 'GET',
          headers: {
            Authorization: `Bearer ${keycloak.token}`,
          },
        }
      );

      if (!response.ok) {
        throw new Error('Failed to download report');
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${userId}.json`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to download');
    }
  };

  if (!initialized) {
    return <div>Loading...</div>;
  }

  if (!keycloak.authenticated) {
    return (
      <div className="report-page">
        <h1>Please login to view reports</h1>
        <button onClick={() => keycloak.login()}>Login</button>
      </div>
    );
  }

  return (
    <div className="report-page" style={{ padding: '20px' }}>
      <h1>Отчёт о работе протеза</h1>

      <div style={{ marginBottom: '20px' }}>
        <button
          onClick={fetchReport}
          disabled={loading}
          style={{
            padding: '10px 20px',
            marginRight: '10px',
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Загрузка...' : 'Получить отчёт'}
        </button>

        <button
          onClick={downloadReport}
          disabled={loading || !report}
          style={{
            padding: '10px 20px',
            cursor: loading || !report ? 'not-allowed' : 'pointer',
          }}
        >
          Скачать отчёт (JSON)
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: '10px',
            backgroundColor: '#ffebee',
            color: '#c62828',
            borderRadius: '4px',
            marginBottom: '20px',
          }}
        >
          {error}
        </div>
      )}

      {report && (
        <div style={{ marginTop: '20px' }}>
          <h2>Данные отчёта</h2>
          <p><strong>User ID:</strong> {report.user_id}</p>
          <p><strong>Prosthesis ID:</strong> {report.prosthesis_id}</p>
          <p><strong>Generated at:</strong> {new Date(report.generated_at).toLocaleString()}</p>
          <p><strong>Total records:</strong> {report.reports.length}</p>

          <h3>История телеметрии:</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px' }}>
            <thead>
              <tr style={{ backgroundColor: '#f5f5f5' }}>
                <th style={{ border: '1px solid #ddd', padding: '8px' }}>Дата/Время</th>
                <th style={{ border: '1px solid #ddd', padding: '8px' }}>Протез</th>
                <th style={{ border: '1px solid #ddd', padding: '8px' }}>Движение</th>
                <th style={{ border: '1px solid #ddd', padding: '8px' }}>Заряд (%)</th>
                <th style={{ border: '1px solid #ddd', padding: '8px' }}>Пользователь</th>
                <th style={{ border: '1px solid #ddd', padding: '8px' }}>Регион</th>
              </tr>
            </thead>
            <tbody>
              {report.reports.map((r, index) => (
                <tr key={index}>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                    {new Date(r.recorded_at).toLocaleString()}
                  </td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{r.prosthesis_id}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{r.movement_type}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{r.battery_level}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{r.crm_user_name}</td>
                  <td style={{ border: '1px solid #ddd', padding: '8px' }}>{r.crm_region}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default ReportPage;