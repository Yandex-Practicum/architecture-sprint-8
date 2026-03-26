import os
import uuid
import time
import threading
from functools import wraps
from datetime import datetime

import psycopg2
import psycopg2.extras
import requests
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from cryptography.fernet import Fernet

import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
KEYCLOAK_URL = os.environ.get("KEYCLOAK_URL", "http://keycloak:8080")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "reports-realm")
CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "reports-frontend")
SESSION_COOKIE_NAME = "BIONICPRO_SESSION"
SESSION_TTL = int(os.environ.get("SESSION_TTL", "600"))  # 10 minutes
CLEANUP_INTERVAL = 60  # seconds

CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN])

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://bionicpro_user:bionicpro_password@localhost:5434/bionicpro_db")
YANDEX_PROFILE_URL = os.environ.get("YANDEX_PROFILE_URL", "https://login.yandex.ru/info")


def _get_db_connection():
    return psycopg2.connect(DATABASE_URL)


def _save_user_profile(keycloak_user_id, username, email=None, first_name=None, last_name=None):
    conn = _get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_profiles (keycloak_user_id, username, email, first_name, last_name, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (keycloak_user_id) DO UPDATE SET
                     username = EXCLUDED.username,
                     email = COALESCE(EXCLUDED.email, user_profiles.email),
                     first_name = COALESCE(EXCLUDED.first_name, user_profiles.first_name),
                     last_name = COALESCE(EXCLUDED.last_name, user_profiles.last_name),
                     updated_at = EXCLUDED.updated_at""",
                (keycloak_user_id, username, email, first_name, last_name, datetime.utcnow()),
            )
        conn.commit()
    finally:
        conn.close()


def _save_yandex_profile(keycloak_user_id, yandex_data):
    conn = _get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE user_profiles SET
                     yandex_id = %s,
                     yandex_login = %s,
                     display_name = %s,
                     first_name = COALESCE(%s, first_name),
                     last_name = COALESCE(%s, last_name),
                     email = COALESCE(%s, email),
                     phone = %s,
                     avatar_url = %s,
                     profile_fetched_at = %s,
                     updated_at = %s
                   WHERE keycloak_user_id = %s""",
                (
                    yandex_data.get("id"),
                    yandex_data.get("login"),
                    yandex_data.get("display_name"),
                    yandex_data.get("first_name"),
                    yandex_data.get("last_name"),
                    yandex_data.get("default_email"),
                    yandex_data.get("default_phone", {}).get("number") if isinstance(yandex_data.get("default_phone"), dict) else None,
                    f"https://avatars.yandex.net/get-yapic/{yandex_data.get('default_avatar_id')}/islands-200" if yandex_data.get("default_avatar_id") else None,
                    datetime.utcnow(),
                    datetime.utcnow(),
                    keycloak_user_id,
                ),
            )
        conn.commit()
    finally:
        conn.close()


def _get_user_profile(keycloak_user_id):
    conn = _get_db_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM user_profiles WHERE keycloak_user_id = %s", (keycloak_user_id,))
            return cur.fetchone()
    finally:
        conn.close()


