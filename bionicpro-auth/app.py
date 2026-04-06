import os
import secrets
import hashlib
import base64
import json
import logging
from datetime import datetime, timedelta
from functools import wraps
from typing import Optional, Dict, Any

import requests
from flask import Flask, request, jsonify, redirect, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import jwt
import redis

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=[os.getenv('FRONTEND_URL', 'http://127.0.0.1:3000')])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://127.0.0.1:8080')
KEYCLOAK_PUBLIC_URL = os.getenv('KEYCLOAK_PUBLIC_URL', 'http://127.0.0.1:8080')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'reports-realm')
KEYCLOAK_CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID', 'bionicpro-auth')
KEYCLOAK_CLIENT_SECRET = os.getenv('KEYCLOAK_CLIENT_SECRET', '')
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://127.0.0.1:3000')
AUTH_SERVICE_BASE_URL = os.getenv('AUTH_SERVICE_BASE_URL', 'http://127.0.0.1:5000')
SESSION_SECRET_KEY = os.getenv('SESSION_SECRET_KEY', 'default-secret-key')
REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
ACCESS_TOKEN_MAX_AGE = int(os.getenv('ACCESS_TOKEN_MAX_AGE', '120'))
SESSION_MAX_AGE = int(os.getenv('SESSION_MAX_AGE', '1800'))

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis successfully")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}. Using in-memory storage.")
    redis_client = None

in_memory_storage: Dict[str, Any] = {}


class SessionStorage:
    """Управление хранением сессий и токенов"""

    @staticmethod
    def set(key: str, value: dict, expire: int = SESSION_MAX_AGE):
        if redis_client:
            redis_client.setex(key, expire, json.dumps(value))
        else:
            in_memory_storage[key] = {
                'data': value,
                'expires_at': datetime.utcnow() + timedelta(seconds=expire)
            }

    @staticmethod
    def get(key: str) -> Optional[dict]:
        if redis_client:
            data = redis_client.get(key)
            return json.loads(data) if data else None
        else:
            stored = in_memory_storage.get(key)
            if stored and stored['expires_at'] > datetime.utcnow():
                return stored['data']
            elif stored:
                del in_memory_storage[key]
            return None

    @staticmethod
    def delete(key: str):
        if redis_client:
            redis_client.delete(key)
        else:
            in_memory_storage.pop(key, None)


class PKCEHelper:
    """PKCE code verifier и code challenge генератор"""

    @staticmethod
    def generate_code_verifier() -> str:
        return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')

    @staticmethod
    def generate_code_challenge(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode('utf-8')).digest()
        return base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')


