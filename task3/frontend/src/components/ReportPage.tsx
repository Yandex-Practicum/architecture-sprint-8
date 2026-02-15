import React, { useState, useEffect } from 'react';
import Keycloak from 'keycloak-js';

const ReportPage: React.FC = () => {
  const [keycloak, setKeycloak] = useState<Keycloak.KeycloakInstance | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reportUrl, setReportUrl] = useState<string | null>(null);

  useEffect(() => {
    const initKeycloak = async () => {
      const keycloakInstance = new Keycloak({
        url: 'http://localhost:8080',
        realm: 'reports-realm',
        clientId: 'reports-frontend' // Existing client in realm
      });

      try {
        const authenticated = await keycloakInstance.init({
          onLoad: 'login-required',
          checkLoginIframe: false
        });
        setKeycloak(keycloakInstance);
        setAuthenticated(authenticated);
      } catch (error) {
        console.error('Keycloak init error:', error);
      }
    };

    initKeycloak();
  }, []);

  const login = () => {
    keycloak?.login();
  };

  const logout = () => {
    keycloak?.logout();
  };

  const getReport = async () => {
    if (!keycloak) {
      setError('Keycloak not initialized');
      return;
    }

    try {
      // Update token if needed
      await keycloak.updateToken(30);
    } catch (error) {
      setError('Failed to refresh token');
      return;
    }

    if (!keycloak.token) {
      setError('No token available');
      return;
    }

    try {
      setLoading(true);
      setError(null);

      const response = await fetch('http://localhost:8083/reports', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${keycloak.token}`,
          'Content-Type': 'application/json'
        }
      });

      if (!response.ok) {
        if (response.status === 401) {
          setAuthenticated(false);
          throw new Error('Unauthorized. Please login again.');
        }
        throw new Error(`Failed to get report: ${response.statusText}`);
      }

      const data = await response.json();
      setReportUrl(data.report_url);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6">BionicPRO Reports</h1>
          <p className="mb-4 text-gray-600">Please login to access reports</p>
          <button
            onClick={login}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <button
            onClick={logout}
            className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
          >
            Logout
          </button>
        </div>
        <button
          onClick={getReport}
          disabled={loading}
          className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600 disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Get Report'}
        </button>
        {error && <p className="text-red-500 mt-4">{error}</p>}
        {reportUrl && (
          <div className="mt-6 p-4 bg-gray-50 rounded">
            <h2 className="text-lg font-semibold mb-2">Report</h2>
            <a href={reportUrl} target="_blank" rel="noopener noreferrer" className="text-blue-500 underline">
              Download Report
            </a>
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;