def _update_consent(keycloak_user_id, consent_given):
    conn = _get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE user_profiles SET consent_given = %s, consent_given_at = %s, updated_at = %s
                   WHERE keycloak_user_id = %s""",
                (consent_given, datetime.utcnow() if consent_given else None, datetime.utcnow(), keycloak_user_id),
            )
        conn.commit()
    finally:
        conn.close()


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

        request.session_id = session_id
        request.session_data = session_data
        return f(*args, **kwargs)

    return decorated


@app.route("/auth/login", methods=["POST"])
def login():
    """Exchange authorization code + PKCE verifier for tokens via Keycloak, return session cookie."""
    logger.info("=== /auth/login called ===")
    body = request.get_json(silent=True) or {}
    code = body.get("code")
    redirect_uri = body.get("redirect_uri")
    code_verifier = body.get("code_verifier")
    logger.info(f"code={code[:20] if code else None}..., redirect_uri={redirect_uri}, verifier={'yes' if code_verifier else 'no'}")

    if not code or not redirect_uri or not code_verifier:
        logger.error("Missing required params")
        return jsonify({"error": "code, redirect_uri, and code_verifier are required"}), 400

    logger.info(f"Exchanging code at {_token_endpoint()}")
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
        logger.error(f"Token exchange failed: {resp.status_code} {resp.text}")
        return jsonify({"error": "Authentication failed", "details": resp.text}), 401

    token_data = resp.json()
    session_id = _create_session(
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data.get("expires_in", 120),
    )

    # Fetch user info right away so frontend doesn't need a separate /auth/session call
    user_resp = requests.get(
        _userinfo_endpoint(),
        headers={"Authorization": f"Bearer {token_data['access_token']}"},
        timeout=10,
    )
    user_data = {}
    consent_given = False
    if user_resp.status_code == 200:
        user_info = user_resp.json()
        keycloak_user_id = user_info.get("sub")
        user_data = {
            "username": user_info.get("preferred_username"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "roles": user_info.get("realm_access", {}).get("roles", []),
        }
        if keycloak_user_id:
            try:
                _save_user_profile(
                    keycloak_user_id,
                    user_info.get("preferred_username", "unknown"),
                    user_info.get("email"),
                    user_info.get("given_name"),
                    user_info.get("family_name"),
                )
            except Exception:
                pass
            try:
                profile = _get_user_profile(keycloak_user_id)
                if profile:
                    consent_given = profile["consent_given"]
            except Exception:
                pass

    response = make_response(jsonify({
        "authenticated": True,
        "user": user_data,
        "consent_given": consent_given,
    }))
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
    keycloak_user_id = user_info.get("sub")

    # Save/update user profile in DB
    if keycloak_user_id:
        try:
            _save_user_profile(
                keycloak_user_id,
                user_info.get("preferred_username", "unknown"),
                user_info.get("email"),
                user_info.get("given_name"),
                user_info.get("family_name"),
            )
        except Exception:
            pass  # non-critical, don't fail the session check

    # Check if user has given consent
    consent_given = False
    if keycloak_user_id:
        try:
            profile = _get_user_profile(keycloak_user_id)
            if profile:
                consent_given = profile["consent_given"]
        except Exception:
            pass

    response = make_response(jsonify({
        "authenticated": True,
        "user": {
            "username": user_info.get("preferred_username"),
            "email": user_info.get("email"),
            "name": user_info.get("name"),
            "roles": user_info.get("realm_access", {}).get("roles", []),
        },
        "consent_given": consent_given,
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


def _get_keycloak_user_id(access_token):
    resp = requests.get(
        _userinfo_endpoint(),
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json().get("sub")
    return None


def _get_idp_token_from_keycloak(access_token):
    url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/broker/yandex/token"
    resp = requests.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        return data.get("access_token")
    return None


def _fetch_yandex_profile(yandex_token):
    resp = requests.get(
        YANDEX_PROFILE_URL,
        headers={"Authorization": f"OAuth {yandex_token}"},
        params={"format": "json"},
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json()
    return None


@app.route("/auth/consent", methods=["POST"])
@require_session
def give_consent():
    session_data = request.session_data
    keycloak_user_id = _get_keycloak_user_id(session_data["access_token"])
    if not keycloak_user_id:
        response = make_response(jsonify({"error": "Failed to get user identity"}), 500)
        _set_session_cookie(response, request.session_id)
        return response

    body = request.get_json(silent=True) or {}
    consent = body.get("consent", False)

    # Ensure profile exists
    profile = _get_user_profile(keycloak_user_id)
    if not profile:
        user_info_resp = requests.get(
            _userinfo_endpoint(),
            headers={"Authorization": f"Bearer {session_data['access_token']}"},
            timeout=10,
        )
        if user_info_resp.status_code == 200:
            ui = user_info_resp.json()
            _save_user_profile(
                keycloak_user_id,
                ui.get("preferred_username", "unknown"),
                ui.get("email"),
                ui.get("given_name"),
                ui.get("family_name"),
            )

    _update_consent(keycloak_user_id, consent)

    if consent:
        # Fetch Yandex profile if user authenticated via Yandex IdP
        yandex_token = _get_idp_token_from_keycloak(session_data["access_token"])
        if yandex_token:
            yandex_data = _fetch_yandex_profile(yandex_token)
            if yandex_data:
                _save_yandex_profile(keycloak_user_id, yandex_data)

    response = make_response(jsonify({"consent": consent, "saved": True}))
    _set_session_cookie(response, request.session_id)
    return response


@app.route("/auth/profile", methods=["GET"])
@require_session
def get_profile():
    session_data = request.session_data
    keycloak_user_id = _get_keycloak_user_id(session_data["access_token"])
    if not keycloak_user_id:
        response = make_response(jsonify({"error": "Failed to get user identity"}), 500)
        _set_session_cookie(response, request.session_id)
        return response

    profile = _get_user_profile(keycloak_user_id)
    if not profile:
        response = make_response(jsonify({"error": "Profile not found"}), 404)
        _set_session_cookie(response, request.session_id)
        return response

    profile_data = {
        "username": profile["username"],
        "email": profile["email"],
        "first_name": profile["first_name"],
        "last_name": profile["last_name"],
        "display_name": profile["display_name"],
        "avatar_url": profile["avatar_url"],
        "phone": profile["phone"],
        "yandex_login": profile["yandex_login"],
        "consent_given": profile["consent_given"],
        "consent_given_at": profile["consent_given_at"].isoformat() if profile["consent_given_at"] else None,
    }

    response = make_response(jsonify({"profile": profile_data}))
    _set_session_cookie(response, request.session_id)
    return response


@app.route("/auth/fetch-yandex-profile", methods=["POST"])
@require_session
def fetch_yandex_profile():
    session_data = request.session_data
    keycloak_user_id = _get_keycloak_user_id(session_data["access_token"])
    if not keycloak_user_id:
        response = make_response(jsonify({"error": "Failed to get user identity"}), 500)
        _set_session_cookie(response, request.session_id)
        return response

    # Check consent
    profile = _get_user_profile(keycloak_user_id)
    if not profile or not profile["consent_given"]:
        response = make_response(jsonify({"error": "Consent not given"}), 403)
        _set_session_cookie(response, request.session_id)
        return response

    # Get stored IdP token from Keycloak
    yandex_token = _get_idp_token_from_keycloak(session_data["access_token"])
    if not yandex_token:
        response = make_response(jsonify({"error": "No Yandex token available. User may not have logged in via Yandex."}), 400)
        _set_session_cookie(response, request.session_id)
        return response

    yandex_data = _fetch_yandex_profile(yandex_token)
    if not yandex_data:
        response = make_response(jsonify({"error": "Failed to fetch Yandex profile"}), 502)
        _set_session_cookie(response, request.session_id)
        return response

    _save_yandex_profile(keycloak_user_id, yandex_data)

    response = make_response(jsonify({
        "fetched": True,
        "yandex_profile": {
            "id": yandex_data.get("id"),
            "login": yandex_data.get("login"),
            "display_name": yandex_data.get("display_name"),
            "first_name": yandex_data.get("first_name"),
            "last_name": yandex_data.get("last_name"),
            "email": yandex_data.get("default_email"),
        },
    }))
    _set_session_cookie(response, request.session_id)
    return response


@app.route("/auth/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
