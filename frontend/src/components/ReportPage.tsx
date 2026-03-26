import React, { useState, useEffect, useCallback } from 'react';

const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8000';
const KEYCLOAK_URL = process.env.REACT_APP_KEYCLOAK_URL || 'http://localhost:8080';
const KEYCLOAK_REALM = process.env.REACT_APP_KEYCLOAK_REALM || 'reports-realm';
const CLIENT_ID = process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'reports-frontend';
const REDIRECT_URI = window.location.origin + '/';

function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return btoa(String.fromCharCode.apply(null, Array.from(array)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return btoa(String.fromCharCode.apply(null, Array.from(new Uint8Array(digest))))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

interface UserInfo {
  username: string;
  email: string;
  name: string;
  roles: string[];
}

interface UserProfile {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  display_name: string;
  avatar_url: string;
  phone: string;
  yandex_login: string;
  consent_given: boolean;
  consent_given_at: string | null;
}

const ReportPage: React.FC = () => {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [consentGiven, setConsentGiven] = useState(false);
  const [showConsentDialog, setShowConsentDialog] = useState(false);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileLoading, setProfileLoading] = useState(false);

  const checkSession = useCallback(async () => {
    try {
      const resp = await fetch(`${AUTH_URL}/auth/session`, {
        credentials: 'include',
      });
      if (resp.ok) {
        const data = await resp.json();
        setAuthenticated(true);
        setUser(data.user);
        setConsentGiven(data.consent_given || false);
        if (!data.consent_given) {
          setShowConsentDialog(true);
        }
      } else {
        setAuthenticated(false);
        setUser(null);
      }
    } catch {
      setAuthenticated(false);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleCallback = useCallback(async () => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    const storedVerifier = sessionStorage.getItem('pkce_code_verifier');

    if (code && storedVerifier) {
      // Clear immediately to prevent double-call from StrictMode
      sessionStorage.removeItem('pkce_code_verifier');
      window.history.replaceState({}, document.title, '/');
      try {
        const resp = await fetch(`${AUTH_URL}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            code,
            redirect_uri: REDIRECT_URI,
            code_verifier: storedVerifier,
          }),
        });

        if (resp.ok) {
          const data = await resp.json();
          setAuthenticated(true);
          setUser(data.user);
          setConsentGiven(data.consent_given || false);
          if (!data.consent_given) {
            setShowConsentDialog(true);
          }
          setLoading(false);
          return true;
        } else {
          setError('Authentication failed');
        }
      } catch {
        setError('Authentication failed');
      }
    }
    return false;
  }, []);

  useEffect(() => {
    const init = async () => {
      const handled = await handleCallback();
      if (!handled) {
        await checkSession();
      }
    };
    init();
  }, [handleCallback, checkSession]);

  const login = async () => {
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    sessionStorage.setItem('pkce_code_verifier', codeVerifier);

    const authUrl = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/auth?` +
      `client_id=${encodeURIComponent(CLIENT_ID)}` +
      `&response_type=code` +
      `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}` +
      `&code_challenge=${encodeURIComponent(codeChallenge)}` +
      `&code_challenge_method=S256` +
      `&scope=openid`;

    window.location.href = authUrl;
  };

  const loginWithYandex = async () => {
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    sessionStorage.setItem('pkce_code_verifier', codeVerifier);

    const authUrl = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/auth?` +
      `client_id=${encodeURIComponent(CLIENT_ID)}` +
      `&response_type=code` +
      `&redirect_uri=${encodeURIComponent(REDIRECT_URI)}` +
      `&code_challenge=${encodeURIComponent(codeChallenge)}` +
      `&code_challenge_method=S256` +
      `&scope=openid` +
      `&kc_idp_hint=yandex`;

    window.location.href = authUrl;
  };

  const logout = async () => {
    try {
      await fetch(`${AUTH_URL}/auth/logout`, {
        method: 'POST',
        credentials: 'include',
      });
    } catch {
      // ignore
    }
    setAuthenticated(false);
    setUser(null);
    setConsentGiven(false);
    setProfile(null);
    setShowConsentDialog(false);
  };

  const handleConsent = async (consent: boolean) => {
    try {
      const resp = await fetch(`${AUTH_URL}/auth/consent`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ consent }),
      });
      if (resp.ok) {
        setConsentGiven(consent);
        setShowConsentDialog(false);
      }
    } catch {
      setError('Failed to save consent');
    }
  };

  const fetchProfile = async () => {
    setProfileLoading(true);
    try {
      const resp = await fetch(`${AUTH_URL}/auth/profile`, {
        credentials: 'include',
      });
      if (resp.ok) {
        const data = await resp.json();
        setProfile(data.profile);
      }
    } catch {
      setError('Failed to fetch profile');
    } finally {
      setProfileLoading(false);
    }
  };

  const downloadReport = async () => {
    try {
      setReportLoading(true);
      setError(null);

      const response = await fetch(`${AUTH_URL}/auth/proxy/reports`, {
        credentials: 'include',
      });

      if (response.status === 401) {
        setAuthenticated(false);
        setUser(null);
        setError('Session expired, please login again');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to fetch report');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setReportLoading(false);
    }
  };

  if (loading) {
    return <div>Loading...</div>;
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md">
          <h1 className="text-2xl font-bold mb-6 text-center">BionicPRO</h1>
          <div className="flex flex-col gap-3">
            <button
              onClick={login}
              className="px-6 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Login
            </button>
            <button
              onClick={loginWithYandex}
              className="px-6 py-2 bg-yellow-400 text-black rounded hover:bg-yellow-500 font-medium"
            >
              Login with Yandex ID
            </button>
          </div>
        </div>
        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
      </div>
    );
  }

  if (showConsentDialog) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <div className="p-8 bg-white rounded-lg shadow-md max-w-md">
          <h2 className="text-xl font-bold mb-4">Consent Required</h2>
          <p className="text-gray-700 mb-4">
            BionicPRO would like to access and store your profile data
            (name, email, phone) from your Yandex account for the prosthetics service.
          </p>
          <p className="text-gray-600 text-sm mb-6">
            This data will be used to personalize your experience and provide
            prosthetics-related services. You can revoke consent at any time.
          </p>
          <div className="flex gap-3 justify-end">
            <button
              onClick={() => handleConsent(false)}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
            >
              Decline
            </button>
            <button
              onClick={() => handleConsent(true)}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              Allow
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Usage Reports</h1>
          <div className="flex items-center gap-4">
            <span className="text-sm text-gray-600">{user?.username}</span>
            <button
              onClick={fetchProfile}
              disabled={profileLoading}
              className="px-3 py-1 text-sm bg-green-100 text-green-700 rounded hover:bg-green-200"
            >
              {profileLoading ? 'Loading...' : 'My Profile'}
            </button>
            <button
              onClick={logout}
              className="px-3 py-1 text-sm bg-gray-200 rounded hover:bg-gray-300"
            >
              Logout
            </button>
          </div>
        </div>

        {profile && (
          <div className="mb-6 p-4 bg-gray-50 rounded-lg">
            <h3 className="font-semibold mb-2">Profile</h3>
            <div className="flex items-start gap-4">
              {profile.avatar_url && (
                <img src={profile.avatar_url} alt="Avatar" className="w-16 h-16 rounded-full" />
              )}
              <div className="text-sm text-gray-700 space-y-1">
                <p><span className="font-medium">Name:</span> {profile.display_name || `${profile.first_name || ''} ${profile.last_name || ''}`}</p>
                <p><span className="font-medium">Email:</span> {profile.email || 'N/A'}</p>
                {profile.yandex_login && (
                  <p><span className="font-medium">Yandex:</span> {profile.yandex_login}</p>
                )}
                {profile.phone && (
                  <p><span className="font-medium">Phone:</span> {profile.phone}</p>
                )}
                <p><span className="font-medium">Consent:</span> {profile.consent_given ? 'Given' : 'Not given'}</p>
              </div>
            </div>
          </div>
        )}

        <button
          onClick={downloadReport}
          disabled={reportLoading}
          className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
            reportLoading ? 'opacity-50 cursor-not-allowed' : ''
          }`}
        >
          {reportLoading ? 'Generating Report...' : 'Download Report'}
        </button>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
