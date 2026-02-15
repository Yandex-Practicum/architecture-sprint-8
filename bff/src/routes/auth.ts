import { Router, Request, Response } from 'express';
import axios from 'axios';
import { config } from '../config';
import { generateCodeVerifier, generateCodeChallenge, generateState } from '../pkce';

const router = Router();

declare module 'express-session' {
  interface SessionData {
    codeVerifier?: string;
    state?: string;
    accessToken?: string;
    refreshToken?: string;
    expiresAt?: number;
    userInfo?: any;
  }
}

router.get('/login', (req: Request, res: Response) => {
  try {
    const codeVerifier = generateCodeVerifier();
    const codeChallenge = generateCodeChallenge(codeVerifier);
    const state = generateState();

    req.session.codeVerifier = codeVerifier;
    req.session.state = state;

    const authUrl = new URL(
      `${config.keycloak.publicUrl}/realms/${config.keycloak.realm}/protocol/openid-connect/auth`
    );
    
    authUrl.searchParams.append('client_id', config.keycloak.clientId);
    authUrl.searchParams.append('redirect_uri', `${config.bffUrl}/auth/callback`);
    authUrl.searchParams.append('response_type', 'code');
    authUrl.searchParams.append('scope', 'openid profile email');
    authUrl.searchParams.append('state', state);
    authUrl.searchParams.append('code_challenge', codeChallenge);
    authUrl.searchParams.append('code_challenge_method', 'S256');

    console.log('Redirecting to Keycloak:', authUrl.toString());
    
    res.redirect(authUrl.toString());
  } catch (error) {
    console.error('Login error:', error);
    res.status(500).json({ error: 'Failed to initiate login' });
  }
});

router.get('/callback', async (req: Request, res: Response) => {
  try {
    const { code, state } = req.query;

    if (!state || state !== req.session.state) {
      return res.status(400).json({ error: 'Invalid state parameter' });
    }

    if (!code) {
      return res.status(400).json({ error: 'Authorization code not provided' });
    }

    const codeVerifier = req.session.codeVerifier;
    if (!codeVerifier) {
      return res.status(400).json({ error: 'Code verifier not found in session' });
    }

    const tokenUrl = `${config.keycloak.url}/realms/${config.keycloak.realm}/protocol/openid-connect/token`;
    
    const tokenResponse = await axios.post(
      tokenUrl,
      new URLSearchParams({
        grant_type: 'authorization_code',
        client_id: config.keycloak.clientId,
        client_secret: config.keycloak.clientSecret,
        code: code as string,
        redirect_uri: `${config.bffUrl}/auth/callback`,
        code_verifier: codeVerifier,
      }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    const { access_token, refresh_token, expires_in } = tokenResponse.data;

    req.session.accessToken = access_token;
    req.session.refreshToken = refresh_token;
    req.session.expiresAt = Date.now() + expires_in * 1000;

    try {
      const userInfoResponse = await axios.get(
        `${config.keycloak.url}/realms/${config.keycloak.realm}/protocol/openid-connect/userinfo`,
        {
          headers: {
            Authorization: `Bearer ${access_token}`,
          },
        }
      );
      req.session.userInfo = userInfoResponse.data;
    } catch (error) {
      console.error('Failed to fetch user info:', error);
    }

    delete req.session.codeVerifier;
    delete req.session.state;

    console.log('Authentication successful, redirecting to frontend');
    
    res.redirect(`${config.frontendUrl}?authenticated=true`);
  } catch (error) {
    console.error('Callback error:', error);
    res.redirect(`${config.frontendUrl}?error=authentication_failed`);
  }
});

router.get('/session', (req: Request, res: Response) => {
  if (!req.session.accessToken) {
    return res.status(401).json({ authenticated: false });
  }

  const now = Date.now();
  const expiresAt = req.session.expiresAt || 0;
  
  if (now >= expiresAt) {
    return res.status(401).json({ 
      authenticated: false, 
      message: 'Token expired' 
    });
  }

  res.json({
    authenticated: true,
    user: req.session.userInfo,
    expiresAt: req.session.expiresAt,
  });
});

router.post('/refresh', async (req: Request, res: Response) => {
  try {
    const refreshToken = req.session.refreshToken;
    
    if (!refreshToken) {
      return res.status(401).json({ error: 'No refresh token available' });
    }

    const tokenUrl = `${config.keycloak.url}/realms/${config.keycloak.realm}/protocol/openid-connect/token`;
    
    const tokenResponse = await axios.post(
      tokenUrl,
      new URLSearchParams({
        grant_type: 'refresh_token',
        client_id: config.keycloak.clientId,
        client_secret: config.keycloak.clientSecret,
        refresh_token: refreshToken,
      }),
      {
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
      }
    );

    const { access_token, refresh_token, expires_in } = tokenResponse.data;

    req.session.accessToken = access_token;
    req.session.refreshToken = refresh_token || refreshToken;
    req.session.expiresAt = Date.now() + expires_in * 1000;

    res.json({ 
      success: true,
      expiresAt: req.session.expiresAt 
    });
  } catch (error) {
    console.error('Token refresh error:', error);
    req.session.destroy(() => {});
    res.status(401).json({ error: 'Failed to refresh token' });
  }
});

router.post('/logout', async (req: Request, res: Response) => {
  try {
    const refreshToken = req.session.refreshToken;

    if (refreshToken) {
      try {
        const logoutUrl = `${config.keycloak.url}/realms/${config.keycloak.realm}/protocol/openid-connect/logout`;
        await axios.post(
          logoutUrl,
          new URLSearchParams({
            client_id: config.keycloak.clientId,
            client_secret: config.keycloak.clientSecret,
            refresh_token: refreshToken,
          }),
          {
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
            },
          }
        );
      } catch (error) {
        console.error('Failed to revoke token in Keycloak:', error);
      }
    }

    req.session.destroy((err) => {
      if (err) {
        console.error('Session destruction error:', err);
      }
    });

    res.json({ success: true, message: 'Logged out successfully' });
  } catch (error) {
    console.error('Logout error:', error);
    res.status(500).json({ error: 'Failed to logout' });
  }
});

export default router;
