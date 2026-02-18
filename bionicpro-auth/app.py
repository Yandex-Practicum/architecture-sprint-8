from flask import Flask, request, jsonify, session, redirect, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import secrets
import logging

from config import Config
from services.keycloak import KeycloakService
from services.session import SessionStore

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Инициализация Flask
app = Flask(__name__)

# Создаем экземпляр конфигурации
config = Config()

# Применяем конфигурацию к Flask app
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SESSION_COOKIE_NAME'] = config.SESSION_COOKIE_NAME
app.config['SESSION_COOKIE_HTTPONLY'] = config.SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SECURE'] = config.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_SAMESITE'] = config.SESSION_COOKIE_SAMESITE
app.config['SESSION_COOKIE_DOMAIN'] = None
app.config['PERMANENT_SESSION_LIFETIME'] = config.PERMANENT_SESSION_LIFETIME

# CORS с поддержкой credentials (для cookie)
# CORS с поддержкой credentials (для cookie)
CORS(
    app,
    supports_credentials=True,
    origins=[config.FRONTEND_URL],
    allow_headers=['Content-Type', 'Authorization'],
    methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    expose_headers=['Content-Type']
)

# Инициализация сервисов - передаем config объект
keycloak_service = KeycloakService(config)
session_store = SessionStore()

# Временное хранилище для code_verifier (в production использовать Redis)
pkce_store = {}


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'service': 'bionicpro-auth'}), 200


@app.route('/auth/init', methods=['POST'])
def auth_init():
    """
    Инициализация PKCE flow
    Frontend вызывает перед редиректом на Keycloak
    """
    data = request.json
    code_challenge = data.get('code_challenge')
    code_verifier = data.get('code_verifier')
    state = data.get('state')

    logger.info("=== AUTH INIT ===")
    logger.info(f"Received state: {state}")
    logger.info(f"Received code_verifier length: {len(code_verifier) if code_verifier else 0}")
    logger.info(f"Received code_challenge length: {len(code_challenge) if code_challenge else 0}")
    logger.info("================")

    if not all([code_challenge, code_verifier, state]):
        logger.error("Missing PKCE parameters!")
        return jsonify({'error': 'Missing PKCE parameters'}), 400

    # Сохраняем code_verifier в Flask session
    session.permanent = True
    session[f'pkce_verifier_{state}'] = code_verifier

    logger.info(f"Stored code_verifier in session for state: {state}")
    logger.info(f"Session keys after save: {list(session.keys())}")

    return jsonify({'status': 'ok'}), 200


@app.route('/auth/callback', methods=['GET'])
def auth_callback():
    """
    Callback endpoint после авторизации в Keycloak
    Обменивает authorization code на токены
    """
    code = request.args.get('code')
    state = request.args.get('state')

    logger.info("=== AUTH CALLBACK ===")
    logger.info(f"Received state: {state}")
    logger.info(f"Received code: {code[:20] if code else 'None'}...")
    logger.info(f"PKCE store contains: {list(pkce_store.keys())}")
    logger.info(f"Session keys: {list(session.keys())}")
    logger.info(f"Looking for key: pkce_verifier_{state}")
    logger.info(f"Session ID (Flask): {request.cookies.get('bionicpro_session', 'NO COOKIE')}")
    logger.info("====================")

    if not code:
        logger.error("No authorization code received")
        return redirect(f"{config.FRONTEND_URL}?error=no_code")

    # Получаем code_verifier для PKCE
    code_verifier = session.pop(f'pkce_verifier_{state}', '')

    logger.info(f"Code verifier retrieved: {code_verifier[:20] if code_verifier else 'EMPTY'}...")

    if not code_verifier:
        logger.error(f"No code_verifier found for state: {state}")
        logger.error(f"Available states in store: {list(pkce_store.keys())}")
        return redirect(f"{config.FRONTEND_URL}?error=no_verifier")

    try:
        # Обмен code на токены
        tokens = keycloak_service.exchange_code_for_tokens(code, code_verifier)

        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']

        # Создаем сессию и сохраняем токены
        session_id = session_store.create_session(access_token, refresh_token)

        # Устанавливаем session cookie
        session.permanent = True
        session['session_id'] = session_id

        logger.info(f"User authenticated successfully, session: {session_id[:8]}...")

        # Редирект на frontend
        return redirect(config.FRONTEND_URL)

    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return redirect(f"{config.FRONTEND_URL}?error=auth_failed")


