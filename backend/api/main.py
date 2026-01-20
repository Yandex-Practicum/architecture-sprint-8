from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from typing import Dict, List
import httpx
import os
from dotenv import load_dotenv
from datetime import datetime
import random

load_dotenv()

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL")
REALM = os.getenv("KEYCLOAK_REALM")
AUDIENCE = os.getenv("KEYCLOAK_AUDIENCE")

JWKS_URL = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"
ALGORITHMS = ["RS256"]

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer()

# Получаем ключ из JWKS
async def get_public_key():
    async with httpx.AsyncClient() as client:
        r = await client.get(JWKS_URL)
        r.raise_for_status()
        jwks = r.json()
    return jwks["keys"]

# Валидация токена
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> Dict:
    token = credentials.credentials
    try:
        keys = await get_public_key()
        for key in keys:
            try:
                payload = jwt.decode(
                    token,
                    key,
                    algorithms=ALGORITHMS,
                    audience=AUDIENCE,
                    options={"verify_aud": True}
                )
                roles: List[str] = payload.get("realm_access", {}).get("roles", [])
                if "prothetic_user" not in roles:
                    raise HTTPException(status_code=403, detail="Forbidden: missing role")
                return payload
            except JWTError:
                continue
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Token validation error")

# Генерация фейковых отчётов
@app.get("/reports")
async def get_reports(user: Dict = Depends(verify_token)):
    reports = [
        {
            "id": i,
            "title": f"Report #{i}",
            "generated_at": datetime.utcnow().isoformat(),
            "value": round(random.uniform(1000, 5000), 2),
        }
        for i in range(1, 6)
    ]
    return {
        "user": user.get("preferred_username"),
        "reports": reports
    }
