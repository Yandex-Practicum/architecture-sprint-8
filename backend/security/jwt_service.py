import jwt
from fastapi import HTTPException, Header, status
from config import JWT_PUBLIC_KEY, JWT_AUDIENCE, JWT_ISSUER

def get_current_user_id(authorization: str = Header(...)) -> str:  # возвращаем str
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header must be Bearer token",
        )

    token = authorization.split(" ", 1)[1]

    try:
        payload = jwt.decode(
            token,
            JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            options={"verify_aud": False},
            issuer=JWT_ISSUER,
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")

    sub = payload.get("sub")
    if sub is None:
        raise HTTPException(status_code=401, detail="No user id in token")

    return sub  # просто строка UUID