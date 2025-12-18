import React, { useEffect, useState } from 'react';

const BFF_BASE = 'http://localhost:5001';

export const FinalDashboard: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [userName, setUserName] = useState<string>('');
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [hasReport, setHasReport] = useState<boolean>(false);
  const [userId, setUserId] = useState<number | null>(null);
  const [crmUserId, setCrmUserId] = useState<number | null>(null);
  const [summary, setSummary] = useState<Record<string, any> | null>(null);
  const [fullReport, setFullReport] = useState<Record<string, any> | null>(null);
  const [showFull, setShowFull] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const st = await fetch(`${BFF_BASE}/api/auth/status`, { credentials: 'include' });
        const stJson = await st.json().catch(() => ({} as any));
        setIsAuthenticated(!!stJson?.isAuthenticated);
        setUserName(stJson?.name || stJson?.username || 'User');
        setUserId(typeof stJson?.userId === 'number' ? stJson.userId : null);
        setCrmUserId(typeof stJson?.crm_user_id === 'number' ? stJson.crm_user_id : null);
        if (!stJson?.isAuthenticated) {
          setError('Not authorized');
          return;
        }
        const r = await fetch(`${BFF_BASE}/api/reports`, { credentials: 'include' });
        if (r.status === 200) {
          setHasReport(true);
          const j = await r.json().catch(() => null);
          setFullReport(j);
          if (j && typeof j === 'object') {
            const pick = (k: string) => (k in j ? j[k] : undefined);
            const short: Record<string, any> = {};
            const fields = [
              'user_id', 'username', 'email',
              'total_sessions', 'total_signals', 'total_usage_time',
              'average_session_time', 'muscle_groups', 'average_accuracy',
              'last_activity', 'has_data'
            ];
            fields.forEach(f => {
              const v = pick(f);
              if (v !== undefined) short[f] = v;
            });
            setSummary(Object.keys(short).length ? short : j);
          }
        } else if (r.status === 404) {
          setHasReport(false);
        } else {
          setError(`Report check error: ${r.status}`);
        }
      } catch (e) {
        setError('Data loading error');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleLogin = () => {
    window.location.href = `${BFF_BASE}/login`;
  };

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

  if (!isAuthenticated) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <p style={{ color: '#dc2626', marginBottom: '16px' }}>Not authorized</p>
          <a 
            href={`${BFF_BASE}/login`} 
            style={{
              display: 'inline-block',
              padding: '8px 16px',
              backgroundColor: '#2563eb',
              color: 'white',
              borderRadius: '6px',
              textDecoration: 'none'
            }}
            onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#1d4ed8'}
            onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#2563eb'}
          >
            Login
          </a>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb', padding: '32px 0' }}>
      <div style={{ maxWidth: '768px', margin: '0 auto', padding: '0 16px' }}>
        <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', padding: '24px', marginBottom: '24px' }}>
          <h1 style={{ fontSize: '24px', fontWeight: 'bold', color: '#1f2937', marginBottom: '4px' }}>Profile</h1>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <p style={{ color: '#374151' }}>User: <span style={{ fontWeight: '600' }}>{userName}</span></p>
            <a 
              href={`${BFF_BASE}/auth/logout`} 
              style={{
                padding: '6px 12px',
                backgroundColor: '#e5e7eb',
                color: '#1f2937',
                borderRadius: '6px',
                fontSize: '14px',
                textDecoration: 'none'
              }}
              onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#d1d5db'}
              onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#e5e7eb'}
            >
              Logout
            </a>
          </div>
          <p style={{ color: '#6b7280', fontSize: '14px' }}>CRM ID: {crmUserId ?? '—'}</p>
        </div>

        <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', padding: '24px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: '600', color: '#1f2937', marginBottom: '12px' }}>Reports</h2>
          {error && (
            <p style={{ color: '#dc2626', marginBottom: '12px' }}>{error}</p>
          )}
          {crmUserId && hasReport ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <h3 style={{ fontWeight: '600' }}>Summary</h3>
              {summary && Object.keys(summary).length > 0 ? (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px 12px', fontSize: '14px' }}>
                  {Object.entries(summary).slice(0, 12).map(([k, v]) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <span style={{ color: '#6b7280' }}>{k}:</span>
                      <span style={{ color: '#1f2937', marginLeft: '8px', maxWidth: '220px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={String(v)}>{String(v)}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <pre style={{ backgroundColor: '#f9fafb', padding: '12px', borderRadius: '6px', border: '1px solid #e5e7eb', fontSize: '12px', overflow: 'auto', maxHeight: '320px' }}>
{JSON.stringify(fullReport ?? {}, null, 2)}
                </pre>
              )}

              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <button 
                  onClick={() => setShowFull(v => !v)} 
                  style={{
                    padding: '8px 16px',
                    backgroundColor: '#2563eb',
                    color: 'white',
                    borderRadius: '6px',
                    border: 'none',
                    cursor: 'pointer'
                  }}
                  onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#1d4ed8'}
                  onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#2563eb'}
                >
                  {showFull ? 'Hide detailed' : 'Show detailed'}
                </button>
              </div>
            </div>
          ) : crmUserId ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <p style={{ color: '#6b7280' }}>Detailed report not available yet. It comes from the data warehouse.</p>
            </div>
          ) : (
            <p style={{ color: '#6b7280' }}>Reports not available for this user.</p>
          )}

          {showFull && fullReport && (
            <div style={{ marginTop: '16px' }}>
              <h3 style={{ fontWeight: '600', marginBottom: '8px' }}>Detailed Report</h3>
              <pre style={{ backgroundColor: '#f9fafb', padding: '12px', borderRadius: '6px', border: '1px solid #e5e7eb', fontSize: '12px', overflow: 'auto', maxHeight: '384px' }}>{JSON.stringify(fullReport, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default FinalDashboard;


