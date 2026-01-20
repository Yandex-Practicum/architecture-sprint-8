import os
import random
import uuid
from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt import PyJWKClient

ROLE_PROTHETIC_USER = "prothetic_user"

KEYCLOAK_URL = "http://keycloak:8080"
KEYCLOAK_REALM = "reports-realm"
KEYCLOAK_CERTS_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
KEYCLOAK_PKCE_ALGORITHM = "RS256"

def generate_reports(count = 20):
    data = []
    for i in range(count):
        data.append({
            'uuid': str(uuid.uuid4()),
            'name': f"Report #{i + 1}",
            'created_at': datetime.utcnow().isoformat(),
            'comment': f"Comment for report #{i + 1}"
        })
    return data

#security = HTTPBearer()
#jwks_client = PyJWKClient(KEYCLOAK_CERTS_URL)

#async def verify_token(credentials = Depends(security)):
async def verify_token(credentials = Depends(HTTPBearer())):
    token = credentials.credentials
    try:
#        signing_key = jwks_client.get_signing_key_from_jwt(token)
        signing_key =  PyJWKClient(KEYCLOAK_CERTS_URL).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=[KEYCLOAK_PKCE_ALGORITHM],
            options={"require": ["exp", "iat"]}
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Access token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")

async def require_role(payload = Depends(verify_token)):
    roles = payload.get("realm_access", {}).get("roles", [])
    if ROLE_PROTHETIC_USER not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Missing required role."
        )
    return payload

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/reports")
def get_reports(_ = Depends(require_role)):
    return generate_reports()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
