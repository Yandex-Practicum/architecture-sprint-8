import { Request, Response, NextFunction } from 'express';
import { createRemoteJWKSet, jwtVerify, JWTPayload } from 'jose';

const KEYCLOAK_URL = process.env.KEYCLOAK_URL ?? 'http://localhost:8080';
const KEYCLOAK_REALM = process.env.KEYCLOAK_REALM ?? 'reports-realm';
const JWKS_URI = `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}/protocol/openid-connect/certs`;

// KEYCLOAK_ISSUER — публичный URL Keycloak (совпадает с полем "iss" в JWT).
// Может отличаться от KEYCLOAK_URL (внутренний Docker-адрес для JWKS).
const ISSUER =
  process.env.KEYCLOAK_ISSUER ??
  `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`;

const JWKS = createRemoteJWKSet(new URL(JWKS_URI));

export interface AuthenticatedRequest extends Request {
  user?: JWTPayload & { email?: string; preferred_username?: string };
}

export async function authMiddleware(
  req: AuthenticatedRequest,
  res: Response,
  next: NextFunction
): Promise<void> {
  const authHeader = req.headers.authorization;

  if (!authHeader?.startsWith('Bearer ')) {
    res.status(401).json({ error: 'Unauthorized: Bearer token required' });
    return;
  }

  const token = authHeader.slice(7);

  try {
    const { payload } = await jwtVerify(token, JWKS, { issuer: ISSUER });
    req.user = payload as AuthenticatedRequest['user'];
    next();
  } catch (err) {
    console.error('JWT verification failed:', err);
    res.status(401).json({ error: 'Unauthorized: Invalid or expired token' });
  }
}
