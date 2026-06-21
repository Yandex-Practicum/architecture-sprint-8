import crypto from 'node:crypto';
import http from 'node:http';

const config = {
  port: Number(process.env.PORT || 8000),
  frontendUrl: process.env.FRONTEND_URL || 'http://localhost:3000',
  keycloakBrowserUrl: process.env.KEYCLOAK_BROWSER_URL || process.env.KEYCLOAK_URL || 'http://localhost:8080',
  keycloakInternalUrl: process.env.KEYCLOAK_INTERNAL_URL || process.env.KEYCLOAK_URL || 'http://localhost:8080',
  realm: process.env.KEYCLOAK_REALM || 'reports-realm',
  clientId: process.env.KEYCLOAK_CLIENT_ID || 'bionicpro-auth',
  clientSecret: process.env.KEYCLOAK_CLIENT_SECRET || 'bionicpro-auth-secret',
  redirectUri: process.env.AUTH_CALLBACK_URL || 'http://localhost:8000/auth/callback',
  cookieSecure: process.env.AUTH_COOKIE_SECURE !== 'false',
  internalSecret: process.env.INTERNAL_AUTH_SECRET || 'local-internal-secret',
  clickhouseUrl: process.env.CLICKHOUSE_URL || 'http://clickhouse:8123',
  clickhouseDatabase: process.env.CLICKHOUSE_DATABASE || 'bionicpro'
};

const SESSION_COOKIE = 'bp_session';
const STATE_COOKIE = 'bp_auth_state';
const sessions = new Map();
const pendingLogins = new Map();

const discovery = {
  authUrl: `${config.keycloakBrowserUrl}/realms/${config.realm}/protocol/openid-connect/auth`,
  tokenUrl: `${config.keycloakInternalUrl}/realms/${config.realm}/protocol/openid-connect/token`,
  logoutUrl: `${config.keycloakInternalUrl}/realms/${config.realm}/protocol/openid-connect/logout`
};

function randomId(size = 32) {
  return crypto.randomBytes(size).toString('base64url');
}

function sha256Base64Url(value) {
  return crypto.createHash('sha256').update(value).digest('base64url');
}

function parseCookies(req) {
  const raw = req.headers.cookie || '';
  return Object.fromEntries(
    raw
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const index = part.indexOf('=');
        return [part.slice(0, index), decodeURIComponent(part.slice(index + 1))];
      })
  );
}

function cookie(name, value, options = {}) {
  const attrs = [
    `${name}=${encodeURIComponent(value)}`,
    'Path=/',
    'HttpOnly',
    `SameSite=${options.sameSite || 'Lax'}`
  ];

  if (config.cookieSecure) {
    attrs.push('Secure');
  }

  if (options.maxAge !== undefined) {
    attrs.push(`Max-Age=${options.maxAge}`);
  }

  return attrs.join('; ');
}

function clearCookie(name) {
  return cookie(name, '', { maxAge: 0 });
}

function sendJson(res, status, payload, extraHeaders = {}) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': config.frontendUrl,
    'Access-Control-Allow-Credentials': 'true',
    ...extraHeaders
  });
  res.end(JSON.stringify(payload));
}

function redirect(res, location, headers = {}) {
  res.writeHead(302, {
    Location: location,
    ...headers
  });
  res.end();
}

function parseJwt(token) {
  const [, payload] = token.split('.');
  if (!payload) {
    return {};
  }

  return JSON.parse(Buffer.from(payload, 'base64url').toString('utf8'));
}

function getPublicUser(session) {
  return {
    id: session.user.sub,
    username: session.user.preferred_username,
    email: session.user.email,
    roles: session.user.realm_access?.roles || []
  };
}

function escapeSql(value) {
  return String(value ?? '').replaceAll('\\', '\\\\').replaceAll("'", "\\'");
}

async function queryClickHouse(sql) {
  const url = new URL('/', config.clickhouseUrl);
  url.searchParams.set('database', config.clickhouseDatabase);
  url.searchParams.set('query', sql);

  const response = await fetch(url, { method: 'POST' });
  if (!response.ok) {
    const details = await response.text();
    throw new Error(`ClickHouse query failed: ${response.status} ${details}`);
  }
}

