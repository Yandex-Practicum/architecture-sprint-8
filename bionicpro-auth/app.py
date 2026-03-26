import os
import uuid
import time
import threading
from functools import wraps

import requests
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from cryptography.fernet import Fernet

app = Flask(__name__)

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "reports-realm")
CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "reports-frontend")
SESSION_COOKIE_NAME = "BIONICPRO_SESSION"
SESSION_TTL = int(os.environ.get("SESSION_TTL", "600"))  # 10 minutes
CLEANUP_INTERVAL = 60  # seconds

CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN])

# Encryption key for refresh tokens at rest
_encryption_key = os.environ.get("ENCRYPTION_KEY")
if not _encryption_key:
    _encryption_key = Fernet.generate_key().decode()
fernet = Fernet(_encryption_key.encode() if isinstance(_encryption_key, str) else _encryption_key)

# In-memory session store: session_id -> { access_token, refresh_token_encrypted, expires_at, created_at }
_sessions: dict[str, dict] = {}
_lock = threading.Lock()


def _token_endpoint():
    return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"


def _userinfo_endpoint():
    return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"


def _logout_endpoint():
    return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/logout"


def _create_session(access_token: str, refresh_token: str, expires_in: int) -> str:
    session_id = uuid.uuid4().hex
    encrypted_rt = fernet.encrypt(refresh_token.encode()).decode()
    with _lock:
        _sessions[session_id] = {
            "access_token": access_token,
            "refresh_token_encrypted": encrypted_rt,
            "expires_at": time.time() + expires_in,
            "created_at": time.time(),
        }
    return session_id


def _get_session(session_id: str) -> dict | None:
    with _lock:
        return _sessions.get(session_id)


def _delete_session(session_id: str):
    with _lock:
        _sessions.pop(session_id, None)


def _rotate_session(old_session_id: str) -> str:
    """Rotate session ID to prevent session fixation. Moves token data to a new session ID."""
    new_session_id = uuid.uuid4().hex
    with _lock:
        data = _sessions.pop(old_session_id, None)
        if data:
            _sessions[new_session_id] = data
    return new_session_id


def _refresh_access_token(session_data: dict) -> dict | None:
    refresh_token = fernet.decrypt(session_data["refresh_token_encrypted"].encode()).decode()
    resp = requests.post(
        _token_endpoint(),
        data={
            "grant_type": "refresh_token",
            "client_id": CLIENT_ID,
            "refresh_token": refresh_token,
        },
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    return resp.json()


def _set_session_cookie(response, session_id: str):
    is_secure = os.environ.get("SECURE_COOKIE", "false").lower() == "true"
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        secure=is_secure,
        samesite="Lax",
        max_age=SESSION_TTL,
        path="/",
    )
    return response


def _cleanup_expired_sessions():
    now = time.time()
    with _lock:
        expired = [sid for sid, data in _sessions.items() if now - data["created_at"] > SESSION_TTL]
        for sid in expired:
            del _sessions[sid]


def _start_cleanup_thread():
    def loop():
        while True:
            time.sleep(CLEANUP_INTERVAL)
            _cleanup_expired_sessions()

    t = threading.Thread(target=loop, daemon=True)
    t.start()


_start_cleanup_thread()


def require_session(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if not session_id:
            return jsonify({"error": "No session"}), 401

        session_data = _get_session(session_id)
        if not session_data:
            return jsonify({"error": "Invalid or expired session"}), 401

        # Check if access_token expired, refresh if needed
        if time.time() >= session_data["expires_at"]:
            token_data = _refresh_access_token(session_data)
            if not token_data:
                _delete_session(session_id)
                resp = make_response(jsonify({"error": "Session expired, please login again"}), 401)
                resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
                return resp
            session_data["access_token"] = token_data["access_token"]
            encrypted_rt = fernet.encrypt(token_data["refresh_token"].encode()).decode()
            session_data["refresh_token_encrypted"] = encrypted_rt
            session_data["expires_at"] = time.time() + token_data.get("expires_in", 120)

        # Session rotation: rebind tokens to new session ID
        new_session_id = _rotate_session(session_id)

        request.session_id = new_session_id
        request.session_data = session_data
        return f(*args, **kwargs)

    return decorated


@app.route("/auth/login", methods=["POST"])
def login():
    """Exchange authorization code + PKCE verifier for tokens via Keycloak, return session cookie."""
    body = request.get_json(silent=True) or {}
    code = body.get("code")
    redirect_uri = body.get("redirect_uri")
    code_verifier = body.get("code_verifier")

    if not code or not redirect_uri or not code_verifier:
        return jsonify({"error": "code, redirect_uri, and code_verifier are required"}), 400

    resp = requests.post(
        _token_endpoint(),
        data={
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=10,
    )

    if resp.status_code != 200:
        return jsonify({"error": "Authentication failed", "details": resp.text}), 401

    token_data = resp.json()
    session_id = _create_session(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data.get("expires_in", 120),
    )

    response = make_response(jsonify({"authenticated": True}))
    _set_session_cookie(response, session_id)
    return response


@app.route("/auth/logout", methods=["POST"])
def logout():
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        session_data = _get_session(session_id)
        if session_data:
            # Notify Keycloak about logout
            try:
                refresh_token = fernet.decrypt(
                    session_data["refresh_token_encrypted"].encode()
                ).decode()
                requests.post(
                    _logout_endpoint(),
                    data={
                        "client_id": CLIENT_ID,
                        "refresh_token": refresh_token,
                    },
                    timeout=5,
                )
            except Exception:
                pass
            _delete_session(session_id)

    resp = make_response(jsonify({"logged_out": True}))
    resp.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return resp


@app.route("/auth/session", methods=["GET"])
@require_session
def session_info():
    """Check session validity and return user info. Rotates session on each call."""
    session_data = request.session_data
    # Fetch user info from Keycloak
    resp = requests.get(
        _userinfo_endpoint(),
        headers={"Authorization": f"Bearer {session_data['access_token']}"},
        timeout=10,
    )
    if resp.status_code != 200:
        return jsonify({"error": "Failed to fetch user info"}), 500

    user_info = resp.json()
    response = make_response(jsonify({
        "authenticated": True,
        "user": {
            "username": user_info.get("preferred_username"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "roles": user_info.get("realm_access", {}).get("roles", []),
        },
    }))
    _set_session_cookie(response, request.session_id)
    return response


@app.route("/auth/proxy/reports", methods=["GET"])
@require_session
def proxy_reports():
    """Proxy request to reports API with the server-side access token."""
    session_data = request.session_data
    api_url = os.environ.get("REPORTS_API_URL", "http://localhost:8001")
    try:
        resp = requests.get(
            f"{api_url}/reports",
            headers={"Authorization": f"Bearer {session_data['access_token']}"},
            timeout=30,
        )
        response = make_response(resp.content, resp.status_code)
        response.headers["Content-Type"] = resp.headers.get("Content-Type", "application/json")
    except requests.RequestException as e:
        response = make_response(jsonify({"error": "Upstream service unavailable"}), 502)

    _set_session_cookie(response, request.session_id)
    return response


@app.route("/auth/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
