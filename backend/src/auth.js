import { createRemoteJWKSet, jwtVerify } from 'jose';
import { config } from './config.js';

const jwks = createRemoteJWKSet(new URL(config.keycloakJwksUri));

export function extractBearerToken(header) {
  if (!header) {
    return null;
  }

  const [scheme, token] = header.split(' ');
  if (scheme !== 'Bearer' || !token) {
    return null;
  }

  return token;
}

export function getUserIdFromClaims(claims, claimName = config.reportUserIdClaim) {
  const userId = claims[claimName];
  if (typeof userId !== 'string' || userId.trim() === '') {
    throw new Error(`Token does not contain ${claimName}`);
  }

  return userId;
}

export function assertSelfAccess(authenticatedUserId, requestedUserId) {
  if (requestedUserId && requestedUserId !== authenticatedUserId) {
    const error = new Error('Reports can only be requested for the authenticated user');
    error.statusCode = 403;
    throw error;
  }

  return authenticatedUserId;
}

export async function authenticateRequest(req, _res, next) {
  try {
    const token = extractBearerToken(req.headers.authorization);
    if (!token) {
      const error = new Error('Missing bearer token');
      error.statusCode = 401;
      throw error;
    }

    const { payload } = await jwtVerify(token, jwks, {
      issuer: config.keycloakIssuer,
    });

    req.auth = {
      claims: payload,
      userId: getUserIdFromClaims(payload),
    };

    next();
  } catch (error) {
    error.statusCode ||= 401;
    next(error);
  }
}