@app.route('/auth/logout', methods=['POST'])
def logout():
    """Выход из системы"""
    session_id = session.get('session_id')

    if session_id:
        session_store.delete_session(session_id)
        session.clear()

    return jsonify({'status': 'logged_out'}), 200


@app.route('/api/reports', methods=['GET'])
def get_reports():
    """
    Защищенный endpoint для получения отчетов
    Включает автоматическое обновление токена и ротацию сессии
    """
    session_id = session.get('session_id')

    # Проверка наличия сессии
    if not session_id:
        logger.warning("Request without session")
        return jsonify({'error': 'Unauthorized', 'code': 'NO_SESSION'}), 401

    # Получаем данные сессии
    session_data = session_store.get_session(session_id)
    if not session_data:
        logger.warning(f"Session not found: {session_id[:8]}...")
        return jsonify({'error': 'Unauthorized', 'code': 'INVALID_SESSION'}), 401

    access_token = session_data['access_token']

    # Проверка истечения access_token
    if keycloak_service.is_token_expired(access_token):
        logger.info(f"Access token expired, refreshing for session: {session_id[:8]}...")

        # Получаем refresh_token
        refresh_token = session_store.get_decrypted_refresh_token(session_id)
        if not refresh_token:
            logger.error("No refresh token available")
            return jsonify({'error': 'Unauthorized', 'code': 'NO_REFRESH_TOKEN'}), 401

        try:
            # Обновляем access_token через refresh_token
            new_tokens = keycloak_service.refresh_access_token(refresh_token)
            new_access_token = new_tokens['access_token']
            new_refresh_token = new_tokens.get('refresh_token', refresh_token)

            # Обновляем токены в сессии
            session_store.update_session_tokens(
                session_id,
                new_access_token,
                new_refresh_token
            )

            access_token = new_access_token
            logger.info("Access token refreshed successfully")

        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            return jsonify({'error': 'Unauthorized', 'code': 'REFRESH_FAILED'}), 401

    # Ротация сессии для защиты от session fixation
    try:
        new_session_id = session_store.rotate_session(session_id)
        session['session_id'] = new_session_id
        logger.info(f"Session rotated: {session_id[:8]}... -> {new_session_id[:8]}...")
    except Exception as e:
        logger.error(f"Session rotation failed: {str(e)}")

    # TODO: Здесь должен быть вызов к реальному API отчетов
    # Пока возвращаем mock данные

    # Получаем информацию о пользователе
    user_info = keycloak_service.get_user_info(access_token)

    mock_report_data = {
        'user': user_info.get('preferred_username', 'unknown') if user_info else 'unknown',
        'reports': [
            {'id': 1, 'name': 'Usage Report Q1 2026', 'date': '2026-01-15'},
            {'id': 2, 'name': 'Usage Report Q2 2026', 'date': '2026-02-15'}
        ]
    }

    return jsonify(mock_report_data), 200


@app.route('/api/user', methods=['GET'])
def get_user():
    """Получить информацию о текущем пользователе"""
    session_id = session.get('session_id')

    if not session_id:
        return jsonify({'error': 'Unauthorized'}), 401

    session_data = session_store.get_session(session_id)
    if not session_data:
        return jsonify({'error': 'Unauthorized'}), 401

    access_token = session_data['access_token']

    # Проверка и обновление токена (аналогично /api/reports)
    if keycloak_service.is_token_expired(access_token):
        refresh_token = session_store.get_decrypted_refresh_token(session_id)
        if not refresh_token:
            return jsonify({'error': 'Unauthorized'}), 401

        try:
            new_tokens = keycloak_service.refresh_access_token(refresh_token)
            session_store.update_session_tokens(
                session_id,
                new_tokens['access_token'],
                new_tokens.get('refresh_token')
            )
            access_token = new_tokens['access_token']
        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            return jsonify({'error': 'Unauthorized'}), 401

    # Получаем информацию о пользователе
    user_info = keycloak_service.get_user_info(access_token)

    if not user_info:
        return jsonify({'error': 'Failed to get user info'}), 500

    return jsonify(user_info), 200


if __name__ == '__main__':
    logger.info("Starting BionicPRO Auth Service...")
    logger.info(f"Frontend URL: {config.FRONTEND_URL}")
    logger.info(f"Keycloak URL: {config.KEYCLOAK_URL}")

    app.run(
        host='0.0.0.0',
        port=5050,
        debug=True
    )
