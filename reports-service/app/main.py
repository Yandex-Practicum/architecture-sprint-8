"""
BionicPRO Reports Service - Main Application Entry Point.

FastAPI service for retrieving prosthesis usage reports from ClickHouse OLAP database.
Reports are pre-aggregated by ETL pipeline - this service performs simple SELECT queries.

Data Sources (Задание 4 - CDC Architecture):
    - CRM data: Debezium CDC → Kafka → ClickHouse (real-time)
    - Telemetry: ETL batch load → ClickHouse (every 15 min)

API Endpoints:
    GET  /api/reports              - List available reports for authenticated user
    GET  /api/reports/summary      - Get user's overall summary
    GET  /api/reports/{date}       - Get detailed daily report
    DELETE /api/reports/cache      - Clear user's cache

Admin Endpoints (require 'administrator' role):
    GET  /api/reports/admin/{user_id}           - Get reports for any user
    GET  /api/reports/admin/{user_id}/{date}    - Get daily report for any user
    GET  /api/reports/admin/{user_id}/summary   - Get summary for any user

Authentication:
    Bearer token (JWT) from Keycloak via bionicpro-auth BFF.
    - Token signature verified with Keycloak public key
    - Token expiration validated
    - Users can only access their own reports (IDOR protection)
    - Administrators can access any user's reports

Security Features:
    - JWT validation with RS256 signature verification
    - User isolation: users can only see their own data
    - Audit logging: all access to reports is logged
    - Security headers: X-Content-Type-Options, X-Frame-Options, etc.
    - Rate limiting ready (configure in reverse proxy)

Caching:
    Redis cache with 5-minute TTL for report data.
    S3/CDN caching for reduced OLAP load.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import reports
from app.services.clickhouse_service import get_clickhouse_service
from app.services.cache_service import get_cache_service
from app.services.s3_service import get_s3_service
from app.auth.audit_middleware import AuditMiddleware, SecurityHeadersMiddleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")
    logger.info(f"ClickHouse: {settings.clickhouse_host}:{settings.clickhouse_port}")
    logger.info(f"Redis: {settings.redis_host}:{settings.redis_port}")
    logger.info(f"S3/MinIO: {settings.s3_endpoint_url} (bucket: {settings.s3_bucket_name})")
    logger.info(f"CDN: {settings.cdn_base_url} (enabled: {settings.cdn_enabled})")
    logger.info(f"Keycloak: {settings.keycloak_url}/realms/{settings.keycloak_realm}")
    logger.info("Security: JWT validation enabled, audit logging enabled")

    yield

    # Shutdown
    logger.info("Shutting down Reports Service")
    get_clickhouse_service().close()
    get_cache_service().close()
    get_s3_service().close()


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=__doc__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Add security headers middleware (first in chain)
app.add_middleware(SecurityHeadersMiddleware)

# Add audit middleware for logging access
app.add_middleware(AuditMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "DELETE"],  # Only allow safe methods
    allow_headers=["Authorization", "Content-Type"],
)


# Include routers
app.include_router(reports.router)


# ============================================================================
# Health & Info Endpoints
# ============================================================================

@app.get("/", tags=["info"])
async def root():
    """Root endpoint with service info."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "running",
        "docs": "/docs",
        "security": {
            "authentication": "JWT Bearer token required",
            "authorization": "Users can only access their own reports",
            "audit": "All access is logged",
        },
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint.

    Checks connectivity to ClickHouse, Redis, and S3/MinIO.
    """
    clickhouse_ok = get_clickhouse_service().health_check()
    redis_ok = get_cache_service().health_check()
    s3_ok = get_s3_service().health_check()

    status = "healthy" if (clickhouse_ok and redis_ok and s3_ok) else "degraded"

    return {
        "status": status,
        "dependencies": {
            "clickhouse": "ok" if clickhouse_ok else "error",
            "redis": "ok" if redis_ok else "error",
            "s3": "ok" if s3_ok else "error",
        },
        "cdn": {
            "enabled": settings.cdn_enabled,
            "base_url": settings.cdn_base_url,
        },
    }


@app.get("/health/ready", tags=["health"])
async def readiness_check():
    """
    Readiness check for Kubernetes.

    Returns 200 if service is ready to accept traffic.
    """
    clickhouse_ok = get_clickhouse_service().health_check()

    if not clickhouse_ok:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "reason": "ClickHouse unavailable"},
        )

    return {"status": "ready"}


@app.get("/health/live", tags=["health"])
async def liveness_check():
    """
    Liveness check for Kubernetes.

    Returns 200 if service is alive.
    """
    return {"status": "alive"}


@app.get("/health/cdc", tags=["health"])
async def cdc_health_check():
    """
    CDC (Change Data Capture) health check.

    Checks if CDC data is flowing from Debezium → Kafka → ClickHouse.
    Verifies that CRM data tables have recent updates.

    Задание 4: Проверка состояния CDC pipeline.
    """
    try:
        clickhouse = get_clickhouse_service()
        client = clickhouse._get_client()

        # Проверяем наличие данных в CDC таблицах
        cdc_tables_query = """
            SELECT
                'crm_customers' AS table_name,
                count() AS row_count,
                max(_version) AS last_version
            FROM reports.crm_customers FINAL
            WHERE _deleted = 0

            UNION ALL

            SELECT
                'crm_prostheses' AS table_name,
                count() AS row_count,
                max(_version) AS last_version
            FROM reports.crm_prostheses FINAL
            WHERE _deleted = 0

            UNION ALL

            SELECT
                'crm_prosthesis_models' AS table_name,
                count() AS row_count,
                max(_version) AS last_version
            FROM reports.crm_prosthesis_models FINAL
            WHERE _deleted = 0
        """

        result = client.execute(cdc_tables_query)

        cdc_status = {}
        total_rows = 0
        for row in result:
            table_name, row_count, last_version = row
            cdc_status[table_name] = {
                "rows": row_count,
                "last_version": last_version,
            }
            total_rows += row_count

        # Определяем статус
        if total_rows > 0:
            status = "healthy"
            message = "CDC data is available"
        else:
            status = "initializing"
            message = "Waiting for Debezium initial snapshot"

        return {
            "status": status,
            "message": message,
            "cdc_tables": cdc_status,
            "architecture": "Debezium → Kafka → ClickHouse KafkaEngine",
        }

    except Exception as e:
        logger.error(f"CDC health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "message": f"CDC check failed: {str(e)}",
                "cdc_tables": {},
            },
        )


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    # Don't expose internal errors in production
    detail = str(exc) if settings.debug else "An unexpected error occurred"

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": detail,
        },
    )


# ============================================================================
# Run with Uvicorn (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.debug,
    )
