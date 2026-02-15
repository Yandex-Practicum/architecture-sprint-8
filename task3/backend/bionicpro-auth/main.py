from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
import redis
import json
import uuid
import secrets
from cryptography.fernet import Fernet
import base64
from datetime import datetime, timedelta
import os

app = FastAPI()

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
KEYCLOAK_EXTERNAL_URL = "http://localhost:8080"
KEYCLOAK_INTERNAL_URL = "http://keycloak:8080"
KEYCLOAK_REALM = "reports-realm"
CLIENT_ID = "reports-api"
CLIENT_SECRET = "oNwoLQdvJAvRcL89SydqCWCe5ry1jMgq"
REDIRECT_URI = "http://localhost:8081/auth/callback"

# Redis
redis_client = redis.Redis(host='redis', port=6379, decode_responses=True)

# Encryption key for refresh tokens
ENCRYPTION_KEY = base64.urlsafe_b64encode(secrets.token_bytes(32))
fernet = Fernet(ENCRYPTION_KEY)

# Session storage (in-memory for refresh tokens)
sessions = {}

@app.get("/auth/login")
async def login():
    state = str(uuid.uuid4())
    auth_url = f"{KEYCLOAK_EXTERNAL_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "openid profile email",
        "state": state
    }
    url = requests.Request('GET', auth_url, params=params).prepare().url
    return RedirectResponse(url)

@app.get("/auth/callback")
async def callback(code: str, state: str):
    # Exchange code for tokens
    token_url = f"{KEYCLOAK_INTERNAL_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
    data = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "redirect_uri": REDIRECT_URI
    }
    resp = requests.post(token_url, data=data)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Token exchange failed")
    
    tokens = resp.json()
    access_token = tokens['access_token']
    refresh_token = tokens['refresh_token']
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Encrypt refresh token
    encrypted_refresh = fernet.encrypt(refresh_token.encode()).decode()
    
    # Store in memory (or secure storage)
    sessions[session_id] = {
        'refresh_token': encrypted_refresh,
        'created_at': datetime.now().isoformat()
    }
    
    # Store access token in Redis with expiration
    redis_client.setex(f"session:{session_id}:access_token", 120, access_token)
    
    # Create response with redirect and cookie
    response = Response(status_code=302)
    response.headers["Location"] = "http://localhost:3000"
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=False,  # Set to False for dev mode without HTTPS
        samesite="lax",  # More permissive than "strict"
        max_age=3600  # 1 hour
    )
    
    return response

def get_current_session(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return session_id

def rotate_session(session_id: str, response: Response):
    # Generate new session ID
    new_session_id = str(uuid.uuid4())
    
    # Move data to new session
    sessions[new_session_id] = sessions.pop(session_id)
    
    # Move Redis data
    access_token = redis_client.get(f"session:{session_id}:access_token")
    if access_token:
        redis_client.delete(f"session:{session_id}:access_token")
        redis_client.setex(f"session:{new_session_id}:access_token", 120, access_token)
    
    # Update cookie
    response.set_cookie(
        key="session_id",
        value=new_session_id,
        httponly=True,
        secure=False,  # Set to False for dev mode without HTTPS
        samesite="lax",  # More permissive than "strict"
        max_age=3600
    )
    
    return new_session_id

def ensure_valid_access_token(session_id: str):
    access_token = redis_client.get(f"session:{session_id}:access_token")
    if not access_token:
        # Try to refresh
        if session_id not in sessions:
            raise HTTPException(status_code=401, detail="Session expired")
        
        encrypted_refresh = sessions[session_id]['refresh_token']
        refresh_token = fernet.decrypt(encrypted_refresh.encode()).decode()
        
        token_url = f"{KEYCLOAK_INTERNAL_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "refresh_token": refresh_token
        }
        resp = requests.post(token_url, data=data)
        if resp.status_code != 200:
            del sessions[session_id]
            raise HTTPException(status_code=401, detail="Refresh failed")
        
        new_tokens = resp.json()
        access_token = new_tokens['access_token']
        new_refresh = new_tokens.get('refresh_token', refresh_token)
        
        # Update stored tokens
        encrypted_new_refresh = fernet.encrypt(new_refresh.encode()).decode()
        sessions[session_id]['refresh_token'] = encrypted_new_refresh
        redis_client.setex(f"session:{session_id}:access_token", 120, access_token)
    
    return access_token

@app.get("/api/protected")
async def protected(session_id: str = Depends(get_current_session), response: Response = None):
    # Rotate session
    new_session_id = rotate_session(session_id, response)
    
    # Ensure valid access token
    access_token = ensure_valid_access_token(new_session_id)
    
    return {"message": "Protected resource", "session_id": new_session_id}

@app.get("/api/reports")
async def reports(session_id: str = Depends(get_current_session), response: Response = None):
    # Rotate session
    new_session_id = rotate_session(session_id, response)
    
    # Ensure valid access token
    access_token = ensure_valid_access_token(new_session_id)
    
    # Here would be the actual report generation logic
    # For now, return mock data
    return {"reports": ["Report 1", "Report 2"], "session_id": new_session_id}

@app.post("/auth/logout")
async def logout(session_id: str = Depends(get_current_session), response: Response = None):
    # Revoke tokens
    if session_id in sessions:
        encrypted_refresh = sessions[session_id]['refresh_token']
        refresh_token = fernet.decrypt(encrypted_refresh.encode()).decode()
        
        revoke_url = f"{KEYCLOAK_INTERNAL_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/revoke"
        data = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "token": refresh_token
        }
        requests.post(revoke_url, data=data)
        
        del sessions[session_id]
    
    redis_client.delete(f"session:{session_id}:access_token")
    
    response.delete_cookie("session_id")
    return {"message": "Logged out"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)