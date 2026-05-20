import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from src.config import JWKS_URL

bearer_scheme = HTTPBearer()

_jwks_keys: list[dict] | None = None


async def _get_jwks_keys() -> list[dict]:
    global _jwks_keys
    if _jwks_keys is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(JWKS_URL, timeout=5)
            resp.raise_for_status()
            _jwks_keys = resp.json().get("keys", [])
    return _jwks_keys


async def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> str:
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        keys = await _get_jwks_keys()
        public_key = next(
            (
                jwt.algorithms.RSAAlgorithm.from_jwk(k)
                for k in keys
                if k.get("kid") == kid
            ),
            None,
        )
        if public_key is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown key id")

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )

        user_id: str | None = payload.get("preferred_username") or payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing user identity in token")

        return user_id

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Invalid token: {exc}")
