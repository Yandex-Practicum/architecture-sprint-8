import logging
import os
from typing import Any, Dict

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.middleware.cors import CORSMiddleware

from .auth import KeycloakAuthenticator
from .database import create_clickhouse_client, fetch_emg_report
from .report import report_to_csv_stream


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Reports API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

auth_scheme = HTTPBearer(auto_error=False)

keycloak_authenticator = KeycloakAuthenticator(
    well_known_url=os.getenv(
        "KEYCLOAK_WELL_KNOWN_URL",
        "http://keycloak:8082/realms/reports-realm/.well-known/openid-configuration",
    ),
    audience=os.getenv("KEYCLOAK_AUDIENCE"),
    issuer_override=os.getenv("KEYCLOAK_ISSUER_OVERRIDE"),
)


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(auth_scheme)) -> Dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header missing")

    token = credentials.credentials
    return keycloak_authenticator.validate_token(token)


@app.get("/health", tags=["health"])
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/reports", response_class=StreamingResponse, tags=["reports"])
def download_report(_: Dict[str, Any] = Depends(get_current_user)) -> StreamingResponse:
    """Return the EMG sensor data report as CSV for authenticated users."""
    client = create_clickhouse_client()
    try:
        result = fetch_emg_report(client)
    finally:
        client.close()

    filename = "reporting_customer_telemetry.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}

    return StreamingResponse(report_to_csv_stream(result), media_type="text/csv", headers=headers)