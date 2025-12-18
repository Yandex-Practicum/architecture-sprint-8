from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import aioboto3
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any
import logging
from pydantic import BaseModel
import clickhouse_driver

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BionicPRO Reports Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "olap_db")
CLICKHOUSE_PORT = int(os.getenv("CLICKHOUSE_PORT", 9000))
CLICKHOUSE_DATABASE = os.getenv("CLICKHOUSE_DATABASE", "default")
CLICKHOUSE_USERNAME = os.getenv("CLICKHOUSE_USERNAME", "default")
CLICKHOUSE_PASSWORD = os.getenv("CLICKHOUSE_PASSWORD", "")

S3_ENDPOINT = os.getenv("S3_ENDPOINT", "minio:9000")
S3_ACCESS_KEY_ID = os.getenv("S3_ACCESS_KEY_ID", "minio_user")
S3_SECRET_ACCESS_KEY = os.getenv("S3_SECRET_ACCESS_KEY", "minio_password")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "reports")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
S3_USE_SSL = os.getenv("S3_USE_SSL", "false").lower() == "true"

CDN_HOST = os.getenv("CDN_HOST", "localhost:8888")

class UserReport(BaseModel):
    user_id: int
    username: str
    email: str
    total_sessions: int
    total_signals: int
    total_usage_time: float
    average_session_time: float
    muscle_groups: str
    average_accuracy: float
    last_activity: datetime
    report_generated_at: datetime
    has_data: bool
    message: Optional[str] = None

class ReportSummary(BaseModel):
    total_users: int
    active_users: int
    total_sessions: int
    average_usage: float

class ClickHouseClient:
    def __init__(self):
        self.connection = clickhouse_driver.connect(
            host=CLICKHOUSE_HOST,
            port=CLICKHOUSE_PORT,
            database=CLICKHOUSE_DATABASE,
            user=CLICKHOUSE_USERNAME,
            password=CLICKHOUSE_PASSWORD
        )
    
    def get_user_report(self, user_id: int) -> UserReport:
        try:
            cursor = self.connection.cursor()

            user_query = "SELECT name, email FROM dim_customers WHERE id = %s"
            cursor.execute(user_query, (user_id,))
            user_result = cursor.fetchone()
            
            username = user_result[0] if user_result else ""
            email = user_result[1] if user_result else ""

            report_query = """
                SELECT 
                    user_id,
                    session_count as total_sessions,
                    total_signals,
                    avg_duration * session_count as total_usage_time,
                    avg_duration as average_session_time,
                    muscle_groups,
                    avg_accuracy,
                    report_date as last_activity
                FROM bionicpro.user_reports_realtime 
                WHERE user_id = %s
                ORDER BY report_date DESC
                LIMIT 1
            """
            
            cursor.execute(report_query, (user_id,))
            report_result = cursor.fetchone()
            
            if report_result:
                report = UserReport(
                    user_id=user_id,
                    username=username,
                    email=email,
                    total_sessions=report_result[1],
                    total_signals=report_result[2],
                    total_usage_time=report_result[3],
                    average_session_time=report_result[4],
                    muscle_groups=report_result[5],
                    average_accuracy=report_result[6],
                    last_activity=report_result[7],
                    report_generated_at=datetime.now(),
                    has_data=True
                )
            else:
                report = UserReport(
                    user_id=user_id,
                    username=username,
                    email=email,
                    total_sessions=0,
                    total_signals=0,
                    total_usage_time=0.0,
                    average_session_time=0.0,
                    muscle_groups="",
                    average_accuracy=0.0,
                    last_activity=datetime.now(),
                    report_generated_at=datetime.now(),
                    has_data=False,
                    message="Данные отчёта пока отсутствуют"
                )
            
            cursor.close()
            return report
            
        except Exception as e:
            logger.error(f"Error getting user report: {e}")
            return UserReport(
                user_id=user_id,
                username="",
                email="",
                total_sessions=0,
                total_signals=0,
                total_usage_time=0.0,
                average_session_time=0.0,
                muscle_groups="",
                average_accuracy=0.0,
                last_activity=datetime.now(),
                report_generated_at=datetime.now(),
                has_data=False,
                message=f"Error retrieving report: {str(e)}"
            )
    
    def get_report_summary(self) -> ReportSummary:
        try:
            cursor = self.connection.cursor()
            
            query = """
                SELECT 
                    COUNT(DISTINCT user_id) as total_users,
                    COUNT(DISTINCT CASE WHEN last_activity > now() - INTERVAL 30 DAY THEN user_id END) as active_users,
                    SUM(total_sessions) as total_sessions,
                    AVG(total_usage_time) as average_usage
                FROM default.report_patient_activity_mart
            """
            
            cursor.execute(query)
            result = cursor.fetchone()
            
            summary = ReportSummary(
                total_users=result[0],
                active_users=result[1],
                total_sessions=result[2],
                average_usage=result[3]
            )
            
            cursor.close()
            return summary
            
        except Exception as e:
            logger.error(f"Error getting report summary: {e}")
            return ReportSummary(
                total_users=0,
                active_users=0,
                total_sessions=0,
                average_usage=0.0
            )

