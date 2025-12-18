import React, { useState, useEffect } from 'react';
import ReportPage from './components/ReportPage';
import FinalDashboard from './components/FinalDashboard';

function HomePage() {
  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#f8fafc', padding: '48px 0' }}>
      <div style={{ maxWidth: '1024px', margin: '0 auto', padding: '0 16px' }}>
        <div style={{ textAlign: 'center', marginBottom: '48px' }}>
          <h1 style={{ fontSize: '36px', fontWeight: 'bold', color: '#1f2937', marginBottom: '16px' }}>
            BionicPRO Security Demo
          </h1>
          <p style={{ fontSize: '20px', color: '#6b7280' }}>
            OAuth 2.0 with PKCE Authentication Demo
          </p>
        </div>

        <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 10px 15px -3px rgba(0, 0, 0, 0.1)', padding: '32px', marginBottom: '32px' }}>
          <h2 style={{ fontSize: '24px', fontWeight: '600', color: '#1f2937', marginBottom: '24px', textAlign: 'center' }}>
            BionicPRO System Login
          </h2>
          
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <p style={{ color: '#6b7280' }}>
              Enter your credentials. Role will be determined automatically.
            </p>
          </div>

          <div style={{ maxWidth: '384px', margin: '0 auto' }}>
            <a
              href="http://localhost:5001/login"
              style={{ 
                display: 'block', 
                textAlign: 'center', 
                backgroundColor: '#2563eb', 
                color: 'white', 
                fontWeight: 'bold', 
                padding: '12px 24px', 
                borderRadius: '8px', 
                textDecoration: 'none',
                transition: 'background-color 0.2s'
              }}
              onMouseOver={(e) => (e.target as HTMLElement).style.backgroundColor = '#1d4ed8'}
              onMouseOut={(e) => (e.target as HTMLElement).style.backgroundColor = '#2563eb'}
            >
              Login to BionicPRO
            </a>
          </div>

          <div style={{ marginTop: '24px', paddingTop: '24px', borderTop: '1px solid #e5e7eb' }}>
            <div style={{ textAlign: 'center', fontSize: '14px', color: '#6b7280' }}>
              <p style={{ marginBottom: '8px', fontWeight: 'bold' }}>Test Credentials:</p>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '16px', textAlign: 'left' }}>
                <div style={{ backgroundColor: '#eff6ff', padding: '12px', borderRadius: '8px' }}>
                  <p style={{ fontWeight: 'bold' }}>CRM Users:</p>
                  <p>alexis.moore / bionicpro123</p>
                  <p>paige.gonzales / bionicpro123</p>
                  <p>theresa.kelly / bionicpro123</p>
                  <p style={{ fontSize: '12px', color: '#2563eb', marginTop: '4px' }}>View only their reports by CRM ID</p>
                </div>
                <div style={{ backgroundColor: '#f0fdf4', padding: '12px', borderRadius: '8px' }}>
                  <p style={{ fontWeight: 'bold' }}>LDAP Users:</p>
                  <p>john.doe / password</p>
                  <p>jane.smith / password</p>
                  <p>alex.johnson / password</p>
                </div>
                <div style={{ backgroundColor: '#faf5ff', padding: '12px', borderRadius: '8px' }}>
                  <p style={{ fontWeight: 'bold' }}>Others:</p>
                  <p>testuser / password123</p>
                  <p>buyer / buyer123</p>
                </div>
              </div>
              <div style={{ marginTop: '16px' }}>
                <div style={{ backgroundColor: '#fefce8', padding: '12px', borderRadius: '8px' }}>
                  <p style={{ fontWeight: 'bold' }}>Yandex ID:</p>
                  <p>Login via Yandex ID on Keycloak login page</p>
                  <p style={{ fontSize: '12px', color: '#6b7280', marginTop: '4px' }}>Through proxy service that removes openid scope</p>
                </div>
              </div>
              <p style={{ marginTop: '8px', fontSize: '12px', color: '#ea580c' }}>
                MFA required for all users
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '24px', marginBottom: '32px' }}>
          <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', padding: '24px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', marginBottom: '12px', color: '#2563eb' }}>🔒</div>
              <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '8px' }}>PKCE Security</h3>
              <p style={{ color: '#6b7280', fontSize: '14px' }}>
                Proof Key for Code Exchange protects against authorization code interception attacks
              </p>
            </div>
          </div>

          <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', padding: '24px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', marginBottom: '12px', color: '#059669' }}>🏢</div>
              <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '8px' }}>LDAP Integration</h3>
              <p style={{ color: '#6b7280', fontSize: '14px' }}>
                Integration with OpenLDAP for international offices
              </p>
            </div>
          </div>

          <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', padding: '24px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', marginBottom: '12px', color: '#dc2626' }}>🔐</div>
              <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '8px' }}>MFA (TOTP)</h3>
              <p style={{ color: '#6b7280', fontSize: '14px' }}>
                Two-factor authentication with Google Authenticator
              </p>
            </div>
          </div>

          <div style={{ backgroundColor: 'white', borderRadius: '8px', boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', padding: '24px' }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: '24px', marginBottom: '12px', color: '#7c3aed' }}>🎯</div>
              <h3 style={{ fontSize: '18px', fontWeight: '600', color: '#1f2937', marginBottom: '8px' }}>Yandex ID</h3>
              <p style={{ color: '#6b7280', fontSize: '14px' }}>
                OAuth 2.0 authentication via Yandex with data consent
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

const App: React.FC = () => { 
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const response = await fetch('http://localhost:5001/api/auth/status', {
          method: 'GET',
          credentials: 'include',
        });

        const data = await response.json();
        setIsAuthenticated(data.isAuthenticated);
      } catch (error) {
        console.error('Auth check failed:', error);
        setIsAuthenticated(false);
      } finally {
        setLoading(false);
      }
    };

    checkAuth();
  }, []);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #eff6ff 0%, #f3e8ff 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ 
            animation: 'spin 1s linear infinite', 
            borderRadius: '50%', 
            height: '64px', 
            width: '64px', 
            borderBottom: '4px solid #2563eb', 
            margin: '0 auto 16px' 
          }}></div>
          <p style={{ fontSize: '20px', color: '#374151' }}>Checking authorization...</p>
        </div>
      </div>
    );
  }

  if (isAuthenticated === null) {
    return (
      <div style={{ minHeight: '100vh', background: 'linear-gradient(135deg, #eff6ff 0%, #f3e8ff 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div style={{ fontSize: '20px', color: '#374151' }}>Loading...</div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <HomePage />;
  }

  return (
    <div>
      <FinalDashboard />
    </div>
  );
};

export default App;