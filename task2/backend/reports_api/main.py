from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import requests
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Reports API", description="API for retrieving user reports from OLAP database")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ALGORITHM = "RS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
KEYCLOAK_URL = os.getenv("KEYCLOAK_URL", "http://keycloak:8080")
REALM = os.getenv("KEYCLOAK_REALM", "reports-realm")

class ReportResponse(BaseModel):
    client_id: str
    name: str
    email: str
    total_events: int
    last_event: str

def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        jwks_url = f"{KEYCLOAK_URL}/realms/{REALM}/protocol/openid-connect/certs"
        response = requests.get(jwks_url)
        if response.status_code != 200:
            print(f"JWKS request failed: {response.status_code}")
            raise credentials_exception
        jwks = response.json()
        print(f"Token prefix: {token[:50]}...")
        payload = jwt.decode(token, jwks, algorithms=[ALGORITHM], options={"verify_aud": False})
        sub: str = payload.get("sub")
        print(f"Decoded sub: {sub}")
        if sub is None:
            raise credentials_exception
        # Assume sub is client_id as string
        return sub
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise credentials_exception

def get_db_connection():
    return psycopg2.connect(
        host=os.getenv("OLAP_DB_HOST", "olap_db"),
        port=os.getenv("OLAP_DB_PORT", "5432"),
        database=os.getenv("OLAP_DB_NAME", "olap"),
        user=os.getenv("OLAP_DB_USER", "olap_user"),
        password=os.getenv("OLAP_DB_PASSWORD", "olap_password")
    )

@app.get("/")
def read_root():
    return {"message": "Reports API is running"}

@app.post("/reports", response_model=ReportResponse)
def get_report(current_client_id: str = Depends(get_current_user)):
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT client_id, name, email, total_events, last_event
            FROM client_datamart
            WHERE client_id = %s
        """, (current_client_id,))
        result = cursor.fetchone()
        print(f"Query result: {result}")
        cursor.close()
        conn.close()

        if not result:
            print("No result, raising 404")
            raise HTTPException(status_code=404, detail="Client not found")

        # Convert last_event datetime to string
        if result['last_event']:
            result['last_event'] = result['last_event'].isoformat()
        else:
            result['last_event'] = ""

        print(f"Processed result: {result}")
        return ReportResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))