class S3Client:
    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=S3_ACCESS_KEY_ID,
            aws_secret_access_key=S3_SECRET_ACCESS_KEY,
            region_name=S3_REGION
        )
    
    async def report_exists(self, user_id: int) -> bool:
        try:
            async with self.session.client(
                's3',
                endpoint_url=f"http://{S3_ENDPOINT}" if not S3_USE_SSL else f"https://{S3_ENDPOINT}",
                use_ssl=S3_USE_SSL
            ) as s3:
                file_name = f"report_{user_id}.json"
                try:
                    await s3.head_object(Bucket=S3_BUCKET_NAME, Key=file_name)
                    return True
                except Exception:
                    return False
        except Exception as e:
            logger.error(f"Error checking if report exists: {e}")
            return False
    
    async def get_report(self, user_id: int) -> UserReport:
        try:
            async with self.session.client(
                's3',
                endpoint_url=f"http://{S3_ENDPOINT}" if not S3_USE_SSL else f"https://{S3_ENDPOINT}",
                use_ssl=S3_USE_SSL
            ) as s3:
                file_name = f"report_{user_id}.json"
                response = await s3.get_object(Bucket=S3_BUCKET_NAME, Key=file_name)
                data = await response['Body'].read()
                report_data = json.loads(data.decode('utf-8'))

                report = UserReport(**report_data)
                return report
        except Exception as e:
            logger.error(f"Error getting report from S3: {e}")
            raise HTTPException(status_code=500, detail=f"Error retrieving report: {str(e)}")
    
    async def store_report(self, user_id: int, report: UserReport):
        try:
            async with self.session.client(
                's3',
                endpoint_url=f"http://{S3_ENDPOINT}" if not S3_USE_SSL else f"https://{S3_ENDPOINT}",
                use_ssl=S3_USE_SSL
            ) as s3:
                file_name = f"report_{user_id}.json"
                try:
                    await s3.head_bucket(Bucket=S3_BUCKET_NAME)
                except Exception:
                    await s3.create_bucket(Bucket=S3_BUCKET_NAME)

                data = json.dumps(report.dict(), default=str, indent=2)
                await s3.put_object(
                    Bucket=S3_BUCKET_NAME,
                    Key=file_name,
                    Body=data,
                    ContentType='application/json'
                )
        except Exception as e:
            logger.error(f"Error storing report to S3: {e}")
            raise HTTPException(status_code=500, detail=f"Error storing report: {str(e)}")
    
    def generate_cdn_link(self, user_id: int) -> str:
        file_name = f"report_{user_id}.json"
        return f"http://{CDN_HOST}/{S3_BUCKET_NAME}/{file_name}"

clickhouse_client = ClickHouseClient()
s3_client = S3Client()

async def get_current_user(request: Request):
    user_id = request.headers.get("X-User-ID")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not provided")
    
    try:
        return int(user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid user ID")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/api/v1/reports")
async def get_reports(current_user_id: int = Depends(get_current_user)):
    try:
        exists = await s3_client.report_exists(current_user_id)
        
        if exists:
            report = await s3_client.get_report(current_user_id)
            return report

        report = clickhouse_client.get_user_report(current_user_id)
        
        if report.has_data:
            await s3_client.store_report(current_user_id, report)
        
        return report
        
    except Exception as e:
        logger.error(f"Error getting reports: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving reports: {str(e)}")

@app.post("/api/v1/reports/generate")
async def generate_reports(current_user_id: int = Depends(get_current_user)):
    try:
        exists = await s3_client.report_exists(current_user_id)
        
        if exists:
            cdn_link = s3_client.generate_cdn_link(current_user_id)
            return {"url": cdn_link}

        report = clickhouse_client.get_user_report(current_user_id)
        
        if not report.has_data:
            return {"error": "Данные для отчета пока не найдены"}

        await s3_client.store_report(current_user_id, report)
        
        cdn_link = s3_client.generate_cdn_link(current_user_id)
        return {"url": cdn_link}
        
    except Exception as e:
        logger.error(f"Error generating reports: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating reports: {str(e)}")

@app.get("/api/v1/reports/summary")
async def get_report_summary():
    try:
        summary = clickhouse_client.get_report_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting report summary: {e}")
        raise HTTPException(status_code=500, detail=f"Error retrieving summary: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5003)
