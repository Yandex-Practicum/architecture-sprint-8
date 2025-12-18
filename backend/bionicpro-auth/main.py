from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from passlib.context import CryptContext
import httpx
import redis
import os
import uuid
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BionicPRO Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("SECRET_KEY", "bionicpro-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 2

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

redis_client = redis.Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", 6379)),
    password=os.getenv("REDIS_PASSWORD", ""),
    db=int(os.getenv("REDIS_DB", 0)),
    decode_responses=True
)

KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")
CLIENT_ID = os.getenv("CLIENT_ID", "backend-auth")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "Y2MCU5BjY8tzCajrWtFLKTINH7kffiHG")

ACCESS_TOKEN_EXPIRE_MINUTES = 2


class TokenData:
    def __init__(self, access_token: str, refresh_token: str, expires_in: int):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_in = expires_in


class UserInfo:
    def __init__(self, sub: str, preferred_username: str, email: str,
                 user_id: int, crm_user_id: Optional[int], roles: list):
        self.sub = sub
        self.preferred_username = preferred_username
        self.email = email
        self.user_id = user_id
        self.crm_user_id = crm_user_id
        self.roles = roles


class Session:
    def __init__(self, session_id: str, auth_code: str, access_token: str,
                 refresh_token: str, expires_at: datetime, user_info: UserInfo):
        self.session_id = session_id
        self.auth_code = auth_code
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = expires_at
        self.user_info = user_info


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


async def get_current_user(request: Request) -> UserInfo:
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")

    try:
        session_data = redis_client.get(f"session:{session_id}")
        if not session_data:
            raise HTTPException(status_code=401, detail="Invalid session")

        import json
        session_dict = json.loads(session_data)
        user_info = UserInfo(
            sub=session_dict['user_info']['sub'],
            preferred_username=session_dict['user_info']['preferred_username'],
            email=session_dict['user_info']['email'],
            user_id=session_dict['user_info']['user_id'],
            crm_user_id=session_dict['user_info'].get('crm_user_id'),
            roles=session_dict['user_info']['roles']
        )
        return user_info
    except Exception as e:
        logger.error(f"Error getting current user: {e}")
        raise HTTPException(status_code=401, detail="Invalid session")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/login")
async def login():
    auth_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "scope": "openid bionic-pro.all",
        "redirect_uri": "http://localhost:5001/api/auth/callback"
    }

    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    redirect_url = f"{auth_url}?{query_string}"

    return RedirectResponse(url=redirect_url)


@app.get("/api/auth/logout")
async def logout(request: Request, response: Response):
    """Logout endpoint"""
    session_id = request.cookies.get("session_id")
    if session_id:
        redis_client.delete(f"session:{session_id}")

        response.set_cookie(
            key="session_id",
            value="",
            max_age=0,
            path="/",
            httponly=True,
            secure=False,
            samesite="lax"
        )

    return RedirectResponse(url="http://localhost:3000")


@app.get("/api/auth/callback")
async def handle_callback(request: Request, response: Response):
    """Handle OAuth callback"""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        return RedirectResponse(url="http://localhost:3000?error=no_code")

    existing_session_key = f"auth_code:{code}"
    existing_session_id = redis_client.get(existing_session_key)

    if existing_session_id:
        response.set_cookie(
            key="session_id",
            value=existing_session_id,
            max_age=24 * 60 * 60,  # 24 hours
            path="/",
            httponly=True,
            secure=False,
            samesite="lax"
        )
        return RedirectResponse(url="http://localhost:3000")

    try:
        token_data = await exchange_code_for_tokens(code)

        session_id = str(uuid.uuid4())
        session = Session(
            session_id=session_id,
            auth_code=code,
            access_token=token_data.access_token,
            refresh_token=token_data.refresh_token,
            expires_at=datetime.utcnow() + timedelta(seconds=token_data.expires_in),
            user_info=None
        )

        user_info = await get_user_info(token_data.access_token)
        session.user_info = user_info

        session_dict = {
            "session_id": session.session_id,
            "auth_code": session.auth_code,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "expires_at": session.expires_at.isoformat(),
            "user_info": {
                "sub": user_info.sub,
                "preferred_username": user_info.preferred_username,
                "email": user_info.email,
                "user_id": user_info.user_id,
                "crm_user_id": user_info.crm_user_id,
                "roles": user_info.roles
            }
        }

        redis_client.setex(
            f"session:{session_id}",
            24 * 60 * 60,
            str(session_dict)
        )

        redis_client.setex(
            existing_session_key,
            5 * 60,
            session_id
        )

        response.set_cookie(
            key="session_id",
            value=session_id,
            max_age=24 * 60 * 60,
            path="/",
            httponly=True,
            secure=False,
            samesite="lax"
        )

        return RedirectResponse(url="http://localhost:3000")

    except Exception as e:
        logger.error(f"Error in callback: {e}")
        return RedirectResponse(url="http://localhost:3000?error=login_failed")