async function saveIdentityProfile(user) {
  await queryClickHouse(`
    CREATE TABLE IF NOT EXISTS identity_profiles
    (
      subject String,
      username String,
      email String,
      full_name String,
      identity_provider LowCardinality(String),
      raw_profile String,
      saved_at DateTime
    )
    ENGINE = ReplacingMergeTree(saved_at)
    ORDER BY (identity_provider, subject)
  `);

  const identityProvider = user.identity_provider || user.idp || user.identityProvider || 'keycloak';
  const fullName = user.name || [user.given_name, user.family_name].filter(Boolean).join(' ');
  const rawProfile = JSON.stringify(user);

  await queryClickHouse(`
    INSERT INTO identity_profiles
      (subject, username, email, full_name, identity_provider, raw_profile, saved_at)
    VALUES
      (
        '${escapeSql(user.sub)}',
        '${escapeSql(user.preferred_username)}',
        '${escapeSql(user.email)}',
        '${escapeSql(fullName)}',
        '${escapeSql(identityProvider)}',
        '${escapeSql(rawProfile)}',
        now()
      )
  `);
}

function rotateSession(oldSessionId, session) {
  const newSessionId = randomId();
  sessions.delete(oldSessionId);
  sessions.set(newSessionId, {
    ...session,
    rotatedAt: Date.now()
  });
  return newSessionId;
}

async function readBody(req) {
  const chunks = [];
  for await (const chunk of req) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString('utf8');
}

async function requestTokens(params) {
  const body = new URLSearchParams({
    client_id: config.clientId,
    client_secret: config.clientSecret,
    ...params
  });

  const response = await fetch(discovery.tokenUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`Keycloak token request failed: ${response.status} ${details}`);
  }

  return response.json();
}

async function refreshIfNeeded(session) {
  const now = Math.floor(Date.now() / 1000);
  if (session.accessExpiresAt - 10 > now) {
    return session;
  }

  const tokens = await requestTokens({
    grant_type: 'refresh_token',
    refresh_token: session.refreshToken
  });
  const user = parseJwt(tokens.id_token || tokens.access_token);

  return {
    ...session,
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token || session.refreshToken,
    accessExpiresAt: now + Number(tokens.expires_in || 120),
    refreshExpiresAt: now + Number(tokens.refresh_expires_in || 1800),
    user
  };
}

async function verifySession(req, res, { rotate = true } = {}) {
  const sessionId = parseCookies(req)[SESSION_COOKIE];
  const session = sessionId ? sessions.get(sessionId) : null;

  if (!session) {
    sendJson(res, 401, { error: 'not_authenticated' });
    return null;
  }

  const refreshed = await refreshIfNeeded(session);
  sessions.set(sessionId, refreshed);

  if (!rotate) {
    return { sessionId, session: refreshed, setCookie: null };
  }

  const newSessionId = rotateSession(sessionId, refreshed);
  return {
    sessionId: newSessionId,
    session: refreshed,
    setCookie: cookie(SESSION_COOKIE, newSessionId, { maxAge: refreshed.refreshExpiresAt - Math.floor(Date.now() / 1000) })
  };
}

async function handleLogin(_req, res) {
  const state = randomId();
  const codeVerifier = randomId(64);
  const codeChallenge = sha256Base64Url(codeVerifier);

  pendingLogins.set(state, {
    codeVerifier,
    createdAt: Date.now()
  });

  const authUrl = new URL(discovery.authUrl);
  authUrl.searchParams.set('client_id', config.clientId);
  authUrl.searchParams.set('redirect_uri', config.redirectUri);
  authUrl.searchParams.set('response_type', 'code');
  authUrl.searchParams.set('scope', 'openid profile email');
  authUrl.searchParams.set('state', state);
  authUrl.searchParams.set('code_challenge', codeChallenge);
  authUrl.searchParams.set('code_challenge_method', 'S256');

  redirect(res, authUrl.toString(), {
    'Set-Cookie': cookie(STATE_COOKIE, state, { maxAge: 300 })
  });
}

