import React, { useEffect, useState, createContext } from 'react';
import ReportPage from './components/ReportPage';

const API_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';
const KEYCLOAK_URL = process.env.REACT_APP_KEYCLOAK_URL || 'http://localhost:8080';
const REALM = process.env.REACT_APP_KEYCLOAK_REALM || 'reports-realm';
const CLIENT_ID = process.env.REACT_APP_KEYCLOAK_CLIENT_ID || 'reports-frontend';

interface AuthState {
  authenticated: boolean;
  username: string | null;
  roles: string[];
  loading: boolean;
}

export const AuthContext = createContext<AuthState>({
  authenticated: false,
  username: null,
  roles: [],
  loading: true,
});

function generateCodeVerifier(): string {
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);
  return btoa(String.fromCharCode.apply(null, Array.from(array)))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

async function generateCodeChallenge(verifier: string): Promise<string> {
  const data = new TextEncoder().encode(verifier);
  const digest = await crypto.subtle.digest('SHA-256', data);
  return btoa(String.fromCharCode.apply(null, Array.from(new Uint8Array(digest))))
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

const App: React.FC = () => {
  const [auth, setAuth] = useState<AuthState>({
    authenticated: false,
    username: null,
    roles: [],
    loading: true,
  });

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');

    if (code) {
      const codeVerifier = sessionStorage.getItem('pkce_code_verifier');
      if (codeVerifier) {
        fetch(`${API_URL}/auth/callback`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            code,
            code_verifier: codeVerifier,
            redirect_uri: window.location.origin + '/',
          }),
        })
          .then((r) => r.json())
          .then((data) => {
            sessionStorage.removeItem('pkce_code_verifier');
            window.history.replaceState({}, '', '/');
            setAuth({
              authenticated: true,
              username: data.username,
              roles: data.roles || [],
              loading: false,
            });
          })
          .catch(() => setAuth((prev: AuthState) => ({ ...prev, loading: false })));
      } else {
        setAuth((prev: AuthState) => ({ ...prev, loading: false }));
      }
    } else {
      fetch(`${API_URL}/auth/session`, { credentials: 'include' })
        .then((r) => {
          if (!r.ok) throw new Error('no session');
          return r.json();
        })
        .then((data) =>
          setAuth({
            authenticated: true,
            username: data.username,
            roles: data.roles || [],
            loading: false,
          })
        )
        .catch(() => setAuth((prev: AuthState) => ({ ...prev, loading: false })));
    }
  }, []);

  const login = async () => {
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = await generateCodeChallenge(codeVerifier);
    sessionStorage.setItem('pkce_code_verifier', codeVerifier);

    const authUrl =
      `${KEYCLOAK_URL}/realms/${REALM}/protocol/openid-connect/auth?` +
      `client_id=${CLIENT_ID}` +
      `&redirect_uri=${encodeURIComponent(window.location.origin + '/')}` +
      `&response_type=code` +
      `&scope=openid` +
      `&code_challenge=${codeChallenge}` +
      `&code_challenge_method=S256`;

    window.location.href = authUrl;
  };

  const logout = async () => {
    await fetch(`${API_URL}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setAuth({ authenticated: false, username: null, roles: [], loading: false });
  };

  if (auth.loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-100">
        Loading...
      </div>
    );
  }

  return (
    <AuthContext.Provider value={auth}>
      <div className="App">
        <ReportPage
          authenticated={auth.authenticated}
          username={auth.username}
          onLogin={login}
          onLogout={logout}
        />
      </div>
    </AuthContext.Provider>
  );
};

export default App;