class KeycloakClient:
    """Клиент для работы с Keycloak"""

    @staticmethod
    def get_token_endpoint() -> str:
        return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/token"

    @staticmethod
    def get_auth_endpoint() -> str:
        return f"{KEYCLOAK_PUBLIC_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/auth"

    @staticmethod
    def get_userinfo_endpoint() -> str:
        return f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/userinfo"

    @staticmethod
    def exchange_code_for_tokens(code: str, code_verifier: str, redirect_uri: str) -> Optional[dict]:
        """Обмен authorization code на токены с использованием PKCE"""
        try:
            response = requests.post(
                KeycloakClient.get_token_endpoint(),
                data={
                    'grant_type': 'authorization_code',
                    'client_id': KEYCLOAK_CLIENT_ID,
                    'client_secret': KEYCLOAK_CLIENT_SECRET,
                    'code': code,
                    'redirect_uri': redirect_uri,
                    'code_verifier': code_verifier
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            return None

    @staticmethod
    def refresh_access_token(refresh_token: str) -> Optional[dict]:
        """Обновление access token используя refresh token"""
        try:
            response = requests.post(
                KeycloakClient.get_token_endpoint(),
                data={
                    'grant_type': 'refresh_token',
                    'client_id': KEYCLOAK_CLIENT_ID,
                    'client_secret': KEYCLOAK_CLIENT_SECRET,
                    'refresh_token': refresh_token
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )

            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Token refresh failed: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error refreshing token: {e}")
            return None

    @staticmethod
    def get_user_info(access_token: str) -> Optional[dict]:
        """Получение информации о пользователе"""
        try:
            response = requests.get(
                KeycloakClient.get_userinfo_endpoint(),
                headers={'Authorization': f'Bearer {access_token}'}
            )

            if response.status_code == 200:
                return response.json()
            else:
                return None
        except Exception as e:
            logger.error(f"Error getting user info: {e}")
            return None


class SessionManager:
    """Управление пользовательскими сессиями"""

    @staticmethod
    def create_session(access_token: str, refresh_token: str, user_info: dict) -> str:
        """Создание новой сессии"""
        session_id = secrets.token_urlsafe(32)

        session_data = {
            'access_token': access_token,
            'refresh_token': refresh_token,
            'user_info': user_info,
            'created_at': datetime.utcnow().isoformat(),
            'last_rotation': datetime.utcnow().isoformat()
        }

        SessionStorage.set(f"session:{session_id}", session_data, SESSION_MAX_AGE)
        logger.info(f"Created session {session_id} for user {user_info.get('preferred_username')}")

        return session_id

    @staticmethod
    def get_session(session_id: str) -> Optional[dict]:
        """Получение данных сессии"""
        return SessionStorage.get(f"session:{session_id}")

    @staticmethod
    def rotate_session(old_session_id: str, access_token: str, refresh_token: str, user_info: dict) -> str:
        """Ротация сессии для предотвращения session fixation"""
        SessionManager.delete_session(old_session_id)

        new_session_id = SessionManager.create_session(access_token, refresh_token, user_info)
        logger.info(f"Rotated session from {old_session_id} to {new_session_id}")

        return new_session_id

    @staticmethod
    def delete_session(session_id: str):
        """Удаление сессии"""
        SessionStorage.delete(f"session:{session_id}")
        logger.info(f"Deleted session {session_id}")

    @staticmethod
    def refresh_session_tokens(session_id: str) -> Optional[dict]:
        """Обновление токенов в сессии"""
        session_data = SessionManager.get_session(session_id)
        if not session_data:
            return None

        refresh_token = session_data.get('refresh_token')
        if not refresh_token:
            return None

        new_tokens = KeycloakClient.refresh_access_token(refresh_token)
        if not new_tokens:
            return None

        session_data['access_token'] = new_tokens['access_token']
        if 'refresh_token' in new_tokens:
            session_data['refresh_token'] = new_tokens['refresh_token']

        SessionStorage.set(f"session:{session_id}", session_data, SESSION_MAX_AGE)
        logger.info(f"Refreshed tokens for session {session_id}")

        return session_data


def require_session(f):
    """Декоратор для проверки наличия валидной сессии"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        session_id = request.cookies.get('session_id')

        if not session_id:
            return jsonify({'error': 'No session found'}), 401

        session_data = SessionManager.get_session(session_id)
        if not session_data:
            return jsonify({'error': 'Invalid or expired session'}), 401

        access_token = session_data.get('access_token')
        if not access_token:
            return jsonify({'error': 'No access token in session'}), 401

        try:
            decoded = jwt.decode(access_token, options={"verify_signature": False})
            exp = decoded.get('exp')

            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                logger.info(f"Access token expired, attempting refresh for session {session_id}")
                refreshed_session = SessionManager.refresh_session_tokens(session_id)

                if not refreshed_session:
                    return jsonify({'error': 'Session expired, please login again'}), 401

                session_data = refreshed_session

        except Exception as e:
            logger.error(f"Error validating token: {e}")
            return jsonify({'error': 'Invalid token'}), 401

        request.session_data = session_data
        request.session_id = session_id

        return f(*args, **kwargs)

    return decorated_function


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'bionicpro-auth'}), 200


@app.route('/auth/login', methods=['GET'])
def login():
    """Инициирует PKCE flow авторизацию"""
    code_verifier = PKCEHelper.generate_code_verifier()
    code_challenge = PKCEHelper.generate_code_challenge(code_verifier)
    state = secrets.token_urlsafe(32)

    pkce_session_id = secrets.token_urlsafe(16)
    SessionStorage.set(
        f"pkce:{pkce_session_id}",
        {
            'code_verifier': code_verifier,
            'state': state
        },
        expire=600
    )

    redirect_uri = f"{AUTH_SERVICE_BASE_URL}/auth/callback"

    auth_url = (
        f"{KeycloakClient.get_auth_endpoint()}"
        f"?client_id={KEYCLOAK_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={redirect_uri}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
        f"&state={state}"
        f"&scope=openid profile email"
    )

    response = make_response(redirect(auth_url))
    response.set_cookie(
        'pkce_session',
        pkce_session_id,
        max_age=600,
        httponly=True,
        secure=False,
        samesite='Lax'
    )

    return response


@app.route('/auth/callback', methods=['GET'])
def callback():
    """Обработка callback от Keycloak после авторизации"""
    code = request.args.get('code')
    state = request.args.get('state')
    pkce_session_id = request.cookies.get('pkce_session')

    if not code or not state or not pkce_session_id:
        return jsonify({'error': 'Missing parameters'}), 400

    pkce_data = SessionStorage.get(f"pkce:{pkce_session_id}")
    if not pkce_data:
        return jsonify({'error': 'Invalid or expired PKCE session'}), 400

    if pkce_data['state'] != state:
        logger.error("State mismatch - possible CSRF attack")
        return jsonify({'error': 'State mismatch'}), 400

    code_verifier = pkce_data['code_verifier']
    redirect_uri = f"{AUTH_SERVICE_BASE_URL}/auth/callback"

    tokens = KeycloakClient.exchange_code_for_tokens(code, code_verifier, redirect_uri)
    if not tokens:
        return jsonify({'error': 'Failed to exchange code for tokens'}), 500

    access_token = tokens.get('access_token')
    refresh_token = tokens.get('refresh_token')

    user_info = KeycloakClient.get_user_info(access_token)
    if not user_info:
        return jsonify({'error': 'Failed to get user info'}), 500

    session_id = SessionManager.create_session(access_token, refresh_token, user_info)

    SessionStorage.delete(f"pkce:{pkce_session_id}")

    response = make_response(redirect(FRONTEND_URL))
    response.set_cookie(
        'session_id',
        session_id,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=False,
        samesite='Lax'
    )
    response.delete_cookie('pkce_session')

    return response


@app.route('/auth/logout', methods=['POST'])
@require_session
def logout():
    """Выход из системы"""
    session_id = request.session_id
    SessionManager.delete_session(session_id)

    response = jsonify({'message': 'Logged out successfully'})
    response.delete_cookie('session_id')

    return response, 200


@app.route('/auth/user', methods=['GET'])
@require_session
def get_user():
    """Получение информации о текущем пользователе"""
    user_info = request.session_data.get('user_info', {})
    return jsonify(user_info), 200


@app.route('/auth/session/rotate', methods=['POST'])
@require_session
def rotate_session():
    """Ротация сессии для предотвращения session fixation"""
    old_session_id = request.session_id
    session_data = request.session_data

    new_session_id = SessionManager.rotate_session(
        old_session_id,
        session_data['access_token'],
        session_data['refresh_token'],
        session_data['user_info']
    )

    response = jsonify({'message': 'Session rotated successfully'})
    response.set_cookie(
        'session_id',
        new_session_id,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        secure=False,
        samesite='Lax'
    )

    return response, 200


@app.route('/auth/token', methods=['GET'])
@require_session
def get_token():
    """Получение access token для использования в API запросах"""
    access_token = request.session_data.get('access_token')
    return jsonify({'access_token': access_token}), 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