async function handleCallback(req, res) {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const code = url.searchParams.get('code');
  const state = url.searchParams.get('state');
  const stateCookie = parseCookies(req)[STATE_COOKIE];
  const pending = state ? pendingLogins.get(state) : null;

  if (!code || !state || state !== stateCookie || !pending) {
    redirect(res, `${config.frontendUrl}/?auth_error=invalid_state`, {
      'Set-Cookie': clearCookie(STATE_COOKIE)
    });
    return;
  }

  pendingLogins.delete(state);

  try {
    const tokens = await requestTokens({
      grant_type: 'authorization_code',
      code,
      redirect_uri: config.redirectUri,
      code_verifier: pending.codeVerifier
    });
    const now = Math.floor(Date.now() / 1000);
    const user = parseJwt(tokens.id_token || tokens.access_token);
    await saveIdentityProfile(user);
    const sessionId = randomId();
    const session = {
      accessToken: tokens.access_token,
      refreshToken: tokens.refresh_token,
      accessExpiresAt: now + Number(tokens.expires_in || 120),
      refreshExpiresAt: now + Number(tokens.refresh_expires_in || 1800),
      user,
      createdAt: Date.now(),
      rotatedAt: Date.now()
    };

    sessions.set(sessionId, session);
    redirect(res, config.frontendUrl, {
      'Set-Cookie': [
        clearCookie(STATE_COOKIE),
        cookie(SESSION_COOKIE, sessionId, { maxAge: session.refreshExpiresAt - now })
      ]
    });
  } catch (error) {
    redirect(res, `${config.frontendUrl}/?auth_error=token_exchange_failed`, {
      'Set-Cookie': clearCookie(STATE_COOKIE)
    });
  }
}

async function handleMe(req, res) {
  const result = await verifySession(req, res);
  if (!result) {
    return;
  }

  sendJson(res, 200, { user: getPublicUser(result.session) }, {
    'Set-Cookie': result.setCookie
  });
}

async function handleLogout(req, res) {
  const sessionId = parseCookies(req)[SESSION_COOKIE];
  if (sessionId) {
    sessions.delete(sessionId);
  }

  sendJson(res, 200, { ok: true }, {
    'Set-Cookie': clearCookie(SESSION_COOKIE)
  });
}

async function handleInternalValidate(req, res) {
  if (req.headers['x-internal-auth-secret'] !== config.internalSecret) {
    sendJson(res, 403, { error: 'forbidden' });
    return;
  }

  const body = JSON.parse((await readBody(req)) || '{}');
  const session = body.sessionId ? sessions.get(body.sessionId) : null;

  if (!session) {
    sendJson(res, 401, { error: 'not_authenticated' });
    return;
  }

  const refreshed = await refreshIfNeeded(session);
  sessions.set(body.sessionId, refreshed);
  const newSessionId = rotateSession(body.sessionId, refreshed);
  const rotatedSession = sessions.get(newSessionId);
  const now = Math.floor(Date.now() / 1000);

  sendJson(res, 200, {
    user: getPublicUser(rotatedSession),
    sessionId: newSessionId,
    sessionMaxAge: Math.max(rotatedSession.refreshExpiresAt - now, 0),
    accessTokenExpiresAt: rotatedSession.accessExpiresAt
  });
}

function handleOptions(_req, res) {
  res.writeHead(204, {
    'Access-Control-Allow-Origin': config.frontendUrl,
    'Access-Control-Allow-Credentials': 'true',
    'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type,X-Internal-Auth-Secret'
  });
  res.end();
}

async function router(req, res) {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (req.method === 'OPTIONS') {
      handleOptions(req, res);
      return;
    }

    if (req.method === 'GET' && url.pathname === '/health') {
      sendJson(res, 200, { ok: true });
      return;
    }

    if (req.method === 'GET' && url.pathname === '/auth/login') {
      await handleLogin(req, res);
      return;
    }

    if (req.method === 'GET' && url.pathname === '/auth/callback') {
      await handleCallback(req, res);
      return;
    }

    if (req.method === 'GET' && url.pathname === '/auth/me') {
      await handleMe(req, res);
      return;
    }

    if (req.method === 'POST' && url.pathname === '/auth/logout') {
      await handleLogout(req, res);
      return;
    }

    if (req.method === 'POST' && url.pathname === '/internal/session/validate') {
      await handleInternalValidate(req, res);
      return;
    }

    sendJson(res, 404, { error: 'not_found' });
  } catch (error) {
    sendJson(res, 500, { error: 'server_error', message: error.message });
  }
}

http.createServer(router).listen(config.port, () => {
  console.log(`bionicpro-auth listening on ${config.port}`);
});
