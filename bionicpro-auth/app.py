from flask import Flask, request, jsonify, session, redirect, make_response
from flask_cors import CORS
from dotenv import load_dotenv
import secrets
import logging

from config import Config
from services.keycloak import KeycloakService
from services.session import SessionStore
from services.olap import OlapService
from services.s3 import S3Service

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
config = Config()

app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['SESSION_COOKIE_NAME'] = config.SESSION_COOKIE_NAME
app.config['SESSION_COOKIE_HTTPONLY'] = config.SESSION_COOKIE_HTTPONLY
app.config['SESSION_COOKIE_SECURE'] = config.SESSION_COOKIE_SECURE
app.config['SESSION_COOKIE_SAMESITE'] = config.SESSION_COOKIE_SAMESITE
app.config['SESSION_COOKIE_DOMAIN'] = None
app.config['PERMANENT_SESSION_LIFETIME'] = config.PERMANENT_SESSION_LIFETIME

CORS(
    app,
    supports_credentials=True,
    origins=[config.FRONTEND_URL],
    allow_headers=['Content-Type', 'Authorization'],
    methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
    expose_headers=['Content-Type']
)

keycloak_service = KeycloakService(config)
session_store = SessionStore()
olap_service = OlapService(config)
s3_service = S3Service(config)

pkce_store = {}


def _get_valid_access_token(session_id):
    """
    Get valid access_token. Refresh if expired.
    Returns (access_token, error_response).
    """
    session_data = session_store.get_session(session_id)
    if not session_data:
        logger.warning(f"Session not found: {session_id[:8]}...")
        return None, (jsonify({'error': 'Unauthorized', 'code': 'INVALID_SESSION'}), 401)

    access_token = session_data['access_token']

    if keycloak_service.is_token_expired(access_token):
        logger.info(f"Access token expired, refreshing for session: {session_id[:8]}...")

        refresh_token = session_store.get_decrypted_refresh_token(session_id)
        if not refresh_token:
            logger.error("No refresh token available")
            return None, (jsonify({'error': 'Unauthorized', 'code': 'NO_REFRESH_TOKEN'}), 401)

        try:
            new_tokens = keycloak_service.refresh_access_token(refresh_token)
            new_access_token = new_tokens['access_token']
            new_refresh_token = new_tokens.get('refresh_token', refresh_token)

            session_store.update_session_tokens(
                session_id,
                new_access_token,
                new_refresh_token
            )

            access_token = new_access_token
            logger.info("Access token refreshed successfully")

        except Exception as e:
            logger.error(f"Token refresh failed: {str(e)}")
            return None, (jsonify({'error': 'Unauthorized', 'code': 'REFRESH_FAILED'}), 401)

    return access_token, None


@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'service': 'bionicpro-auth'}), 200


@app.route('/auth/init', methods=['POST'])
def auth_init():
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

    session.permanent = True
    session[f'pkce_verifier_{state}'] = code_verifier

    logger.info(f"Stored code_verifier in session for state: {state}")
    logger.info(f"Session keys after save: {list(session.keys())}")

    return jsonify({'status': 'ok'}), 200


@app.route('/auth/callback', methods=['GET'])
def auth_callback():
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

    code_verifier = session.pop(f'pkce_verifier_{state}', '')

    logger.info(f"Code verifier retrieved: {code_verifier[:20] if code_verifier else 'EMPTY'}...")

    if not code_verifier:
        logger.error(f"No code_verifier found for state: {state}")
        logger.error(f"Available states in store: {list(pkce_store.keys())}")
        return redirect(f"{config.FRONTEND_URL}?error=no_verifier")

    try:
        tokens = keycloak_service.exchange_code_for_tokens(code, code_verifier)

        access_token = tokens['access_token']
        refresh_token = tokens['refresh_token']

        session_id = session_store.create_session(access_token, refresh_token)

        session.permanent = True
        session['session_id'] = session_id

        logger.info(f"User authenticated successfully, session: {session_id[:8]}...")

        return redirect(config.FRONTEND_URL)

    except Exception as e:
        logger.error(f"Authentication failed: {str(e)}")
        return redirect(f"{config.FRONTEND_URL}?error=auth_failed")


@app.route('/auth/logout', methods=['POST'])
def logout():
    session_id = session.get('session_id')

    if session_id:
        session_store.delete_session(session_id)
        session.clear()

    return jsonify({'status': 'logged_out'}), 200