async def exchange_code_for_tokens(code: str) -> TokenData:
    async with httpx.AsyncClient() as client:
        url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": code,
            "redirect_uri": "http://localhost:5001/api/auth/callback"
        }

        response = await client.post(url, data=data)

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Token exchange failed: {response.text}")

        token_data = response.json()
        return TokenData(
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            expires_in=token_data["expires_in"]
        )


async def get_user_info(access_token: str) -> UserInfo:
    async with httpx.AsyncClient() as client:
        url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"
        headers = {"Authorization": f"Bearer {access_token}"}

        response = await client.get(url, headers=headers)

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"User info request failed: {response.text}")

        user_data = response.json()

        crm_user_id = None
        if "crm_user_id" in user_data:
            try:
                crm_user_id = int(user_data["crm_user_id"])
            except (ValueError, TypeError):
                pass

        roles = user_data.get("roles", [])

        return UserInfo(
            sub=user_data.get("sub", ""),
            preferred_username=user_data.get("preferred_username", ""),
            email=user_data.get("email", ""),
            user_id=int(user_data.get("user_id", 0)),
            crm_user_id=crm_user_id,
            roles=roles
        )


@app.get("/api/auth/status")
async def get_auth_status(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id:
        return {"isAuthenticated": False}

    try:
        session_data = redis_client.get(f"session:{session_id}")
        if not session_data:
            return {"isAuthenticated": False}

        import json
        session_dict = json.loads(session_data)
        user_info = session_dict['user_info']

        return {
            "isAuthenticated": True,
            "name": user_info['preferred_username'],
            "username": user_info['preferred_username'],
            "userId": user_info['user_id'],
            "crm_user_id": user_info.get('crm_user_id')
        }
    except Exception as e:
        logger.error(f"Error checking auth status: {e}")
        return {"isAuthenticated": False}


@app.get("/api/auth/me")
async def get_user_info_endpoint(request: Request, current_user: UserInfo = Depends(get_current_user)):
    return {
        "id": current_user.sub,
        "username": current_user.preferred_username,
        "email": current_user.email,
        "roles": current_user.roles,
        "userId": current_user.user_id,
        "crm_user_id": current_user.crm_user_id
    }


@app.post("/api/auth/refresh")
async def refresh_token(request: Request, response: Response):
    session_id = request.cookies.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="No session found")

    try:
        session_data = redis_client.get(f"session:{session_id}")
        if not session_data:
            raise HTTPException(status_code=401, detail="Invalid session")

        import json
        session_dict = json.loads(session_data)

        async with httpx.AsyncClient() as client:
            url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
            data = {
                "grant_type": "refresh_token",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": session_dict["refresh_token"]
            }

            response = await client.post(url, data=data)

            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Failed to refresh token")

            token_data = response.json()

            new_session_dict = session_dict.copy()
            new_session_dict["access_token"] = token_data["access_token"]
            new_session_dict["expires_at"] = (
                        datetime.utcnow() + timedelta(seconds=token_data["expires_in"])).isoformat()

            redis_client.setex(
                f"session:{session_id}",
                24 * 60 * 60,
                str(new_session_dict)
            )

            return {"message": "Token refreshed successfully"}

    except Exception as e:
        logger.error(f"Error refreshing token: {e}")
        raise HTTPException(status_code=401, detail="Failed to refresh token")


@app.get("/api/reports")
async def get_reports(request: Request, current_user: UserInfo = Depends(get_current_user)):
    if not current_user.crm_user_id:
        raise HTTPException(status_code=403, detail="Reports not available for this user (no CRM ID)")

    try:
        async with httpx.AsyncClient() as client:
            url = "http://reports-api:5003/api/v1/reports"
            headers = {
                "Authorization": f"Bearer {current_user}",  # This will need to be fixed
                "X-User-ID": str(current_user.crm_user_id)
            }

            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to get reports")

            return response.json()

    except Exception as e:
        logger.error(f"Error getting reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to get reports")


@app.post("/api/reports/generate")
async def generate_reports(request: Request, current_user: UserInfo = Depends(get_current_user)):
    try:
        async with httpx.AsyncClient() as client:
            url = "http://reports-api:5003/api/v1/reports/generate"
            headers = {
                "Authorization": f"Bearer {current_user}"
            }

            response = await client.post(url, headers=headers)

            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail="Failed to generate reports")

            return response.json()

    except Exception as e:
        logger.error(f"Error generating reports: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate reports")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=5001)
