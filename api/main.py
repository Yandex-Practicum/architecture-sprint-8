import os
import logging
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from keycloak import KeycloakOpenID
from jwcrypto import jwk 
from fastapi.responses import JSONResponse


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL", "http://keycloak:8080")
REALM_NAME = os.getenv("REALM_NAME", "reports-realm")
CLIENT_ID = os.getenv("CLIENT_ID", "reports-api")
CLIENT_SECRET = os.getenv("CLIENT_SECRET", "IiePgosFlLulH7K9A8WEY0bKHZkKzqYg")

keycloak_openid = KeycloakOpenID(
    server_url=KEYCLOAK_SERVER_URL,
    client_id=CLIENT_ID,
    realm_name=REALM_NAME,
    client_secret_key=CLIENT_SECRET
)

# Cache for the public key as a JWK object
PUBLIC_JWK = None

def format_public_key(raw_key: str) -> str:
    raw_key = raw_key.strip()
    lines = [raw_key[i:i+64] for i in range(0, len(raw_key), 64)]
    pem_key = "-----BEGIN PUBLIC KEY-----\n" + "\n".join(lines) + "\n-----END PUBLIC KEY-----"
    return pem_key

def verify_token(authorization: str = Header(None)):
   
    if not authorization or not authorization.startswith("Bearer "):
       raise HTTPException(status_code=401, detail="Missing or invalid token")

    token = authorization.split("Bearer ")[1]


    global PUBLIC_JWK
    try:
        if PUBLIC_JWK is None:
            raw_public_key = keycloak_openid.public_key()
            formatted_public_key = format_public_key(raw_public_key)
            jwk_obj = jwk.JWK.from_pem(formatted_public_key.encode("utf-8"))
            PUBLIC_JWK = jwk_obj
            logger.info("Converted public key to JWK object.")
        user_info = keycloak_openid.decode_token(token, key=PUBLIC_JWK)
        logger.info("Decoded token successfully: %s", user_info)
        return user_info
    except Exception as e:
        logger.exception("Token decoding failed: %s", e)
        raise HTTPException(status_code=401, detail="Invalid token (decoding error)")

@app.get("/reports")
async def get_reports(user: dict = Depends(verify_token)):
    roles = user.get("realm_access", {}).get("roles", [])
    user_id = user.get("sub")

    if "prothetic_user" not in roles:
        raise HTTPException(status_code=403, detail="Forbidden: Missing prothetic_user role")

    return JSONResponse(content={"user_id": user_id, "roles": roles})
