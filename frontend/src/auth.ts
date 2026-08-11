const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8081';

export interface SessionInfo {
  username: string;
  roles: string[];
  accessTokenExpiresAt: string;
}

export const loginUrl = `${AUTH_URL}/oauth2/authorization/keycloak`;

export async function fetchSession(): Promise<SessionInfo | null> {
  const response = await fetch(`${AUTH_URL}/api/session`, {
    credentials: 'include',
  });

  if (response.status === 401) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Session check failed: ${response.status}`);
  }
  return response.json();
}

function readCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function logout(): void {
  const csrfToken = readCookie('XSRF-TOKEN');
  const form = document.createElement('form');
  form.method = 'POST';
  form.action = `${AUTH_URL}/auth/logout`;

  if (csrfToken) {
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = '_csrf';
    csrfInput.value = csrfToken;
    form.appendChild(csrfInput);
  }

  document.body.appendChild(form);
  form.submit();
}
