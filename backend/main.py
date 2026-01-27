from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from clickhouse_driver import Client
from datetime import datetime, date
from typing import Optional
import requests
from jose import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
from config import (
    CLICKHOUSE_HOST,
    CLICKHOUSE_PORT,
    CLICKHOUSE_DB,
    CLICKHOUSE_USER,
    CLICKHOUSE_PASSWORD,
    KEYCLOAK_URL,
    KEYCLOAK_REALM
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

def get_keycloak_public_key(token: str):
    jwks_url = f"{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs"
    response = requests.get(jwks_url)
    jwks = response.json()
    
    unverified_header = jwt.get_unverified_header(token)
    key_data = None
    for key in jwks['keys']:
        if key['kid'] == unverified_header['kid']:
            key_data = key
            break
    
    if not key_data:
        raise HTTPException(status_code=401, detail="Unable to find appropriate key")
    
    n = base64.urlsafe_b64decode(key_data['n'] + '==')
    e = base64.urlsafe_b64decode(key_data['e'] + '==')
    
    n_int = int.from_bytes(n, 'big')
    e_int = int.from_bytes(e, 'big')
    
    public_numbers = rsa.RSAPublicNumbers(e_int, n_int)
    public_key = public_numbers.public_key(default_backend())
    
    pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )
    
    return pem.decode('utf-8')

def verify_token(request: Request, credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    if not credentials:
        auth_header = request.headers.get("Authorization")
        logger.error(f"No credentials, auth header: {auth_header}")
        raise HTTPException(status_code=401, detail="Token not provided")
    
    token = credentials.credentials if credentials else None
    
    if not token:
        logger.error("Token is empty")
        raise HTTPException(status_code=401, detail="Token not provided")
    
    try:
        logger.info(f"Verifying token, length: {len(token)}")
        public_key = get_keycloak_public_key(token)
        logger.info("Public key obtained")
        
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            options={"verify_exp": True, "verify_aud": False}
        )
        logger.info(f"Token verified, user: {payload.get('preferred_username')}")
        return payload
    except jwt.ExpiredSignatureError:
        logger.error("Token expired")
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError as e:
        logger.error(f"JWT error: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")

def get_clickhouse_client():
    return Client(
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        database=CLICKHOUSE_DB,
        user=CLICKHOUSE_USER,
        password=CLICKHOUSE_PASSWORD
    )

def get_last_processed_date(client: Client) -> Optional[date]:
    result = client.execute("SELECT last_processed_date FROM etl_watermark ORDER BY updated_at DESC LIMIT 1")
    if result:
        return result[0][0]
    
    result = client.execute("SELECT max(date) FROM user_reports_mart")
    if result and result[0][0]:
        return result[0][0]
    
    return None

@app.get("/reports")
async def get_reports(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    token_payload: dict = Depends(verify_token)
):
    username = token_payload.get('preferred_username') or token_payload.get('sub')
    if not username:
        raise HTTPException(status_code=401, detail="Username not found in token")
    
    client = get_clickhouse_client()
    
    try:
        last_processed = get_last_processed_date(client)
        
        if start_date:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
        else:
            start = None
        
        if end_date:
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
        else:
            end = last_processed
        
        if start and end and start > end:
            raise HTTPException(status_code=422, detail="Start date must be before end date")
        
        if end and last_processed and end > last_processed:
            raise HTTPException(
                status_code=422,
                detail=f"Данные за запрошенный период ещё не обработаны. Последняя обработанная дата: {last_processed}"
            )
        
        query = f"SELECT * FROM reports_db.user_reports_mart WHERE username = '{username}'"
        
        if start:
            query += f" AND date >= '{start}'"
        
        if end:
            query += f" AND date <= '{end}'"
        
        query += " ORDER BY date DESC"
        
        result = client.execute(query)
        
        if not result:
            raise HTTPException(status_code=404, detail="Данные не найдены")
        
        reports = []
        for row in result:
            reports.append({
                'user_id': row[0],
                'username': row[1],
                'prosthesis_id': row[2],
                'date': str(row[3]),
                'total_movements': row[4],
                'avg_reaction_time': row[5],
                'min_reaction_time': row[6],
                'max_reaction_time': row[7],
                'customer_name': row[8],
                'customer_email': row[9],
                'order_date': str(row[10]) if row[10] else None,
                'prosthesis_type': row[11]
            })
        
        return {
            'username': username,
            'last_processed_date': str(last_processed) if last_processed else None,
            'reports': reports
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    finally:
        client.disconnect()

@app.get("/health")
async def health():
    return {"status": "ok"}
