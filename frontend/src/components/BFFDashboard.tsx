import React, { useState, useEffect } from 'react';
import { ReportsComponent } from './ReportsComponent';

interface UserInfo {
  sub: string;
  crm_user_id: number | null;
  username: string;
  email: string;
  given_name?: string;
  family_name?: string;
  roles: string[];
  crm_info?: {
    id: number;
    name: string;
    email: string;
    age: number;
    gender: string;
    country: string;
  } | null;
}

export const BFFDashboard: React.FC = () => {
  const [userInfo, setUserInfo] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'reports'>('dashboard');

  useEffect(() => {
    const fetchUserInfo = async () => {
      try {
        setLoading(true);
        const res = await fetch('http://localhost:5001/api/auth/status', { credentials: 'include' });
        if (!res.ok) throw new Error(`status ${res.status}`);
        const data = await res.json();
        if (data?.isAuthenticated) {
          const mapped: UserInfo = {
            sub: '',
            crm_user_id: data.crm_user_id || null,
            username: data.name ?? 'User',
            email: '',
            roles: [],
            crm_info: null
          };
          setUserInfo(mapped);
        } else {
          setError('User not authenticated');
        }
      } catch (err) {
        console.error('Failed to fetch user info:', err);
        setError('Failed to load user information');
      } finally {
        setLoading(false);
      }
    };

    fetchUserInfo();
  }, []);

  const handleLogout = async () => {
    window.location.href = '/';
  };

  const getUserRoleBadges = (roles: string[]) => {
    const roleColors: { [key: string]: { bg: string; text: string } } = {
      'prosthetic-pilot': { bg: '#dbeafe', text: '#1e40af' },
      'prothetic_user': { bg: '#dbeafe', text: '#1e40af' },
      'prosthetic-buyer': { bg: '#dcfce7', text: '#166534' },
      'default-roles-bionicpro': { bg: '#f3f4f6', text: '#374151' },
      'offline_access': { bg: '#f3e8ff', text: '#7c3aed' },
      'uma_authorization': { bg: '#fed7aa', text: '#ea580c' }
    };

    const mainRoles = roles.filter(role => 
      ['prosthetic-pilot', 'prothetic_user', 'prosthetic-buyer'].includes(role)
    );

    return mainRoles.map(role => {
      const colors = roleColors[role] || { bg: '#f3f4f6', text: '#374151' };
      const roleDisplay = (role === 'prosthetic-pilot' || role === 'prothetic_user') ? 'Prosthesis Pilot' : 'Prosthesis Buyer';
      
      return (
        <span 
          key={role} 
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '2px 10px',
            borderRadius: '9999px',
            fontSize: '12px',
            fontWeight: '500',
            backgroundColor: colors.bg,
            color: colors.text
          }}
        >
          {roleDisplay}
        </span>
      );
    });
  };

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ 
            animation: 'spin 1s linear infinite', 
            borderRadius: '50%', 
            height: '48px', 
            width: '48px', 
            borderBottom: '2px solid #2563eb', 
            margin: '0 auto 16px' 
          }}></div>
          <p style={{ marginTop: '16px', color: '#6b7280' }}>Loading profile...</p>
        </div>
      </div>
    );
  }

  if (error || !userInfo) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: '#f9fafb' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ color: '#dc2626', fontSize: '20px', marginBottom: '16px' }}>Loading Error</div>
          <p style={{ color: '#6b7280', marginBottom: '16px' }}>{error}</p>
          <button
            onClick={() => window.location.reload()}
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
            Refresh Page
          </button>
        </div>
      </div>
    );
  }

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f9fafb', padding: '32px 0' }}>
      <div style={{ maxWidth: '1024px', margin: '0 auto', padding: '0 16px' }}>
        <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)', padding: '24px', marginBottom: '32px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h1 style={{ fontSize: '30px', fontWeight: 'bold', color: '#1f2937', marginBottom: '8px' }}>
                BionicPRO Dashboard (BFF Mode)
              </h1>
              <p style={{ color: '#6b7280' }}>
                Secure authentication via Backend for Frontend
              </p>
            </div>
            <button
              onClick={handleLogout}
              style={{
                padding: '8px 16px',
                backgroundColor: '#dc2626',
                color: 'white',
                borderRadius: '6px',
                border: 'none',
                cursor: 'pointer'
              }}
              onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#b91c1c'}
              onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#dc2626'}
            >
              Logout
            </button>
          </div>
          
          <div style={{ marginTop: '24px', borderBottom: '1px solid #e5e7eb' }}>
            <nav style={{ display: 'flex', gap: '32px' }}>
              <button
                onClick={() => setActiveTab('dashboard')}
                style={{
                  padding: '8px 4px',
                  borderBottom: '2px solid',
                  borderBottomColor: activeTab === 'dashboard' ? '#2563eb' : 'transparent',
                  fontSize: '14px',
                  fontWeight: '500',
                  color: activeTab === 'dashboard' ? '#2563eb' : '#6b7280',
                  backgroundColor: 'transparent',
                  border: 'none',
                  cursor: 'pointer'
                }}
                onMouseOver={(e) => !activeTab && ((e.target as HTMLElement).style.color = '#374151')}
                onMouseOut={(e) => !activeTab && ((e.target as HTMLElement).style.color = '#6b7280')}
              >
                Home
              </button>
              {userInfo?.crm_user_id && (
                <button
                  onClick={() => setActiveTab('reports')}
                  style={{
                    padding: '8px 4px',
                    borderBottom: '2px solid',
                    borderBottomColor: activeTab === 'reports' ? '#2563eb' : 'transparent',
                    fontSize: '14px',
                    fontWeight: '500',
                    color: activeTab === 'reports' ? '#2563eb' : '#6b7280',
                    backgroundColor: 'transparent',
                    border: 'none',
                    cursor: 'pointer'
                  }}
                  onMouseOver={(e) => !activeTab && ((e.target as HTMLElement).style.color = '#374151')}
                  onMouseOut={(e) => !activeTab && ((e.target as HTMLElement).style.color = '#6b7280')}
                >
                  Reports
                </button>
              )}
            </nav>
          </div>
        </div>

        {activeTab === 'dashboard' && (
          <>
            <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)', padding: '24px', marginBottom: '32px' }}>
              <h2 style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937', marginBottom: '16px' }}>
                User Information
              </h2>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
                <div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <div>
                      <span style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280' }}>Username:</span>
                      <p style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937' }}>{userInfo.username}</p>
                    </div>
                    
                    <div>
                      <span style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280' }}>Email:</span>
                      <p style={{ fontSize: '18px', color: '#1f2937' }}>{userInfo.email}</p>
                    </div>
                    
                    {(userInfo.given_name || userInfo.family_name) && (
                      <div>
                        <span style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280' }}>Full Name:</span>
                        <p style={{ fontSize: '18px', color: '#1f2937' }}>
                          {userInfo.given_name} {userInfo.family_name}
                        </p>
                      </div>
                    )}
                  </div>
                </div>
                
                <div>
                  <span style={{ fontSize: '14px', fontWeight: '500', color: '#6b7280' }}>Roles:</span>
                  <div style={{ marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {getUserRoleBadges(userInfo.roles)}
                  </div>
                  
                  <div style={{ marginTop: '16px', padding: '12px', backgroundColor: '#f9fafb', borderRadius: '6px' }}>
                    <span style={{ fontSize: '12px', fontWeight: '500', color: '#6b7280' }}>All roles:</span>
                    <p style={{ fontSize: '14px', color: '#374151', marginTop: '4px' }}>
                      {userInfo.roles.join(', ')}
                    </p>
                  </div>
                </div>
              </div>
            </div>

            <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)', padding: '24px', marginBottom: '32px' }}>
              <h2 style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937', marginBottom: '16px' }}>
                BFF Security Features
              </h2>
              
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px', marginBottom: '24px' }}>
                <div style={{ padding: '16px', backgroundColor: '#f0fdf4', borderRadius: '8px' }}>
                  <h3 style={{ fontWeight: '600', color: '#166534', marginBottom: '8px' }}>HTTP-Only Cookies</h3>
                  <p style={{ fontSize: '14px', color: '#15803d' }}>
                    Tokens stored in secure HTTP-only cookies, inaccessible to JavaScript
                  </p>
                </div>
                
                <div style={{ padding: '16px', backgroundColor: '#eff6ff', borderRadius: '8px' }}>
                  <h3 style={{ fontWeight: '600', color: '#1e40af', marginBottom: '8px' }}>Session Rotation</h3>
                  <p style={{ fontSize: '14px', color: '#1d4ed8' }}>
                    Automatic session ID rotation on each request to protected resources
                  </p>
                </div>
                
                <div style={{ padding: '16px', backgroundColor: '#faf5ff', borderRadius: '8px' }}>
                  <h3 style={{ fontWeight: '600', color: '#7c3aed', marginBottom: '8px' }}>Token Refresh</h3>
                  <p style={{ fontSize: '14px', color: '#8b5cf6' }}>
                    Automatic access_token refresh via refresh_token (lifetime: 2 min)
                  </p>
                </div>
                
                <div style={{ padding: '16px', backgroundColor: '#fff7ed', borderRadius: '8px' }}>
                  <h3 style={{ fontWeight: '600', color: '#ea580c', marginBottom: '8px' }}>Encrypted Storage</h3>
                  <p style={{ fontSize: '14px', color: '#f97316' }}>
                    Tokens encrypted and stored in Redis on backend
                  </p>
                </div>
              </div>
            </div>

            <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)', padding: '24px' }}>
              <h2 style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937', marginBottom: '16px' }}>
                Role-based Content
              </h2>
              
              {(userInfo.roles.includes('prosthetic-pilot') || userInfo.roles.includes('prothetic_user')) && (
                <div style={{ marginBottom: '24px', padding: '16px', backgroundColor: '#eff6ff', borderRadius: '8px' }}>
                  <h3 style={{ fontWeight: '600', color: '#1e40af', marginBottom: '8px' }}>For Prosthesis Pilot</h3>
                  <ul style={{ fontSize: '14px', color: '#1d4ed8', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <li>• Prosthesis telemetry data</li>
                    <li>• Muscle signals and movements</li>
                    <li>• Usage statistics</li>
                    <li>• Prosthesis settings</li>
                  </ul>
                  <button
                    onClick={() => setActiveTab('reports')}
                    style={{
                      marginTop: '12px',
                      padding: '8px 16px',
                      backgroundColor: '#2563eb',
                      color: 'white',
                      borderRadius: '6px',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
              onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#1d4ed8'}
              onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#2563eb'}
                  >
                    Go to Reports
                  </button>
                </div>
              )}
              
              {userInfo.roles.includes('prosthetic-buyer') && (
                <div style={{ marginBottom: '24px', padding: '16px', backgroundColor: '#f0fdf4', borderRadius: '8px' }}>
                  <h3 style={{ fontWeight: '600', color: '#166534', marginBottom: '8px' }}>For Buyer</h3>
                  <ul style={{ fontSize: '14px', color: '#15803d', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <li>• Order history</li>
                    <li>• Delivery statuses</li>
                    <li>• Warranty reports</li>
                    <li>• Product catalog</li>
                  </ul>
                  <button
                    onClick={() => setActiveTab('reports')}
                    style={{
                      marginTop: '12px',
                      padding: '8px 16px',
                      backgroundColor: '#16a34a',
                      color: 'white',
                      borderRadius: '6px',
                      border: 'none',
                      cursor: 'pointer',
                      fontSize: '14px'
                    }}
                    onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#15803d'}
                    onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#16a34a'}
                  >
                    Go to Reports
                  </button>
                </div>
              )}
            </div>
          </>
        )}

        {activeTab === 'reports' && userInfo?.crm_user_id && (
          <ReportsComponent 
            userId={userInfo.crm_user_id}
            className="mb-8"
          />
        )}
      </div>
    </div>
  );
};