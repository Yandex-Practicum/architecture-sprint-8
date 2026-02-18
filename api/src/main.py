import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .models import ReportResponse, ErrorResponse, HealthResponse
from .clickhouse import clickhouse_client
from .auth import verify_jwt_token, require_user_id_match

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.API_TITLE,
    version=settings.API_VERSION,
    description="API service for BionicPRO prosthetic reports from OLAP database",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    logger.info(f"Starting {settings.API_TITLE} v{settings.API_VERSION}")
    logger.info(f"ClickHouse: {settings.CLICKHOUSE_HOST}:{settings.CLICKHOUSE_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down Reports API")
    clickhouse_client.close()


@app.get("/", tags=["System"])
async def root():
    return {
        "service": settings.API_TITLE,
        "version": settings.API_VERSION,
        "status": "running"
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    clickhouse_ok = clickhouse_client.check_connection()
    
    return HealthResponse(
        status="healthy" if clickhouse_ok else "degraded",
        clickhouse_connected=clickhouse_ok,
        timestamp=datetime.utcnow()
    )


@app.get(
    "/reports",
    response_model=ReportResponse,
    tags=["Reports"],
    responses={
        200: {"description": "Report successfully retrieved"},
        401: {"model": ErrorResponse, "description": "Unauthorized - invalid or missing token"},
        403: {"model": ErrorResponse, "description": "Forbidden - cannot access other user's reports"},
        404: {"model": ErrorResponse, "description": "Report not found"},
        400: {"model": ErrorResponse, "description": "Invalid parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_report(
    user_id: int = Query(..., description="User ID", gt=0),
    period: str = Query(..., description="Period in YYYY-MM format (e.g., 2026-01)"),
    current_user: dict = Depends(verify_jwt_token)
):
    if current_user["user_id"] != user_id:
        logger.warning(
            f"Authorization failed: user {current_user['user_id']} "
            f"attempted to access reports for user {user_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="You can only access your own reports"
        )
    
    try:
        try:
            datetime.strptime(period, "%Y-%m")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Period must be in YYYY-MM format (e.g., 2026-01)"
            )
        
        report = clickhouse_client.get_report(user_id=user_id, period=period)
        
        if report is None:
            raise HTTPException(
                status_code=404,
                detail=f"Report not found for user_id={user_id}, period={period}. "
                       f"Make sure the period has been processed by Airflow ETL."
            )
        
        logger.info(f"Report retrieved: user_id={user_id}, period={period}")
        return report
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving report: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get(
    "/reports/user/{user_id}",
    response_model=list[ReportResponse],
    tags=["Reports"],
    responses={
        200: {"description": "Reports successfully retrieved"},
        401: {"model": ErrorResponse, "description": "Unauthorized - invalid or missing token"},
        403: {"model": ErrorResponse, "description": "Forbidden - cannot access other user's reports"},
        500: {"model": ErrorResponse, "description": "Internal server error"}
    }
)
async def get_user_reports(
    user_id: int,
    limit: int = Query(10, description="Maximum number of reports to return", ge=1, le=100),
    current_user: dict = Depends(verify_jwt_token)
):
    if current_user["user_id"] != user_id:
        logger.warning(
            f"Authorization failed: user {current_user['user_id']} "
            f"attempted to access reports for user {user_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="You can only access your own reports"
        )
    
    try:
        reports = clickhouse_client.get_user_reports(user_id=user_id, limit=limit)
        logger.info(f"Retrieved {len(reports)} reports for user_id={user_id}")
        return reports
        
    except Exception as e:
        logger.error(f"Error retrieving user reports: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
        log_level="info"
    )
