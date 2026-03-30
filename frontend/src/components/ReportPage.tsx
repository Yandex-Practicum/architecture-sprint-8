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
  user_id?: number;
}

interface ReportRow {
  user_id: number;
  report_date: string;
  session_count: number;
  avg_wear_time_min: number;
  total_gestures: number;
  avg_myosignal_quality: number;
  order_status: string | null;
  prosthesis_model: string | null;
  last_contact_date: string | null;
}

interface GenerateReportResponse {
  user_id: number;
  requested_range: { from: string; to: string };
  actual_range: { from: string | null; to: string | null };
  available_range: { from: string | null; to: string | null };
  data_complete: boolean;
  count: number;
  reports: ReportRow[];
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
  const [reports, setReports] = useState<ReportRow[]>([]);
  const [reportsLoaded, setReportsLoaded] = useState(false);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [availableFrom, setAvailableFrom] = useState<string | null>(null);
  const [availableTo, setAvailableTo] = useState<string | null>(null);
  const [dataComplete, setDataComplete] = useState(true);
  const [actualRange, setActualRange] = useState<{ from: string | null; to: string | null } | null>(null);

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
    setReports([]);
    setReportsLoaded(false);
    setDateFrom('');
    setDateTo('');
    setAvailableFrom(null);
    setAvailableTo(null);
    setDataComplete(true);
    setActualRange(null);
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

  const fetchAvailableRange = useCallback(async () => {
    if (!user?.user_id) return;
    try {
      const params = new URLSearchParams({ user_id: String(user.user_id) });
      const resp = await fetch(`${AUTH_URL}/auth/proxy/reports/date-range?${params}`, {
        credentials: 'include',
      });
      if (resp.ok) {
        const data = await resp.json();
        setAvailableFrom(data.available_from);
        setAvailableTo(data.available_to);
        if (data.available_from && data.available_to) {
          setDateFrom(data.available_from);
          setDateTo(data.available_to);
        }
      }
    } catch {
      // non-critical
    }
  }, [user]);

  useEffect(() => {
    if (authenticated && user?.user_id) {
      fetchAvailableRange();
    }
  }, [authenticated, user, fetchAvailableRange]);

  const generateReport = async () => {
    if (!user?.user_id) {
      setError('User ID not available. Please re-login.');
      return;
    }
    if (!dateFrom || !dateTo) {
      setError('Please select date range.');
      return;
    }
    try {
      setReportLoading(true);
      setError(null);
      setReports([]);
      setReportsLoaded(false);
      setDataComplete(true);
      setActualRange(null);

      const response = await fetch(`${AUTH_URL}/auth/proxy/reports/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          user_id: user.user_id,
          date_from: dateFrom,
          date_to: dateTo,
        }),
      });

      if (response.status === 401) {
        setAuthenticated(false);
        setUser(null);
        setError('Session expired, please login again');
        return;
      }

      if (response.status === 403) {
        setError('Access denied: you can only view your own reports');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to generate report');
      }

      const data: GenerateReportResponse = await response.json();
      setReports(data.reports);
      setReportsLoaded(true);
      setDataComplete(data.data_complete);
      setActualRange(data.actual_range);
      if (data.available_range.from) setAvailableFrom(data.available_range.from);
      if (data.available_range.to) setAvailableTo(data.available_range.to);
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

        <div className="mb-4">
          <h3 className="font-semibold mb-2">Generate Report</h3>
          {availableFrom && availableTo && (
            <p className="text-xs text-gray-500 mb-2">
              Data available: {availableFrom} — {availableTo}
            </p>
          )}
          <div className="flex items-end gap-3">
            <div>
              <label className="block text-xs text-gray-600 mb-1">From</label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="border rounded px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="block text-xs text-gray-600 mb-1">To</label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="border rounded px-2 py-1 text-sm"
              />
            </div>
            <button
              onClick={generateReport}
              disabled={reportLoading}
              className={`px-4 py-1.5 bg-blue-500 text-white text-sm rounded hover:bg-blue-600 ${
                reportLoading ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              {reportLoading ? 'Generating...' : 'Generate Report'}
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded text-sm">
            {error}
          </div>
        )}

        {reportsLoaded && !dataComplete && (
          <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 text-yellow-800 rounded text-sm">
            Data is available only through <strong>{availableTo}</strong>.
            {actualRange?.from && actualRange?.to
              ? ` Report generated for ${actualRange.from} — ${actualRange.to}.`
              : ' No data for the requested period.'
            }
            {' '}The ETL pipeline processes data daily.
          </div>
        )}

        {reportsLoaded && (
          <div className="mt-4">
            {reports.length === 0 ? (
              <p className="text-gray-500">No reports found for the selected period.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm border border-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 border-b text-left">Date</th>
                      <th className="px-3 py-2 border-b text-left">Sessions</th>
                      <th className="px-3 py-2 border-b text-left">Avg Wear (min)</th>
                      <th className="px-3 py-2 border-b text-left">Gestures</th>
                      <th className="px-3 py-2 border-b text-left">Signal Quality</th>
                      <th className="px-3 py-2 border-b text-left">Order Status</th>
                      <th className="px-3 py-2 border-b text-left">Prosthesis</th>
                      <th className="px-3 py-2 border-b text-left">Last Contact</th>
                    </tr>
                  </thead>
                  <tbody>
                    {reports.map((row, idx) => (
                      <tr key={idx} className={idx % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                        <td className="px-3 py-2 border-b">{row.report_date}</td>
                        <td className="px-3 py-2 border-b">{row.session_count}</td>
                        <td className="px-3 py-2 border-b">{row.avg_wear_time_min.toFixed(1)}</td>
                        <td className="px-3 py-2 border-b">{row.total_gestures}</td>
                        <td className="px-3 py-2 border-b">{(row.avg_myosignal_quality * 100).toFixed(0)}%</td>
                        <td className="px-3 py-2 border-b">{row.order_status || '—'}</td>
                        <td className="px-3 py-2 border-b">{row.prosthesis_model || '—'}</td>
                        <td className="px-3 py-2 border-b">{row.last_contact_date || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default ReportPage;
