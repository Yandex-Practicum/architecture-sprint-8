import React, { useEffect, useState } from 'react';

type ReportData = any;

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportData | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        console.log('[ReportPage] check auth /api/auth/status ...');
        const statusRes = await fetch('http://localhost:5001/api/auth/status', {
          credentials: 'include'
        });
        console.log('[ReportPage] /api/auth/status code =', statusRes.status);
        const status = await statusRes.json().catch(() => ({} as any));
        console.log('[ReportPage] /api/auth/status payload =', status);
        if (!status?.isAuthenticated) {
          setError('Not authorized');
          return;
        }

        console.log('[ReportPage] fetch /reports ...');
        const res = await fetch('http://localhost:5001/api/reports', {
          credentials: 'include'
        });
        console.log('[ReportPage] /reports code =', res.status);
        if (res.status === 401) {
          setError('Not authorized');
          return;
        }
        if (!res.ok) {
          if (res.status === 404) {
            setError('Report not ready yet');
            return;
          }
          setError(`Report loading error: ${res.status}`);
          return;
        }

        const data = await res.json().catch(() => null);
        console.log('[ReportPage] /reports json =', data);
        setReport(data);
      } catch (e) {
        console.error('[ReportPage] error =', e);
        setError('Error getting report');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ 
            animation: 'spin 1s linear infinite', 
            borderRadius: '50%', 
            height: '48px', 
            width: '48px', 
            borderBottom: '2px solid #2563eb', 
            margin: '0 auto 16px' 
          }}></div>
          <p style={{ color: '#6b7280' }}>Loading...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ color: '#dc2626', marginBottom: '4px' }}>{error === 'Not authorized' ? 'Authentication error' : 'Report unavailable'}</p>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '12px' }}>
            <button
              onClick={() => {
                console.log('[ReportPage] click login -> /login');
                window.location.href = 'http://localhost:5001/login';
              }}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '8px 16px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                fontSize: '14px',
                fontWeight: '500',
                color: 'white',
                backgroundColor: '#2563eb'
              }}
              onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#1d4ed8'}
              onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#2563eb'}
            >
              Login
            </button>
            <a
              href="/"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                padding: '8px 16px',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
                fontSize: '14px',
                fontWeight: '500',
                color: '#374151',
                backgroundColor: 'white',
                textDecoration: 'none'
              }}
              onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#f9fafb'}
              onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = 'white'}
            >
              ← Back to home
            </a>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb' }}>
      <div style={{ maxWidth: '1280px', margin: '0 auto', padding: '24px 16px' }}>
        <h1 style={{ fontSize: '24px', fontWeight: 'bold', marginBottom: '16px' }}>Your Report</h1>
        {report ? (
          <pre style={{ 
            backgroundColor: 'white', 
            padding: '16px', 
            borderRadius: '8px', 
            border: '1px solid #e5e7eb',
            overflow: 'auto',
            fontSize: '14px'
          }}>
{JSON.stringify(report, null, 2)}
          </pre>
        ) : (
          <p style={{ color: '#6b7280' }}>Report generated and provided as file.</p>
        )}
        <div style={{ marginTop: '16px' }}>
          <a
            href="http://localhost:5001/reports"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              padding: '8px 16px',
              border: '1px solid #d1d5db',
              borderRadius: '6px',
              boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
              fontSize: '14px',
              fontWeight: '500',
              color: '#374151',
              backgroundColor: 'white',
              textDecoration: 'none'
            }}
            onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#f9fafb'}
            onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = 'white'}
          >
            Download JSON Report
          </a>
        </div>
      </div>
    </div>
  );
};

export default ReportPage;
