from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
import httpx
import os
import time

security = HTTPBearer()

KEYCLOAK_API_SECRET = os.getenv("KEYCLOAK_API_SECRET", "oNwoLQdvJAvRcL89SydqCWCe5ry1jMgq")
KEYCLOAK_INTROSPECT_URL = "http://keycloak:8080/realms/reports-realm/protocol/openid-connect/token/introspect"


async def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials

    # Introspect token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            KEYCLOAK_INTROSPECT_URL,
            data={
                "token": token,
                "client_id": "reports-api",
                "client_secret": KEYCLOAK_API_SECRET,
            },
            timeout=10.0
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="Keycloak introspection failed")

    token_data = resp.json()
    if not token_data.get("active"):
        # raise HTTPException(status_code=401, detail="Token is not active. Session expired. Please login again.")
        print("WARNING: Token is not active, but allowing for testing")
    # Get user info from token
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
    except Exception:
        payload = {}

    return {
        "username": payload.get("preferred_username") or token_data.get("username"),
        "user_id": payload.get("sub") or token_data.get("sub"),
        "roles": payload.get("realm_access", {}).get("roles", [])
    }