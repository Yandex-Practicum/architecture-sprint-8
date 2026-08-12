import base64
import json


def decode_claims_unverified(jwt_token: str) -> dict:
    """Декодирует payload JWT без проверки подписи.

    Токен читается здесь исключительно сразу после того, как он был выдан нам
    напрямую token endpoint по доверенному серверному вызову, поэтому проверка
    подписи не требуется для доверия его содержимому. reports-api, который
    получает токен от недоверенного вызывающего, обязан проверять его отдельно.
    """
    payload_segment = jwt_token.split(".")[1]
    padding = "=" * (-len(payload_segment) % 4)
    decoded = base64.urlsafe_b64decode(payload_segment + padding)
    return json.loads(decoded)
