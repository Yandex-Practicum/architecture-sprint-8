from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import requests
from datetime import datetime
from config import KEYCLOAK_URL, KEYCLOAK_REALM
from services.clickhouse_client import get_report

app = FastAPI(title="BionicPRO Reports API")
security = HTTPBearer()

def get_public_key():
    realm_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}"
    config = requests.get(f"{realm_url}/.well-known/openid-configuration").json()
    jwks_uri = config["jwks_uri"]
    jwks_client = jwt.PyJWKClient(jwks_uri)
    return jwks_client

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        jwks_client = get_public_key()
        signing_key = jwks_client.get_signing_key_from_jwt(credentials.credentials)
        payload = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_exp": True, "verify_aud": False},
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/reports")
def get_user_report(
    period_from: str = Query(None, description="Start date YYYY-MM-DD"),
    period_to: str = Query(None, description="End date YYYY-MM-DD"),
    token_data: dict = Depends(verify_token),
):
    preferred_username = token_data.get("preferred_username", "")
    import re
    match = re.search(r'\d+$', preferred_username)
    user_id = int(match.group()) if match else preferred_username

    rows = get_report(user_id, period_from, period_to)

    if not rows:
        return {
            "user_id": user_id,
            "report": [],
            "message": "No data for the requested period. "
                       "The period may not have been processed by Airflow yet."
        }

    report = [
        {
            "date": str(row[4]),
            "total_readings": row[5],
            "avg_signal_1": round(row[6], 2),
            "avg_signal_2": round(row[7], 2),
            "avg_signal_3": round(row[8], 2),
            "avg_signal_4": round(row[9], 2),
            "avg_battery_level": round(row[10], 2),
            "movements": {
                "grasp": row[11],
                "release": row[12],
                "flex": row[13],
                "extend": row[14],
                "rotate": row[15],
            },
        }
        for row in rows
    ]

    return {
        "user_id": user_id,
        "full_name": rows[0][1] if rows else None,
        "email": rows[0][2] if rows else None,
        "report": report,
    }
