import os
import secrets
import hashlib
import base64
import json
import time
from functools import wraps
from urllib.parse import urlencode
from flask import Flask, request, jsonify, redirect, make_response
from flask_cors import CORS
import redis
import requests
from cryptography.fernet import Fernet
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)

# Configure CORS to allow requests from frontend
CORS(app,
     origins=[os.getenv('FRONTEND_URL', 'http://localhost:3000')],
     supports_credentials=True,
     allow_headers=['Content-Type', 'Authorization'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])

# Configuration
KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://keycloak:8080')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'reports-realm')
KEYCLOAK_PUBLIC_URL = os.getenv('KEYCLOAK_PUBLIC_URL', KEYCLOAK_URL)
CLIENT_ID = os.getenv('CLIENT_ID', 'bionicpro-auth')
REDIRECT_URI = os.getenv('REDIRECT_URI', 'http://localhost:8000/auth/callback')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
KEYCLOAK_SCOPES = os.getenv('KEYCLOAK_SCOPES', 'openid')
REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
SESSION_COOKIE_NAME = 'BIONICPRO_SESSION'
SESSION_LIFETIME = 14400  # 4 hours - comfortable work session without re-login
ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')

# PostgreSQL configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://bionicpro_user:bionicpro_password@localhost:5434/bionicpro_db')

# Yandex ID configuration
YANDEX_CLIENT_ID = os.getenv('YANDEX_CLIENT_ID')
YANDEX_CLIENT_SECRET = os.getenv('YANDEX_CLIENT_SECRET')
YANDEX_USERINFO_URL = 'https://login.yandex.ru/info'

# Redis client
redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)


def get_db_connection():
    """Get PostgreSQL database connection."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)


def get_user_profile(keycloak_user_id):
    """Get user profile from database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM user_profiles WHERE keycloak_user_id = %s",
            (keycloak_user_id,)
        )
        profile = cur.fetchone()
        cur.close()
        conn.close()
        return dict(profile) if profile else None
    except Exception as e:
        app.logger.error(f"Error getting user profile: {e}")
        return None


def save_user_profile(profile_data):
    """Save or update user profile in database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute(
            """
            INSERT INTO user_profiles (
                keycloak_user_id, identity_provider, yandex_id, yandex_login,
                yandex_avatar_id, email, first_name, last_name, display_name,
                phone, avatar_url, consent_given, consent_given_at, consent_scopes,
                last_login_at
            ) VALUES (
                %(keycloak_user_id)s, %(identity_provider)s, %(yandex_id)s, %(yandex_login)s,
                %(yandex_avatar_id)s, %(email)s, %(first_name)s, %(last_name)s, %(display_name)s,
                %(phone)s, %(avatar_url)s, %(consent_given)s, %(consent_given_at)s, %(consent_scopes)s,
                CURRENT_TIMESTAMP
            )
            ON CONFLICT (keycloak_user_id) DO UPDATE SET
                identity_provider = EXCLUDED.identity_provider,
                yandex_id = COALESCE(EXCLUDED.yandex_id, user_profiles.yandex_id),
                yandex_login = COALESCE(EXCLUDED.yandex_login, user_profiles.yandex_login),
                yandex_avatar_id = COALESCE(EXCLUDED.yandex_avatar_id, user_profiles.yandex_avatar_id),
                email = COALESCE(EXCLUDED.email, user_profiles.email),
                first_name = COALESCE(EXCLUDED.first_name, user_profiles.first_name),
                last_name = COALESCE(EXCLUDED.last_name, user_profiles.last_name),
                display_name = COALESCE(EXCLUDED.display_name, user_profiles.display_name),
                phone = COALESCE(EXCLUDED.phone, user_profiles.phone),
                avatar_url = COALESCE(EXCLUDED.avatar_url, user_profiles.avatar_url),
                consent_given = COALESCE(EXCLUDED.consent_given, user_profiles.consent_given),
                consent_given_at = COALESCE(EXCLUDED.consent_given_at, user_profiles.consent_given_at),
                consent_scopes = COALESCE(EXCLUDED.consent_scopes, user_profiles.consent_scopes),
                last_login_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            profile_data
        )

        result = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        return result['id'] if result else None
    except Exception as e:
        app.logger.error(f"Error saving user profile: {e}")
        return None


