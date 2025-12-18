import base64
import hashlib
import json
import logging
import re
from typing import Dict, Any, Optional
from urllib.parse import urlencode, unquote_plus

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

api = FastAPI(
    title="Yandex OAuth OIDC Proxy",
    description="Адаптер для интеграции Yandex OAuth с OIDC-совместимыми системами",
    version="1.0.0"
)

YANDEX_AUTHORIZATION_ENDPOINT = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_ENDPOINT = "https://oauth.yandex.ru/token"
YANDEX_USER_PROFILE_ENDPOINT = "https://login.yandex.ru/info"

pkce_nonce_mapping: Dict[str, str] = {}


@api.get("/health")
async def service_health():
    return {"service": "yandex-proxy", "status": "operational"}


@api.get("/authorize")
async def handle_authorization_request(request: Request):
    request_params = dict(request.query_params)

    logger.info("Получен запрос авторизации: %s", {
        'client_id': request_params.get('client_id'),
        'scope': request_params.get('scope'),
        'response_type': request_params.get('response_type')
    })

    if 'scope' in request_params:
        original_scopes = request_params['scope']

        cleaned_scopes = re.sub(r'\bopenid\b\s*', '', original_scopes)

        cleaned_scopes = re.sub(r'\s+', ' ', cleaned_scopes).strip()
        request_params['scope'] = cleaned_scopes

        logger.debug("Модифицирован scope: %s -> %s", original_scopes, cleaned_scopes)

    challenge_value = request_params.get('code_challenge')
    nonce_value = request_params.get('nonce')

    if challenge_value and nonce_value:
        pkce_nonce_mapping[challenge_value] = nonce_value
        logger.info("Сохранена связь PKCE challenge -> nonce (%s символов)",
                    len(challenge_value))

    yandex_auth_url = f"{YANDEX_AUTHORIZATION_ENDPOINT}?{urlencode(request_params)}"
    logger.info("Перенаправление пользователя на Yandex OAuth")

    return RedirectResponse(url=yandex_auth_url)


@api.post("/token")
async def process_token_exchange(request: Request):

    raw_body = await request.body()
    parsed_form_data = {}

    if raw_body:
        decoded_body = raw_body.decode('utf-8')
        for item in decoded_body.split('&'):
            if '=' in item:
                key, value = item.split('=', 1)
                parsed_key = unquote_plus(key)
                parsed_value = unquote_plus(value)
                parsed_form_data[parsed_key] = parsed_value

    logger.info("Запрос обмена токена для client_id: %s",
                parsed_form_data.get('client_id'))

    async with httpx.AsyncClient(timeout=30.0) as http_client:

        yandex_response = await http_client.post(
            YANDEX_TOKEN_ENDPOINT,
            data=parsed_form_data,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )

        logger.info("Ответ от Yandex: HTTP %s", yandex_response.status_code)

        if yandex_response.status_code == 200:
            tokens = yandex_response.json()

            if 'id_token' not in tokens:
                logger.info("Генерация id_token для OIDC-совместимости")

                user_subject = await _fetch_user_subject(
                    http_client,
                    tokens.get('access_token')
                )

                id_token = await _construct_id_token(
                    access_token_data=tokens,
                    form_data=parsed_form_data,
                    user_subject_id=user_subject
                )

                tokens['id_token'] = id_token
                logger.debug("Сгенерирован id_token: %s...", id_token[:50])

            return Response(
                content=json.dumps(tokens),
                status_code=yandex_response.status_code,
                media_type="application/json",
                headers={
                    'Cache-Control': 'no-store, no-cache, must-revalidate',
                    'Pragma': 'no-cache'
                }
            )
        else:

            logger.error("Ошибка от Yandex API: %s", yandex_response.text)
            return Response(
                content=yandex_response.content,
                status_code=yandex_response.status_code,
                headers=dict(yandex_response.headers)
            )


@api.get("/info")
async def retrieve_user_information(request: Request):
    forwarded_headers = dict(request.headers)
    forwarded_headers.pop('host', None)

    async with httpx.AsyncClient() as http_client:
        profile_response = await http_client.get(
            YANDEX_USER_PROFILE_ENDPOINT,
            headers=forwarded_headers
        )

        logger.info("Запрос информации о пользователе: HTTP %s",
                    profile_response.status_code)

        if profile_response.status_code == 200:
            user_profile = profile_response.json()
            logger.debug("Профиль пользователя: %s", user_profile)

            enriched_profile = _enrich_user_profile(user_profile)

            return Response(
                content=json.dumps(enriched_profile),
                status_code=profile_response.status_code,
                media_type="application/json",
                headers={'Cache-Control': 'no-store'}
            )
        else:
            logger.error("Ошибка получения профиля: %s", profile_response.text)
            return Response(
                content=profile_response.content,
                status_code=profile_response.status_code,
                headers=dict(profile_response.headers)
            )


async def _fetch_user_subject(client: httpx.AsyncClient,
                              access_token: Optional[str]) -> str:
    if not access_token:
        return "yandex_unknown_user"

    try:
        userinfo_response = await client.get(
            YANDEX_USER_PROFILE_ENDPOINT,
            headers={'Authorization': f"OAuth {access_token}"}
        )

        if userinfo_response.status_code == 200:
            user_data = userinfo_response.json()
            return str(user_data.get('id', 'yandex_user'))
    except Exception as error:
        logger.warning("Не удалось получить userinfo: %s", error)

    return "yandex_user"


async def _construct_id_token(access_token_data: Dict[str, Any],
                              form_data: Dict[str, Any],
                              user_subject_id: str) -> str:

    jwt_header = {
        "alg": "none",
        "typ": "JWT"
    }

    jwt_payload = {
        "iss": "https://oauth.yandex.ru",
        "sub": user_subject_id,
        "aud": access_token_data.get('client_id', 'default_client'),

    }

    code_verifier = form_data.get('code_verifier')
    if code_verifier:
        try:

            sha256_hash = hashlib.sha256(code_verifier.encode()).digest()
            calculated_challenge = base64.urlsafe_b64encode(sha256_hash)
            calculated_challenge_str = calculated_challenge.decode().rstrip('=')

            associated_nonce = pkce_nonce_mapping.get(calculated_challenge_str)
            if associated_nonce:
                jwt_payload['nonce'] = associated_nonce
                logger.info("Добавлен nonce в id_token через PKCE")
        except Exception as error:
            logger.warning("Ошибка при восстановлении nonce: %s", error)

    encoded_header = base64.urlsafe_b64encode(
        json.dumps(jwt_header).encode()
    ).decode().rstrip('=')

    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(jwt_payload).encode()
    ).decode().rstrip('=')

    return f"{encoded_header}.{encoded_payload}."


def _enrich_user_profile(original_profile: Dict[str, Any]) -> Dict[str, Any]:
    enriched = original_profile.copy()

    if 'id' in enriched and 'sub' not in enriched:
        enriched['sub'] = str(enriched['id'])

    if 'default_email' in enriched and 'email' not in enriched:
        enriched['email'] = enriched['default_email']

    logger.debug("Профиль обогащен OIDC-полями")
    return enriched


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        api,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