@app.route('/api/reports', methods=['GET'])
def get_reports():
    """
    Get user report with S3 caching:
    1. Get datamart version (last ETL update time)
    2. Check if report exists in S3 for email + version
    3. If found in S3 -> return CDN link (no OLAP query)
    4. If not found -> query OLAP, save to S3, return CDN link
    """
    session_id = session.get('session_id')

    if not session_id:
        logger.warning("Request without session")
        return jsonify({'error': 'Unauthorized', 'code': 'NO_SESSION'}), 401

    access_token, error_response = _get_valid_access_token(session_id)
    if error_response:
        return error_response

    try:
        new_session_id = session_store.rotate_session(session_id)
        session['session_id'] = new_session_id
        logger.info(f"Session rotated: {session_id[:8]}... -> {new_session_id[:8]}...")
    except Exception as e:
        logger.error(f"Session rotation failed: {str(e)}")

    user_info = keycloak_service.get_user_info(access_token)
    if not user_info:
        return jsonify({'error': 'Failed to get user info'}), 500

    user_email = user_info.get('email', '')
    username = user_info.get('preferred_username', 'unknown')

    if not olap_service.check_datamart_exists():
        logger.warning("Datamart is empty or does not exist")
        return jsonify({
            'user': username,
            'reports': [],
            'report_data': None,
            'message': 'Данные ещё не обработаны. Airflow ETL-процесс не завершён. Попробуйте позже.'
        }), 200

    datamart_updated_at = olap_service.get_datamart_last_updated() or 'unknown'

    # Step 1: check S3 cache
    cached_report = s3_service.get_report(user_email, datamart_updated_at)

    if cached_report:
        logger.info(f"Cache HIT for user {username}, serving from S3/CDN")
        cdn_url = s3_service.get_cdn_url(user_email, datamart_updated_at)

        reports_list = []
        for idx, telemetry in enumerate(cached_report.get('telemetry_summary', []), start=1):
            reports_list.append({
                'id': idx,
                'name': f"Телеметрия: {telemetry['prosthesis_type']} — {telemetry['muscle_group']}",
                'date': telemetry.get('last_signal_time', 'N/A')
            })

        return jsonify({
            'user': username,
            'reports': reports_list,
            'report_data': cached_report,
            'cdn_url': cdn_url,
            'cache_status': 'HIT'
        }), 200

    # Step 2: cache MISS, query OLAP
    logger.info(f"Cache MISS for user {username}, querying OLAP")
    report = olap_service.get_user_report_by_email(user_email)

    if not report:
        logger.info(f"No report data found for user: {username} (email: {user_email})")
        return jsonify({
            'user': username,
            'reports': [],
            'report_data': None,
            'message': 'Отчёт для вашего пользователя не найден. Возможно, ваши данные ещё не обработаны Airflow.'
        }), 200

    # Step 3: save to S3 and get CDN URL
    cdn_url = s3_service.put_report(user_email, datamart_updated_at, report)

    reports_list = []
    for idx, telemetry in enumerate(report.get('telemetry_summary', []), start=1):
        reports_list.append({
            'id': idx,
            'name': f"Телеметрия: {telemetry['prosthesis_type']} — {telemetry['muscle_group']}",
            'date': telemetry.get('last_signal_time', 'N/A')
        })

    return jsonify({
        'user': username,
        'reports': reports_list,
        'report_data': report,
        'cdn_url': cdn_url,
        'cache_status': 'MISS'
    }), 200


@app.route('/api/reports/generate', methods=['POST'])
def generate_report():
    """
    Generate report: check S3 -> if not found, generate from OLAP -> save to S3 -> return CDN URL.
    """
    session_id = session.get('session_id')

    if not session_id:
        logger.warning("Generate report request without session")
        return jsonify({'error': 'Unauthorized', 'code': 'NO_SESSION'}), 401

    access_token, error_response = _get_valid_access_token(session_id)
    if error_response:
        return error_response

    user_info = keycloak_service.get_user_info(access_token)
    if not user_info:
        return jsonify({'error': 'Failed to get user info'}), 500

    user_email = user_info.get('email', '')
    username = user_info.get('preferred_username', 'unknown')

    if not olap_service.check_datamart_exists():
        return jsonify({
            'error': 'DATA_NOT_READY',
            'message': 'Данные ещё не обработаны ETL-процессом Airflow. Витрина пуста. Попробуйте позже.'
        }), 404

    datamart_updated_at = olap_service.get_datamart_last_updated() or 'unknown'

    # Check S3 cache first
    cached_report = s3_service.get_report(user_email, datamart_updated_at)
    if cached_report:
        logger.info(f"Report already cached for user {username}, returning CDN URL")
        cdn_url = s3_service.get_cdn_url(user_email, datamart_updated_at)
        cached_report['datamart_last_updated'] = datamart_updated_at
        return jsonify({
            'status': 'success',
            'report': cached_report,
            'cdn_url': cdn_url,
            'cache_status': 'HIT'
        }), 200

    # Generate from OLAP
    report = olap_service.get_user_report_by_email(user_email)

    if not report:
        return jsonify({
            'error': 'NO_DATA',
            'message': f'Данные для пользователя {username} не найдены в OLAP. '
                       f'Возможно, ETL ещё не обработал ваши данные. '
                       f'Последнее обновление витрины: {datamart_updated_at}.'
        }), 404

    report['datamart_last_updated'] = datamart_updated_at

    # Save to S3
    cdn_url = s3_service.put_report(user_email, datamart_updated_at, report)

    logger.info(f"Report generated and cached for user: {username} (email: {user_email})")

    return jsonify({
        'status': 'success',
        'report': report,
        'cdn_url': cdn_url,
        'cache_status': 'MISS'
    }), 200


@app.route('/api/user', methods=['GET'])
def get_user():
    session_id = session.get('session_id')

    if not session_id:
        return jsonify({'error': 'Unauthorized'}), 401

    access_token, error_response = _get_valid_access_token(session_id)
    if error_response:
        return error_response

    user_info = keycloak_service.get_user_info(access_token)

    if not user_info:
        return jsonify({'error': 'Failed to get user info'}), 500

    return jsonify(user_info), 200


if __name__ == '__main__':
    logger.info("Starting BionicPRO Auth Service...")
    logger.info(f"Frontend URL: {config.FRONTEND_URL}")
    logger.info(f"Keycloak URL: {config.KEYCLOAK_URL}")
    logger.info(f"ClickHouse URL: {config.CLICKHOUSE_HTTP_URL}")
    logger.info(f"S3 Endpoint: {config.S3_ENDPOINT_URL}")
    logger.info(f"CDN Base URL: {config.CDN_BASE_URL}")

    app.run(
        host='0.0.0.0',
        port=5050,
        debug=True
    )