def log_consent(user_profile_id, client_id, scopes, action, ip_address=None, user_agent=None):
    """Log consent action to history."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO consent_history (user_profile_id, client_id, scopes, action, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (user_profile_id, client_id, scopes, action, ip_address, user_agent)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        app.logger.error(f"Error logging consent: {e}")


def get_keycloak_userinfo(access_token):
    """Get user info from Keycloak userinfo endpoint."""
    config = get_keycloak_openid_config()
    userinfo_endpoint = config.get('userinfo_endpoint')

    if not userinfo_endpoint:
        return None

    response = requests.get(
        userinfo_endpoint,
        headers={'Authorization': f'Bearer {access_token}'}
    )

    if response.status_code == 200:
        return response.json()
    return None


def get_yandex_profile_data(yandex_access_token):
    """Get additional profile data from Yandex API."""
    if not yandex_access_token:
        return None

    response = requests.get(
        YANDEX_USERINFO_URL,
        headers={'Authorization': f'OAuth {yandex_access_token}'},
        params={'format': 'json'}
    )

    if response.status_code == 200:
        return response.json()
    return None


def get_broker_token_from_keycloak(access_token, idp_alias):
    """Get the brokered identity provider token from Keycloak."""
    # This requires the user to have 'broker' scope and read-token role
    url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/broker/{idp_alias}/token"

    response = requests.get(
        url,
        headers={'Authorization': f'Bearer {access_token}'}
    )

    if response.status_code == 200:
        return response.json()
    return None


def build_avatar_url(avatar_id):
    """Build Yandex avatar URL from avatar ID."""
    if not avatar_id:
        return None
    return f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200"

def load_encryption_key():
    """Load and validate the Fernet encryption key from environment."""
    if ENCRYPTION_KEY:
        key_bytes = ENCRYPTION_KEY.encode()
        try:
            Fernet(key_bytes)
            return key_bytes
        except ValueError:
            app.logger.warning(
                "Invalid ENCRYPTION_KEY provided; generating a new key for this instance."
            )
    return Fernet.generate_key()


# Encryption for refresh tokens
fernet = fernet = Fernet(load_encryption_key())


def generate_pkce_pair():
    """Generate PKCE code_verifier and code_challenge."""
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')
    return code_verifier, code_challenge


def generate_session_id():
    """Generate a secure session ID."""
    return secrets.token_urlsafe(32)


def encrypt_token(token):
    """Encrypt a token for secure storage."""
    return fernet.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token):
    """Decrypt a stored token."""
    return fernet.decrypt(encrypted_token.encode()).decode()


def get_session_data(session_id):
    """Get session data from Redis."""
    data = redis_client.get(f"session:{session_id}")
    if data:
        return json.loads(data)
    return None


def save_session_data(session_id, data, ttl=SESSION_LIFETIME):
    """Save session data to Redis."""
    redis_client.setex(f"session:{session_id}", ttl, json.dumps(data))


def delete_session(session_id):
    """Delete a session from Redis."""
    redis_client.delete(f"session:{session_id}")


def create_session_cookie(response, session_id):
    """Create HTTP-only, Secure session cookie."""
    response.set_cookie(
        SESSION_COOKIE_NAME,
        session_id,
        httponly=True,
        secure=os.getenv('SECURE_COOKIES', 'false').lower() == 'true',
        samesite='Lax',
        max_age=SESSION_LIFETIME
    )
    return response


def get_keycloak_openid_config():
    """Get Keycloak OpenID configuration."""
    url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"
    response = requests.get(url)
    return response.json()


def exchange_code_for_tokens(code, code_verifier):
    """Exchange authorization code for tokens using PKCE."""
    config = get_keycloak_openid_config()
    token_endpoint = config['token_endpoint']

    data = {
        'grant_type': 'authorization_code',
        'client_id': CLIENT_ID,
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'code_verifier': code_verifier
    }

    response = requests.post(token_endpoint, data=data)
    if response.status_code == 200:
        return response.json()
    return None


def refresh_access_token(refresh_token):
    """Refresh access token using refresh token."""
    config = get_keycloak_openid_config()
    token_endpoint = config['token_endpoint']

    data = {
        'grant_type': 'refresh_token',
        'client_id': CLIENT_ID,
        'refresh_token': refresh_token
    }

    response = requests.post(token_endpoint, data=data)
    if response.status_code == 200:
        return response.json()
    return None


def rotate_session(old_session_id, session_data):
    """Rotate session ID to prevent session fixation attacks."""
    new_session_id = generate_session_id()

    # Delete old session
    delete_session(old_session_id)

    # Save data with new session ID
    save_session_data(new_session_id, session_data)

    return new_session_id


def require_session(f):
    """Decorator to require valid session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.cookies.get(SESSION_COOKIE_NAME)
        if not session_id:
            return jsonify({'error': 'No session'}), 401

        session_data = get_session_data(session_id)
        if not session_data:
            return jsonify({'error': 'Invalid session'}), 401

        # Check if access token needs refresh
        if session_data.get('access_token_expires_at', 0) < time.time():
            try:
                refresh_token = decrypt_token(session_data['encrypted_refresh_token'])
                tokens = refresh_access_token(refresh_token)

                if tokens:
                    session_data['access_token'] = tokens['access_token']
                    session_data['access_token_expires_at'] = time.time() + tokens.get('expires_in', 120)

                    if 'refresh_token' in tokens:
                        session_data['encrypted_refresh_token'] = encrypt_token(tokens['refresh_token'])
                else:
                    # Refresh failed, session is invalid
                    delete_session(session_id)
                    return jsonify({'error': 'Session expired'}), 401
            except Exception as e:
                delete_session(session_id)
                return jsonify({'error': 'Session expired'}), 401

        # Session rotation for session fixation prevention
        new_session_id = rotate_session(session_id, session_data)

        # Store session data in request context
        request.session_data = session_data
        request.new_session_id = new_session_id

        return f(*args, **kwargs)
    return decorated_function


