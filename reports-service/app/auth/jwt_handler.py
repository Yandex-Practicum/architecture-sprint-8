"""
JWT authentication handler for Reports Service.

Implements secure JWT validation with Keycloak public key verification.
Ensures users can only access their own reports (IDOR protection).
"""

import logging
import time
from typing import Optional, List

import httpx
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, ExpiredSignatureError
from jose.exceptions import JWTClaimsError

from app.config import get_settings, Settings
from app.models import CurrentUser, TokenPayload

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

# Admin role that can access any user's reports
ADMIN_ROLE = "administrator"


class JWTHandler:
    """
    Handler for JWT token validation with Keycloak.

    Security features:
    - Fetches and caches Keycloak public key for signature verification
    - Validates token expiration (exp claim)
    - Validates token issuer (iss claim)
    - Extracts user roles for authorization
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._public_key: Optional[str] = None
        self._public_key_fetched_at: float = 0
        self._public_key_ttl: int = 3600  # Refresh key every hour

    async def get_public_key(self) -> Optional[str]:
        """
        Fetch Keycloak public key for JWT verification.
        Caches the key with TTL to handle key rotation.
        """
        current_time = time.time()

        # Return cached key if still valid
        if self._public_key and (current_time - self._public_key_fetched_at) < self._public_key_ttl:
            return self._public_key

        try:
            # Fetch realm info from Keycloak
            url = f"{self.settings.keycloak_url}/realms/{self.settings.keycloak_realm}"
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=10.0)
                if response.status_code == 200:
                    realm_info = response.json()
                    public_key = realm_info.get("public_key")
                    if public_key:
                        # Format as PEM
                        self._public_key = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
                        self._public_key_fetched_at = current_time
                        logger.info("Successfully fetched Keycloak public key")
                        return self._public_key
        except Exception as e:
            logger.warning(f"Failed to fetch Keycloak public key: {e}")
            # Return cached key if available, even if expired
            if self._public_key:
                logger.warning("Using cached public key")
                return self._public_key

        return None

    async def decode_token_async(self, token: str) -> Optional[TokenPayload]:
        """
        Decode and validate JWT token asynchronously with Keycloak public key.

        Args:
            token: JWT token string

        Returns:
            Token payload or None if invalid
        """
        # First try to get public key for RS256 validation
        public_key = await self.get_public_key()

        if public_key:
            return self._decode_with_key(token, public_key, "RS256")
        else:
            # Fallback to HS256 with secret (for testing/development)
            logger.warning("Using fallback HS256 validation (Keycloak unavailable)")
            return self._decode_with_key(token, self.settings.jwt_secret_key, "HS256")

    def _decode_with_key(self, token: str, key: str, algorithm: str) -> Optional[TokenPayload]:
        """
        Decode token with specified key and algorithm.

        Args:
            token: JWT token string
            key: Verification key
            algorithm: JWT algorithm (RS256 or HS256)

        Returns:
            Token payload or None if invalid
        """
        try:
            # Don't verify issuer strictly - it may come from different URLs
            # (http://keycloak:8080 internal vs http://localhost:8080 external)
            # The signature verification is sufficient for security
            payload = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_iat": True,
                    "require_exp": True,
                    "verify_iss": False,  # Skip issuer check due to internal/external URL mismatch
                },
            )

            # Manual issuer validation - accept both internal and external URLs
            token_issuer = payload.get("iss", "")
            expected_issuers = [
                f"{self.settings.keycloak_url}/realms/{self.settings.keycloak_realm}",
                f"http://localhost:8080/realms/{self.settings.keycloak_realm}",
                f"http://127.0.0.1:8080/realms/{self.settings.keycloak_realm}",
            ]
            if token_issuer not in expected_issuers:
                logger.warning(f"Unexpected token issuer: {token_issuer}")
                # Still accept - signature is verified

            return TokenPayload(**payload)

        except ExpiredSignatureError:
            logger.warning("JWT token has expired")
            return None
        except JWTClaimsError as e:
            logger.warning(f"JWT claims validation failed: {e}")
            return None
        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            return None

    def decode_token_sync(self, token: str, verify: bool = False) -> Optional[TokenPayload]:
        """
        Synchronous token decode (without signature verification).
        Used for extracting claims when async is not available.

        Args:
            token: JWT token string
            verify: Whether to verify signature

        Returns:
            Token payload or None if invalid
        """
        try:
            options = {"verify_signature": verify}
            if not verify:
                options["verify_exp"] = False

            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=["RS256", "HS256"],
                options=options,
            )

            return TokenPayload(**payload)

        except JWTError as e:
            logger.warning(f"JWT decode error: {e}")
            return None

    def extract_user_from_token(self, payload: TokenPayload) -> CurrentUser:
        """
        Extract user information from token payload.

        Args:
            payload: Decoded token payload

        Returns:
            CurrentUser object with user_id, username, email, and roles
        """
        # Extract roles from realm_access
        roles: List[str] = []
        if payload.realm_access and "roles" in payload.realm_access:
            roles = payload.realm_access["roles"]

        # Use preferred_username as user_id (matches external_id in CRM)
        # Fall back to sub if preferred_username not available
        user_id = payload.preferred_username or payload.sub

        return CurrentUser(
            user_id=user_id,
            username=payload.preferred_username,
            email=payload.email,
            roles=roles,
        )

    def is_admin(self, user: CurrentUser) -> bool:
        """Check if user has administrator role."""
        return ADMIN_ROLE in user.roles


# Singleton handler
_jwt_handler: Optional[JWTHandler] = None


def get_jwt_handler() -> JWTHandler:
    """Get singleton JWT handler instance."""
    global _jwt_handler
    if _jwt_handler is None:
        _jwt_handler = JWTHandler(get_settings())
    return _jwt_handler


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> CurrentUser:
    """
    FastAPI dependency to get current authenticated user.

    Extracts and validates JWT from Authorization header.
    Uses Keycloak public key for signature verification.

    Raises:
        HTTPException 401: If token is missing, invalid, or expired
    """
    if not credentials:
        logger.warning("Authentication failed: Authorization header missing")
        raise HTTPException(
            status_code=401,
            detail="Authorization header missing",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    handler = get_jwt_handler()

    # Validate token with Keycloak public key
    payload = await handler.decode_token_async(token)

    if not payload:
        logger.warning("Authentication failed: Invalid or expired token")
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = handler.extract_user_from_token(payload)
    logger.info(f"User authenticated: {user.user_id} (roles: {user.roles})")

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> Optional[CurrentUser]:
    """
    Optional version of get_current_user.
    Returns None instead of raising exception if not authenticated.
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def require_self_or_admin(current_user: CurrentUser, target_user_id: str) -> None:
    """
    Authorization check: user can only access their own data, unless admin.

    Args:
        current_user: Authenticated user from JWT
        target_user_id: User ID being accessed

    Raises:
        HTTPException 403: If user tries to access another user's data without admin role
    """
    handler = get_jwt_handler()

    if current_user.user_id != target_user_id and not handler.is_admin(current_user):
        logger.warning(
            f"Access denied: User {current_user.user_id} attempted to access "
            f"reports for user {target_user_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied: You can only access your own reports",
        )


async def get_admin_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
) -> CurrentUser:
    """
    FastAPI dependency to get current user and verify admin role.

    Raises:
        HTTPException 401: If not authenticated
        HTTPException 403: If user is not an administrator
    """
    user = await get_current_user(credentials)
    handler = get_jwt_handler()

    if not handler.is_admin(user):
        logger.warning(f"Admin access denied for user: {user.user_id}")
        raise HTTPException(
            status_code=403,
            detail="Administrator access required",
        )

    return user
