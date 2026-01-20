import os
import logging
import requests
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from jose import jwt, jwk
from jose.utils import base64url_decode

logger = logging.getLogger("api_logger")
app = FastAPI()


@app.on_event("startup")
def configure_logging():
    logging.basicConfig(level=logging.DEBUG)
    logger.info("API started. Logging configured.")


KEYCLOAK_URL = os.getenv("KEYCLOAK_URL")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
OIDC_DISCOVERY_URL = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/.well-known/openid-configuration"
ALGORITHM = "RS256"

JWKS_CACHE = {}  # map[kid]jwk-object

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_jwks():
    oidc_config = requests.get(OIDC_DISCOVERY_URL).json()
    jwks_uri = oidc_config["jwks_uri"]

    jwks = requests.get(jwks_uri).json()
    keys = jwks.get("keys", [])
    if not keys:
        raise HTTPException(status_code=500, detail="No keys found in JWKS")
    return keys


def get_jwk_for_kid(kid: str):
    if kid in JWKS_CACHE:
        return JWKS_CACHE[kid]
    keys = load_jwks()

    for key_data in keys:
        if key_data.get("kid") == kid:
            logger.debug(f"Matched kid={kid} in JWKS")
            jwk_obj = jwk.construct(key_data, ALGORITHM)
            JWKS_CACHE[kid] = jwk_obj
            return jwk_obj

    raise HTTPException(status_code=401, detail=f"No matching kid '{kid}' found in JWKS")


def validate_token(authorization: str = Header(None)):
    logger.debug(f"Authorization header: {authorization}")
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing token")

    try:
        token = authorization.split(" ")[1]
        logger.debug(f"Received token: {token}")

        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        logger.debug(f"Token header: {header}")

        if not kid:
            raise HTTPException(status_code=401, detail="No kid in token header")

        public_jwk = get_jwk_for_kid(kid)

        payload = jwt.decode(token, public_jwk, algorithms=[ALGORITHM])
        logger.debug(f"Token payload: {payload}")

        roles = payload.get("realm_access", {}).get("roles", [])
        logger.debug(f"User roles from token: {roles}")
        if "prothetic_user" not in roles:
            raise HTTPException(status_code=403, detail="Forbidden: insufficient role")

    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        # logger.exception("got expection on validation")
        raise HTTPException(status_code=401, detail="Unexpected validation error")

    return payload


@app.get("/reports")
def get_reports(user=Depends(validate_token)):
    logger.info(f"Serving /reports for user payload: {user}")
    return {"data": [{"id": 1, "report": "report"}]}


@app.get("/health")
def health():
    return {"status": "ok"}
