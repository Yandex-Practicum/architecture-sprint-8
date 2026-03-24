import logging
from typing import Optional

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt


logger = logging.getLogger(__name__)


class KeycloakAuthenticator:
    """Fetches JWKS from Keycloak and validates bearer tokens."""

    def __init__(self, well_known_url: str, audience: Optional[str] = None, issuer_override: Optional[str] = None) -> None:
        if not well_known_url:
            raise ValueError("KEYCLOAK_WELL_KNOWN_URL must be configured")

        self.well_known_url = well_known_url.rstrip("/")
        self.audience = audience
        self.jwks_uri: Optional[str] = None
        self.issuer: Optional[str] = None
        self.jwks_keys = []
        self.issuer_override = issuer_override
        self.refresh_metadata()

    def refresh_metadata(self) -> None:
        """Load OIDC metadata and keys from Keycloak."""
        try:
            with httpx.Client(timeout=5) as client:
                metadata_response = client.get(self.well_known_url)
                metadata_response.raise_for_status()
                metadata = metadata_response.json()

                jwks_response = client.get(metadata["jwks_uri"])
                jwks_response.raise_for_status()
                self.jwks_keys = jwks_response.json().get("keys", [])

                self.jwks_uri = metadata["jwks_uri"]
                self.issuer = self.issuer_override or metadata.get("issuer")
        except Exception as exc:  # pragma: no cover - startup failure path
            logger.exception("Failed to refresh Keycloak metadata")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication service unavailable",
            ) from exc

    def _get_signing_key(self, kid: str):
        key = next((key for key in self.jwks_keys if key.get("kid") == kid), None)
        if key is None:
            self.refresh_metadata()
            key = next((key for key in self.jwks_keys if key.get("kid") == kid), None)
        return key

    def validate_token(self, token: str) -> dict:
        """Validate a JWT and return its payload."""
        try:
            unverified_header = jwt.get_unverified_header(token)
        except JWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token header") from exc

        signing_key = self._get_signing_key(unverified_header.get("kid"))
        if signing_key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown signing key")

        options = {"verify_aud": bool(self.audience), "verify_iss": bool(self.issuer)}

        try:
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=[unverified_header.get("alg", "RS256")],
                audience=self.audience if self.audience else None,
                issuer=self.issuer if self.issuer else None,
                options=options,
            )
        except JWTError as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token validation failed") from exc

        return payload