from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from clickhouse_driver import Client
import os
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import requests
from fastapi.middleware.cors import CORSMiddleware
import boto3
import json
from datetime import datetime, timedelta

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

# S3 configuration
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "http://minio:9000")
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY", "minioadmin")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY", "minioadmin")
S3_BUCKET = os.getenv("S3_BUCKET", "reports")
CDN_URL = os.getenv("CDN_URL", "http://localhost:8084")

# Initialize S3 client
s3_client = boto3.client(
    's3',
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    region_name='us-east-1'  # MinIO doesn't care about region
)

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
        email: str = payload.get("email")
        print(f"Decoded email: {email}")
        if email is None:
            raise credentials_exception
        # Use email as client_id
        return email
    except JWTError as e:
        print(f"JWT Error: {e}")
        raise credentials_exception

def get_db_connection():
    return Client(
        host=os.getenv("OLAP_DB_HOST", "clickhouse"),
        port=int(os.getenv("OLAP_DB_PORT", "9000")),
        database=os.getenv("OLAP_DB_NAME", "default"),
        user=os.getenv("OLAP_DB_USER", "default"),
        password=os.getenv("OLAP_DB_PASSWORD", "")
    )

def generate_report(client_id: str):
    """Generate report data from ClickHouse database"""
    client = get_db_connection()
    query = """
        SELECT client_id, name, email, total_events, last_event
        FROM client_datamart
        WHERE client_id = %(client_id)s
    """
    print(f"Querying datamart for client_id={client_id}")
    result = client.execute(query, {"client_id": client_id})
    print(f"Datamart result rows={len(result)}")
    client.disconnect()

    if not result:
        raise HTTPException(status_code=404, detail="Client not found")

    row = result[0]
    return {
        'client_id': row[0],
        'name': row[1],
        'email': row[2],
        'total_events': row[3],
        'last_event': row[4].isoformat() if row[4] else ""
    }

def check_report_in_s3(client_id: str) -> bool:
    """Check if report exists in S3"""
    key = f"reports/{client_id}/report.json"
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=key)
        print(f"Report exists in S3: {key}")
        return True
    except s3_client.exceptions.NoSuchKey:
        print(f"Report not found in S3: {key}")
        return False
    except Exception as e:
        print(f"Error checking S3: {e}")
        return False

def upload_report_to_s3(client_id: str, report_data: dict):
    """Upload report to S3"""
    key = f"reports/{client_id}/report.json"
    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=json.dumps(report_data),
            ContentType='application/json'
        )
        print(f"Uploaded report to S3: {key}")
    except Exception as e:
        print(f"Error uploading to S3: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload report")

def get_report_url(client_id: str) -> str:
    """Get CDN URL for the report"""
    return f"{CDN_URL}/{S3_BUCKET}/reports/{client_id}/report.json"

def init_s3_bucket():
    """Initialize S3 bucket if it doesn't exist"""
    try:
        s3_client.head_bucket(Bucket=S3_BUCKET)
        print(f"Bucket {S3_BUCKET} exists")
    except s3_client.exceptions.NoSuchBucket:
        try:
            s3_client.create_bucket(Bucket=S3_BUCKET)
            print(f"Bucket {S3_BUCKET} created")
        except Exception as e:
            print(f"Error creating S3 bucket: {e}")
    except Exception as e:
        print(f"Error initializing S3 bucket: {e}")
        # Try to create anyway
        try:
            s3_client.create_bucket(Bucket=S3_BUCKET)
            print(f"Bucket {S3_BUCKET} created on error")
        except Exception as e2:
            print(f"Failed to create bucket: {e2}")

# Initialize bucket on startup
init_s3_bucket()

@app.get("/")
def read_root():
    return {"message": "Reports API is running"}

@app.get("/test")
def get_report(current_client_id: str = Depends(get_current_user)):
    try:
        # Check if report exists in S3
        if check_report_in_s3(current_client_id):
            # Return CDN URL
            return {"report_url": get_report_url(current_client_id)}
        else:
            # Generate report
            report_data = generate_report(current_client_id)
            # Upload to S3
            upload_report_to_s3(current_client_id, report_data)
            # Return CDN URL
            return {"report_url": get_report_url(current_client_id)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.api_route("/reports", methods=["POST", "OPTIONS"])
def get_report(current_client_id: str = Depends(get_current_user)):
    try:
        # Check if report exists in S3
        if check_report_in_s3(current_client_id):
            # Return CDN URL
            return {"report_url": get_report_url(current_client_id)}
        else:
            # Generate report
            report_data = generate_report(current_client_id)
            # Upload to S3
            upload_report_to_s3(current_client_id, report_data)
            # Return CDN URL
            return {"report_url": get_report_url(current_client_id)}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Exception: {e}")
        raise HTTPException(status_code=500, detail=str(e))