@app.route('/auth/login', methods=['GET'])
def login():
    """Initiate OAuth2 PKCE login flow."""
    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(32)

    # Store PKCE verifier and state temporarily
    redis_client.setex(f"pkce:{state}", 300, code_verifier)

    auth_endpoint = (
        f"{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"
    )

    query_params = {
        'client_id': CLIENT_ID,
        'redirect_uri': REDIRECT_URI,
        'response_type': 'code',
        'scope': KEYCLOAK_SCOPES,
        'state': state,
        'code_challenge': code_challenge,
        'code_challenge_method': 'S256'
    }

    auth_url = f"{auth_endpoint}?{urlencode(query_params)}"

    return redirect(auth_url)


@app.route('/auth/callback', methods=['GET'])
def callback():
    """Handle OAuth2 callback and exchange code for tokens."""
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')

    if error:
        return redirect(f"{FRONTEND_URL}?error={error}")

    if not code or not state:
        return redirect(f"{FRONTEND_URL}?error=missing_params")

    # Retrieve PKCE verifier
    code_verifier = redis_client.get(f"pkce:{state}")
    redis_client.delete(f"pkce:{state}")

    if not code_verifier:
        return redirect(f"{FRONTEND_URL}?error=invalid_state")

    # Exchange code for tokens
    tokens = exchange_code_for_tokens(code, code_verifier)

    if not tokens:
        return redirect(f"{FRONTEND_URL}?error=token_exchange_failed")

    # Create session
    session_id = generate_session_id()
    session_data = {
        'access_token': tokens['access_token'],
        'access_token_expires_at': time.time() + tokens.get('expires_in', 120),
        'encrypted_refresh_token': encrypt_token(tokens['refresh_token']),
        'id_token': tokens.get('id_token'),
        'created_at': time.time()
    }

    save_session_data(session_id, session_data)

    # Get user info from Keycloak and save profile
    try:
        userinfo = get_keycloak_userinfo(tokens['access_token'])
        if userinfo:
            identity_provider = userinfo.get('identity_provider')
            keycloak_user_id = userinfo.get('sub')

            # Build profile data
            profile_data = {
                'keycloak_user_id': keycloak_user_id,
                'identity_provider': identity_provider,
                'email': userinfo.get('email'),
                'first_name': userinfo.get('given_name'),
                'last_name': userinfo.get('family_name'),
                'display_name': userinfo.get('display_name') or userinfo.get('name'),
                'phone': userinfo.get('phone_number'),
                'yandex_id': userinfo.get('yandex_id'),
                'yandex_login': userinfo.get('preferred_username') if identity_provider == 'yandex' else None,
                'yandex_avatar_id': userinfo.get('yandex_avatar_id'),
                'avatar_url': build_avatar_url(userinfo.get('yandex_avatar_id')),
                'consent_given': True,  # Consent was given during OAuth flow
                'consent_given_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'consent_scopes': tokens.get('scope', '').split() if tokens.get('scope') else None
            }

            # If authenticated via Yandex, try to get additional data from Yandex API
            if identity_provider == 'yandex':
                try:
                    broker_token = get_broker_token_from_keycloak(tokens['access_token'], 'yandex')
                    if broker_token and broker_token.get('access_token'):
                        yandex_profile = get_yandex_profile_data(broker_token['access_token'])
                        if yandex_profile:
                            # Enrich profile with Yandex data
                            profile_data['yandex_id'] = yandex_profile.get('id')
                            profile_data['yandex_login'] = yandex_profile.get('login')
                            profile_data['yandex_avatar_id'] = yandex_profile.get('default_avatar_id')
                            profile_data['avatar_url'] = build_avatar_url(yandex_profile.get('default_avatar_id'))
                            profile_data['email'] = profile_data['email'] or yandex_profile.get('default_email')
                            profile_data['first_name'] = profile_data['first_name'] or yandex_profile.get('first_name')
                            profile_data['last_name'] = profile_data['last_name'] or yandex_profile.get('last_name')
                            profile_data['display_name'] = profile_data['display_name'] or yandex_profile.get('display_name')
                            if yandex_profile.get('default_phone'):
                                profile_data['phone'] = yandex_profile['default_phone'].get('number')
                except Exception as e:
                    app.logger.warning(f"Could not fetch Yandex profile data: {e}")

            # Save profile to database
            profile_id = save_user_profile(profile_data)
            if profile_id:
                # Log consent
                log_consent(
                    profile_id,
                    CLIENT_ID,
                    profile_data['consent_scopes'] or [],
                    'granted',
                    request.remote_addr,
                    request.headers.get('User-Agent')
                )
                app.logger.info(f"Saved profile for user {keycloak_user_id}")
    except Exception as e:
        app.logger.error(f"Error processing user profile: {e}")

    # Create response with session cookie and success parameter
    # Use HTML with JavaScript redirect instead of HTTP redirect
    # to ensure cookie is set before redirecting to frontend
    redirect_url = f"{FRONTEND_URL}?auth=success"
    html = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login Successful</title>
    </head>
    <body>
        <p>Login successful. Redirecting...</p>
        <script>
            window.location.href = "{redirect_url}";
        </script>
    </body>
    </html>
    '''
    response = make_response(html, 200)
    response.headers['Content-Type'] = 'text/html'
    create_session_cookie(response, session_id)

    return response


@app.route('/auth/logout', methods=['POST'])
def logout():
    """Logout and invalidate session."""
    session_id = request.cookies.get(SESSION_COOKIE_NAME)

    if session_id:
        session_data = get_session_data(session_id)

        if session_data:
            # Logout from Keycloak
            try:
                config = get_keycloak_openid_config()
                logout_endpoint = config.get('end_session_endpoint')

                if logout_endpoint and session_data.get('id_token'):
                    requests.get(
                        logout_endpoint,
                        params={'id_token_hint': session_data['id_token']}
                    )
            except Exception:
                pass

        delete_session(session_id)

    response = make_response(jsonify({'status': 'logged_out'}))
    response.delete_cookie(SESSION_COOKIE_NAME)
    return response


@app.route('/auth/session', methods=['GET'])
@require_session
def get_session():
    """Get current session info (without exposing tokens)."""
    session_data = request.session_data
    new_session_id = request.new_session_id

    # Decode ID token to get user info (without exposing actual tokens)
    user_info = {}
    if session_data.get('id_token'):
        try:
            # Decode JWT payload (without verification - just for display)
            payload = session_data['id_token'].split('.')[1]
            # Add padding if needed
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            user_info = json.loads(base64.urlsafe_b64decode(payload))
        except Exception:
            pass

    response = make_response(jsonify({
        'authenticated': True,
        'user': {
            'sub': user_info.get('sub'),
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'preferred_username': user_info.get('preferred_username'),
            'given_name': user_info.get('given_name'),
            'family_name': user_info.get('family_name')
        }
    }))

    # Update session cookie with rotated session ID
    create_session_cookie(response, new_session_id)

    return response


@app.route('/auth/profile', methods=['GET'])
@require_session
def get_profile():
    """Get user profile from database."""
    session_data = request.session_data
    new_session_id = request.new_session_id

    # Get user ID from id_token
    user_id = None
    if session_data.get('id_token'):
        try:
            payload = session_data['id_token'].split('.')[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            token_data = json.loads(base64.urlsafe_b64decode(payload))
            user_id = token_data.get('sub')
        except Exception:
            pass

    if not user_id:
        response = make_response(jsonify({'error': 'User ID not found'}), 400)
        create_session_cookie(response, new_session_id)
        return response

    # Get profile from database
    profile = get_user_profile(user_id)

    if not profile:
        # Try to fetch from Keycloak and save
        userinfo = get_keycloak_userinfo(session_data['access_token'])
        if userinfo:
            profile_data = {
                'keycloak_user_id': user_id,
                'identity_provider': userinfo.get('identity_provider'),
                'email': userinfo.get('email'),
                'first_name': userinfo.get('given_name'),
                'last_name': userinfo.get('family_name'),
                'display_name': userinfo.get('display_name') or userinfo.get('name'),
                'phone': userinfo.get('phone_number'),
                'yandex_id': userinfo.get('yandex_id'),
                'yandex_login': None,
                'yandex_avatar_id': userinfo.get('yandex_avatar_id'),
                'avatar_url': build_avatar_url(userinfo.get('yandex_avatar_id')),
                'consent_given': True,
                'consent_given_at': time.strftime('%Y-%m-%d %H:%M:%S'),
                'consent_scopes': None
            }
            save_user_profile(profile_data)
            profile = get_user_profile(user_id)

    if not profile:
        response = make_response(jsonify({'error': 'Profile not found'}), 404)
        create_session_cookie(response, new_session_id)
        return response

    # Remove sensitive fields and convert datetime objects
    safe_profile = {
        'id': profile.get('id'),
        'email': profile.get('email'),
        'first_name': profile.get('first_name'),
        'last_name': profile.get('last_name'),
        'display_name': profile.get('display_name'),
        'phone': profile.get('phone'),
        'avatar_url': profile.get('avatar_url'),
        'identity_provider': profile.get('identity_provider'),
        'yandex_id': profile.get('yandex_id'),
        'consent_given': profile.get('consent_given'),
        'created_at': profile.get('created_at').isoformat() if profile.get('created_at') else None,
        'last_login_at': profile.get('last_login_at').isoformat() if profile.get('last_login_at') else None
    }

    response = make_response(jsonify({'profile': safe_profile}))
    create_session_cookie(response, new_session_id)
    return response


@app.route('/auth/consent', methods=['POST'])
@require_session
def update_consent():
    """Update user consent settings."""
    session_data = request.session_data
    new_session_id = request.new_session_id

    data = request.get_json()
    if not data:
        response = make_response(jsonify({'error': 'No data provided'}), 400)
        create_session_cookie(response, new_session_id)
        return response

    # Get user ID from id_token
    user_id = None
    if session_data.get('id_token'):
        try:
            payload = session_data['id_token'].split('.')[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            token_data = json.loads(base64.urlsafe_b64decode(payload))
            user_id = token_data.get('sub')
        except Exception:
            pass

    if not user_id:
        response = make_response(jsonify({'error': 'User ID not found'}), 400)
        create_session_cookie(response, new_session_id)
        return response

    profile = get_user_profile(user_id)
    if not profile:
        response = make_response(jsonify({'error': 'Profile not found'}), 404)
        create_session_cookie(response, new_session_id)
        return response

    consent_given = data.get('consent_given', True)
    scopes = data.get('scopes', [])

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        if consent_given:
            cur.execute(
                """
                UPDATE user_profiles
                SET consent_given = TRUE, consent_given_at = CURRENT_TIMESTAMP, consent_scopes = %s
                WHERE keycloak_user_id = %s
                """,
                (scopes, user_id)
            )
            action = 'granted'
        else:
            cur.execute(
                """
                UPDATE user_profiles
                SET consent_given = FALSE, consent_scopes = NULL
                WHERE keycloak_user_id = %s
                """,
                (user_id,)
            )
            action = 'revoked'

        conn.commit()
        cur.close()
        conn.close()

        # Log consent action
        log_consent(
            profile['id'],
            CLIENT_ID,
            scopes,
            action,
            request.remote_addr,
            request.headers.get('User-Agent')
        )

        response = make_response(jsonify({'status': 'success', 'action': action}))
        create_session_cookie(response, new_session_id)
        return response
    except Exception as e:
        app.logger.error(f"Error updating consent: {e}")
        response = make_response(jsonify({'error': 'Failed to update consent'}), 500)
        create_session_cookie(response, new_session_id)
        return response


@app.route('/auth/consent/history', methods=['GET'])
@require_session
def get_consent_history():
    """Get user's consent history."""
    session_data = request.session_data
    new_session_id = request.new_session_id

    # Get user ID from id_token
    user_id = None
    if session_data.get('id_token'):
        try:
            payload = session_data['id_token'].split('.')[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += '=' * padding
            token_data = json.loads(base64.urlsafe_b64decode(payload))
            user_id = token_data.get('sub')
        except Exception:
            pass

    if not user_id:
        response = make_response(jsonify({'error': 'User ID not found'}), 400)
        create_session_cookie(response, new_session_id)
        return response

    profile = get_user_profile(user_id)
    if not profile:
        response = make_response(jsonify({'error': 'Profile not found'}), 404)
        create_session_cookie(response, new_session_id)
        return response

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT client_id, scopes, action, created_at
            FROM consent_history
            WHERE user_profile_id = %s
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (profile['id'],)
        )
        history = cur.fetchall()
        cur.close()
        conn.close()

        history_list = [
            {
                'client_id': row['client_id'],
                'scopes': row['scopes'],
                'action': row['action'],
                'created_at': row['created_at'].isoformat() if row['created_at'] else None
            }
            for row in history
        ]

        response = make_response(jsonify({'history': history_list}))
        create_session_cookie(response, new_session_id)
        return response
    except Exception as e:
        app.logger.error(f"Error getting consent history: {e}")
        response = make_response(jsonify({'error': 'Failed to get consent history'}), 500)
        create_session_cookie(response, new_session_id)
        return response


@app.route('/api/proxy/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@require_session
def api_proxy(path):
    """Proxy API requests with access token injection."""
    session_data = request.session_data
    new_session_id = request.new_session_id
    access_token = session_data['access_token']

    # Build target URL (configure API_GATEWAY_URL as needed)
    api_gateway_url = os.getenv('API_GATEWAY_URL', 'http://api-gateway:8080')
    target_url = f"{api_gateway_url}/{path}"

    # Forward request with access token
    headers = {k: v for k, v in request.headers if k.lower() not in ['host', 'cookie']}
    headers['Authorization'] = f'Bearer {access_token}'

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=request.get_data(),
            params=request.args,
            timeout=30
        )

        response = make_response(resp.content, resp.status_code)

        # Copy response headers except those that might conflict
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        for key, value in resp.headers.items():
            if key.lower() not in excluded_headers:
                response.headers[key] = value

        # Update session cookie with rotated session ID
        create_session_cookie(response, new_session_id)

        return response
    except requests.exceptions.RequestException as e:
        response = make_response(jsonify({'error': 'API request failed'}), 502)
        create_session_cookie(response, new_session_id)
        return response


# =============================================================================
# Reports Service Proxy
# =============================================================================

REPORTS_SERVICE_URL = os.getenv('REPORTS_SERVICE_URL', 'http://reports-service:8001')


@app.route('/api/reports', methods=['GET'])
@app.route('/api/reports/<path:subpath>', methods=['GET', 'DELETE'])
@require_session
def reports_proxy(subpath=''):
    """
    Proxy requests to Reports Service with access token injection.

    Routes:
        GET /api/reports - List of user's reports
        GET /api/reports/summary - User's summary
        GET /api/reports/{date} - Daily report
        DELETE /api/reports/cache - Clear user's cache

    Security:
        - Requires valid session
        - Access token is injected as Bearer token
        - Reports Service validates token and enforces user isolation
    """
    session_data = request.session_data
    new_session_id = request.new_session_id
    access_token = session_data['access_token']

    # Build target URL
    if subpath:
        target_url = f"{REPORTS_SERVICE_URL}/api/reports/{subpath}"
    else:
        target_url = f"{REPORTS_SERVICE_URL}/api/reports"

    # Forward request with access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    # Add X-Forwarded headers for audit logging
    headers['X-Forwarded-For'] = request.remote_addr
    headers['X-Forwarded-User-Agent'] = request.headers.get('User-Agent', '')

    app.logger.info(f"Proxying reports request: {request.method} {target_url}")

    try:
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=headers,
            params=request.args,
            timeout=30
        )

        response = make_response(resp.content, resp.status_code)
        response.headers['Content-Type'] = 'application/json'

        # Copy X-Request-ID for tracing
        if 'X-Request-ID' in resp.headers:
            response.headers['X-Request-ID'] = resp.headers['X-Request-ID']

        # Update session cookie with rotated session ID
        create_session_cookie(response, new_session_id)

        return response

    except requests.exceptions.Timeout:
        app.logger.error("Reports service timeout")
        response = make_response(
            jsonify({'success': False, 'error': 'Reports service timeout'}),
            504
        )
        create_session_cookie(response, new_session_id)
        return response

    except requests.exceptions.ConnectionError:
        app.logger.error("Reports service unavailable")
        response = make_response(
            jsonify({'success': False, 'error': 'Reports service unavailable'}),
            503
        )
        create_session_cookie(response, new_session_id)
        return response

    except requests.exceptions.RequestException as e:
        app.logger.error(f"Reports proxy error: {e}")
        response = make_response(
            jsonify({'success': False, 'error': 'Failed to fetch reports'}),
            502
        )
        create_session_cookie(response, new_session_id)
        return response


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint."""
    try:
        redis_client.ping()
        redis_status = 'healthy'
    except Exception:
        redis_status = 'unhealthy'

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        db_status = 'healthy'
    except Exception:
        db_status = 'unhealthy'

    overall_status = 'healthy' if redis_status == 'healthy' and db_status == 'healthy' else 'degraded'

    return jsonify({
        'status': overall_status,
        'redis': redis_status,
        'database': db_status
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=os.getenv('DEBUG', 'false').lower() == 'true')
