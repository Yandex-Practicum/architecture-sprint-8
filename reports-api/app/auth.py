import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient

from .config import settings

_jwks_client = PyJWKClient(settings.jwks_url)


def get_current_username(authorization: str = Header(default=None)) -> str:
    """Проверяет bearer access_token и возвращает имя аутентифицированного пользователя.

    Подпись, audience, issuer и срок действия проверяются по опубликованным
    ключам Keycloak - reports-api никогда не доверяет идентичности,
    переданной вызывающей стороной.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.removeprefix("Bearer ").strip()

    try:
        signing_key = _jwks_client.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.expected_audience,
            issuer=settings.expected_issuer,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    username = claims.get("preferred_username")
    if not username:
        raise HTTPException(status_code=401, detail="Token missing preferred_username claim")
    return username
