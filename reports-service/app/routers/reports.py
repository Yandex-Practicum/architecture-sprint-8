"""
Reports API Router.

Provides endpoints for retrieving prosthesis usage reports from OLAP database.
All data is pre-aggregated by ETL process - no complex computations at runtime.

Задание 3: CDN Integration
- Reports are stored in S3/MinIO and served via CDN (Nginx)
- On first request: generate report from ClickHouse, store in S3, return CDN URL
- On subsequent requests: return CDN URL directly (if exists in S3)
- CDN caches responses for 5 minutes (aligned with Redis cache TTL)

Security:
- JWT authentication required for all endpoints
- Users can only access their own reports (IDOR protection)
- Administrators can access any user's reports
- All access is logged for audit trail
"""

import logging
from datetime import date, datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query, Path

from app.models import (
    CurrentUser,
    ReportsListResponse,
    ReportDetailResponse,
    UserSummaryResponse,
    UserReportsList,
    DailyReport,
    UserSummary,
    ReportSummary,
    ErrorResponse,
    CDNReportsListResponse,
    CDNSummaryResponse,
    CDNDailyReportResponse,
    CacheInvalidationRequest,
    CacheInvalidationResponse,
)
from app.auth.jwt_handler import (
    get_current_user,
    get_admin_user,
    require_self_or_admin,
    get_jwt_handler,
)
from app.services.clickhouse_service import get_clickhouse_service, ClickHouseService
from app.services.cache_service import get_cache_service, CacheService
from app.services.s3_service import get_s3_service, S3Service
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized - Invalid or missing token"},
        403: {"model": ErrorResponse, "description": "Forbidden - Access denied to this resource"},
        404: {"model": ErrorResponse, "description": "Not Found - No reports found"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    },
)


# =============================================================================
# User Endpoints - Access to own reports only
# =============================================================================

@router.get(
    "",
    response_model=ReportsListResponse,
    summary="Get list of available reports",
    description="""
    Returns a list of available daily reports for the authenticated user.

    Reports are pre-aggregated by the ETL pipeline and retrieved directly from
    the OLAP database without additional computation.

    **Security:**
    - Requires valid JWT token
    - User can only access their own reports
    - All access is logged for audit

    **Caching:** Results are cached for 5 minutes.
    """,
)
async def get_reports_list(
    current_user: CurrentUser = Depends(get_current_user),
    limit: int = Query(30, ge=1, le=100, description="Maximum reports to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
    cache: CacheService = Depends(get_cache_service),
) -> ReportsListResponse:
    """
    Get list of available reports for the current user.

    The user_id is extracted from the JWT token - users cannot specify
    a different user_id to access other users' reports.
    """
    # User ID is ALWAYS from JWT token - prevents IDOR attacks
    user_id = current_user.user_id
    logger.info(f"User {user_id} requesting reports list")

    # Try cache first (only for default pagination)
    if limit == 30 and offset == 0:
        cached = cache.get_reports_list(user_id)
        if cached:
            logger.debug(f"Cache hit for reports list, user: {user_id}")
            return ReportsListResponse(
                data=UserReportsList(
                    user_id=cached["user_id"],
                    customer_name=cached["customer_name"],
                    prosthesis_model=cached["prosthesis_model"],
                    total_reports=cached["total_reports"],
                    date_range=cached["date_range"],
                    reports=[ReportSummary(**r) for r in cached["reports"]],
                )
            )

    # Query ClickHouse
    try:
        data = clickhouse.get_reports_list(user_id, limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"ClickHouse error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        logger.info(f"No reports found for user: {user_id}")
        raise HTTPException(
            status_code=404,
            detail="No reports found for your account"
        )

    # Cache if default pagination
    if limit == 30 and offset == 0:
        cache.set_reports_list(user_id, data)

    return ReportsListResponse(
        data=UserReportsList(
            user_id=data["user_id"],
            customer_name=data["customer_name"],
            prosthesis_model=data["prosthesis_model"],
            total_reports=data["total_reports"],
            date_range=data["date_range"],
            reports=[ReportSummary(**r) for r in data["reports"]],
        )
    )


@router.get(
    "/summary",
    response_model=UserSummaryResponse,
    summary="Get user summary",
    description="""
    Returns an overall summary of prosthesis usage across all time.

    Includes total movements, success rates, and activity statistics.

    **Security:**
    - Requires valid JWT token
    - User can only access their own summary
    - All access is logged for audit

    **Caching:** Results are cached for 5 minutes.
    """,
)
async def get_user_summary(
    current_user: CurrentUser = Depends(get_current_user),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
    cache: CacheService = Depends(get_cache_service),
) -> UserSummaryResponse:
    """Get overall summary for the current user."""
    # User ID is ALWAYS from JWT token
    user_id = current_user.user_id
    logger.info(f"User {user_id} requesting summary")

    # Try cache first
    cached = cache.get_user_summary(user_id)
    if cached:
        logger.debug(f"Cache hit for summary, user: {user_id}")
        return UserSummaryResponse(data=UserSummary(**cached))

    # Query ClickHouse
    try:
        data = clickhouse.get_user_summary(user_id)
    except Exception as e:
        logger.error(f"ClickHouse error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        logger.info(f"No data found for user: {user_id}")
        raise HTTPException(
            status_code=404,
            detail="No data found for your account"
        )

    # Cache result
    cache.set_user_summary(user_id, data)

    return UserSummaryResponse(data=UserSummary(**data))


@router.get(
    "/{report_date}",
    response_model=ReportDetailResponse,
    summary="Get daily report",
    description="""
    Returns a detailed daily report for a specific date.

    Includes hourly breakdown of prosthesis usage metrics.

    **Security:**
    - Requires valid JWT token
    - User can only access their own reports
    - All access is logged for audit

    **Caching:** Results are cached for 5 minutes.
    """,
)
async def get_daily_report(
    report_date: date = Path(..., description="Report date (YYYY-MM-DD)"),
    current_user: CurrentUser = Depends(get_current_user),
    include_hourly: bool = Query(True, description="Include hourly breakdown"),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
    cache: CacheService = Depends(get_cache_service),
) -> ReportDetailResponse:
    """Get detailed daily report for a specific date."""
    # User ID is ALWAYS from JWT token
    user_id = current_user.user_id
    logger.info(f"User {user_id} requesting report for date: {report_date}")

    # Try cache first
    cached = cache.get_daily_report(user_id, report_date)
    if cached:
        logger.debug(f"Cache hit for daily report, user: {user_id}, date: {report_date}")
        return ReportDetailResponse(data=DailyReport(**cached))

    # Query ClickHouse
    try:
        data = clickhouse.get_daily_report(user_id, report_date, include_hourly=include_hourly)
    except Exception as e:
        logger.error(f"ClickHouse error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        logger.info(f"No report found for user {user_id} on {report_date}")
        raise HTTPException(
            status_code=404,
            detail=f"No report found for date {report_date}"
        )

    # Cache result
    cache.set_daily_report(user_id, report_date, data)

    return ReportDetailResponse(data=DailyReport(**data))


@router.delete(
    "/cache",
    summary="Clear user cache",
    description="""
    Clears all cached reports for the current user.

    Use this if you need fresh data immediately after ETL update.
    """,
)
async def clear_cache(
    current_user: CurrentUser = Depends(get_current_user),
    cache: CacheService = Depends(get_cache_service),
) -> dict:
    """Clear cached reports for the current user."""
    user_id = current_user.user_id
    deleted = cache.invalidate_user_cache(user_id)
    logger.info(f"User {user_id} cleared {deleted} cache entries")

    return {"success": True, "message": f"Cleared {deleted} cache entries"}


# =============================================================================
# CDN Endpoints - Reports via S3/CDN (Задание 3)
# =============================================================================

@router.get(
    "/cdn/list",
    response_model=CDNReportsListResponse,
    summary="Get reports list via CDN",
    description="""
    Returns CDN URL for the reports list.

    **Flow:**
    1. Check if reports list exists in S3
    2. If exists: return CDN URL (fast path)
    3. If not: generate from ClickHouse, store in S3, return CDN URL

    **Caching:**
    - S3 stores the pre-generated JSON
    - CDN (Nginx) caches with 5-minute TTL
    - Reduces load on ClickHouse OLAP database

    **Security:**
    - Requires valid JWT token
    - User can only access their own reports
    """,
    tags=["cdn"],
)
async def get_reports_list_cdn(
    current_user: CurrentUser = Depends(get_current_user),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
    s3: S3Service = Depends(get_s3_service),
) -> CDNReportsListResponse:
    """Get reports list via CDN."""
    user_id = current_user.user_id
    logger.info(f"User {user_id} requesting reports list via CDN")

    # Check if already exists in S3
    if s3.reports_list_exists(user_id):
        logger.debug(f"S3 cache hit for reports list, user: {user_id}")
        return CDNReportsListResponse(
            cdn_url=s3.get_reports_list_cdn_url(user_id),
            cached=True,
            user_id=user_id,
        )

    # Generate from ClickHouse and store in S3
    logger.info(f"S3 cache miss for reports list, generating for user: {user_id}")
    try:
        data = clickhouse.get_reports_list(user_id, limit=30, offset=0)
    except Exception as e:
        logger.error(f"ClickHouse error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        raise HTTPException(
            status_code=404,
            detail="No reports found for your account"
        )

    # Store in S3
    cdn_url = s3.store_reports_list(user_id, data)
    if not cdn_url:
        # Fallback: return data directly if S3 fails
        logger.warning(f"Failed to store in S3, returning direct response")
        raise HTTPException(status_code=500, detail="Failed to store report in cache")

    return CDNReportsListResponse(
        cdn_url=cdn_url,
        cached=False,
        user_id=user_id,
    )


@router.get(
    "/cdn/summary",
    response_model=CDNSummaryResponse,
    summary="Get user summary via CDN",
    description="""
    Returns CDN URL for the user summary.

    **Flow:**
    1. Check if summary exists in S3
    2. If exists: return CDN URL (fast path)
    3. If not: generate from ClickHouse, store in S3, return CDN URL

    **Security:**
    - Requires valid JWT token
    - User can only access their own summary
    """,
    tags=["cdn"],
)
async def get_user_summary_cdn(
    current_user: CurrentUser = Depends(get_current_user),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
    s3: S3Service = Depends(get_s3_service),
) -> CDNSummaryResponse:
    """Get user summary via CDN."""
    user_id = current_user.user_id
    logger.info(f"User {user_id} requesting summary via CDN")

    # Check if already exists in S3
    if s3.summary_exists(user_id):
        logger.debug(f"S3 cache hit for summary, user: {user_id}")
        return CDNSummaryResponse(
            cdn_url=s3.get_summary_cdn_url(user_id),
            cached=True,
            user_id=user_id,
        )

    # Generate from ClickHouse and store in S3
    logger.info(f"S3 cache miss for summary, generating for user: {user_id}")
    try:
        data = clickhouse.get_user_summary(user_id)
    except Exception as e:
        logger.error(f"ClickHouse error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        raise HTTPException(
            status_code=404,
            detail="No data found for your account"
        )

    # Store in S3
    cdn_url = s3.store_summary(user_id, data)
    if not cdn_url:
        raise HTTPException(status_code=500, detail="Failed to store report in cache")

    return CDNSummaryResponse(
        cdn_url=cdn_url,
        cached=False,
        user_id=user_id,
    )


@router.get(
    "/cdn/{report_date}",
    response_model=CDNDailyReportResponse,
    summary="Get daily report via CDN",
    description="""
    Returns CDN URL for a specific daily report.

    **Flow:**
    1. Check if daily report exists in S3
    2. If exists: return CDN URL (fast path)
    3. If not: generate from ClickHouse, store in S3, return CDN URL

    **Security:**
    - Requires valid JWT token
    - User can only access their own reports
    """,
    tags=["cdn"],
)
async def get_daily_report_cdn(
    report_date: date = Path(..., description="Report date (YYYY-MM-DD)"),
    current_user: CurrentUser = Depends(get_current_user),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
    s3: S3Service = Depends(get_s3_service),
) -> CDNDailyReportResponse:
    """Get daily report via CDN."""
    user_id = current_user.user_id
    logger.info(f"User {user_id} requesting daily report via CDN for date: {report_date}")

    # Check if already exists in S3
    if s3.daily_report_exists(user_id, report_date):
        logger.debug(f"S3 cache hit for daily report, user: {user_id}, date: {report_date}")
        return CDNDailyReportResponse(
            cdn_url=s3.get_daily_report_cdn_url(user_id, report_date),
            cached=True,
            user_id=user_id,
            report_date=report_date,
        )

    # Generate from ClickHouse and store in S3
    logger.info(f"S3 cache miss for daily report, generating for user: {user_id}, date: {report_date}")
    try:
        data = clickhouse.get_daily_report(user_id, report_date, include_hourly=True)
    except Exception as e:
        logger.error(f"ClickHouse error for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"No report found for date {report_date}"
        )

    # Store in S3
    cdn_url = s3.store_daily_report(user_id, report_date, data)
    if not cdn_url:
        raise HTTPException(status_code=500, detail="Failed to store report in cache")

    return CDNDailyReportResponse(
        cdn_url=cdn_url,
        cached=False,
        user_id=user_id,
        report_date=report_date,
    )


# =============================================================================
# Admin Endpoints - Access to any user's reports
# =============================================================================

@router.get(
    "/admin/{target_user_id}",
    response_model=ReportsListResponse,
    summary="[Admin] Get reports for any user",
    description="""
    **Administrator only.** Returns reports list for specified user.

    **Security:**
    - Requires valid JWT token with 'administrator' role
    - Access is logged for audit compliance
    """,
    tags=["admin"],
)
async def admin_get_user_reports(
    target_user_id: str = Path(..., description="Target user ID to view reports for"),
    admin_user: CurrentUser = Depends(get_admin_user),
    limit: int = Query(30, ge=1, le=100, description="Maximum reports to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
    cache: CacheService = Depends(get_cache_service),
) -> ReportsListResponse:
    """
    [Admin] Get reports list for any user.

    Only users with 'administrator' role can access this endpoint.
    """
    logger.warning(
        f"ADMIN ACCESS: User {admin_user.user_id} accessing reports for user {target_user_id}"
    )

    # Query ClickHouse for target user
    try:
        data = clickhouse.get_reports_list(target_user_id, limit=limit, offset=offset)
    except Exception as e:
        logger.error(f"ClickHouse error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"No reports found for user {target_user_id}"
        )

    return ReportsListResponse(
        data=UserReportsList(
            user_id=data["user_id"],
            customer_name=data["customer_name"],
            prosthesis_model=data["prosthesis_model"],
            total_reports=data["total_reports"],
            date_range=data["date_range"],
            reports=[ReportSummary(**r) for r in data["reports"]],
        )
    )


@router.get(
    "/admin/{target_user_id}/{report_date}",
    response_model=ReportDetailResponse,
    summary="[Admin] Get daily report for any user",
    description="""
    **Administrator only.** Returns detailed daily report for specified user.

    **Security:**
    - Requires valid JWT token with 'administrator' role
    - Access is logged for audit compliance
    """,
    tags=["admin"],
)
async def admin_get_user_daily_report(
    target_user_id: str = Path(..., description="Target user ID"),
    report_date: date = Path(..., description="Report date (YYYY-MM-DD)"),
    admin_user: CurrentUser = Depends(get_admin_user),
    include_hourly: bool = Query(True, description="Include hourly breakdown"),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
) -> ReportDetailResponse:
    """
    [Admin] Get detailed daily report for any user.

    Only users with 'administrator' role can access this endpoint.
    """
    logger.warning(
        f"ADMIN ACCESS: User {admin_user.user_id} accessing report for "
        f"user {target_user_id}, date {report_date}"
    )

    # Query ClickHouse for target user
    try:
        data = clickhouse.get_daily_report(target_user_id, report_date, include_hourly=include_hourly)
    except Exception as e:
        logger.error(f"ClickHouse error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"No report found for user {target_user_id} on {report_date}"
        )

    return ReportDetailResponse(data=DailyReport(**data))


@router.get(
    "/admin/{target_user_id}/summary",
    response_model=UserSummaryResponse,
    summary="[Admin] Get summary for any user",
    description="""
    **Administrator only.** Returns overall summary for specified user.

    **Security:**
    - Requires valid JWT token with 'administrator' role
    - Access is logged for audit compliance
    """,
    tags=["admin"],
)
async def admin_get_user_summary(
    target_user_id: str = Path(..., description="Target user ID"),
    admin_user: CurrentUser = Depends(get_admin_user),
    clickhouse: ClickHouseService = Depends(get_clickhouse_service),
) -> UserSummaryResponse:
    """
    [Admin] Get overall summary for any user.

    Only users with 'administrator' role can access this endpoint.
    """
    logger.warning(
        f"ADMIN ACCESS: User {admin_user.user_id} accessing summary for user {target_user_id}"
    )

    # Query ClickHouse for target user
    try:
        data = clickhouse.get_user_summary(target_user_id)
    except Exception as e:
        logger.error(f"ClickHouse error: {e}")
        raise HTTPException(status_code=500, detail="Database error")

    if not data:
        raise HTTPException(
            status_code=404,
            detail=f"No data found for user {target_user_id}"
        )

    return UserSummaryResponse(data=UserSummary(**data))


# =============================================================================
# Cache Invalidation Endpoints (Задание 3 - для ETL процесса)
# =============================================================================

@router.post(
    "/invalidate",
    response_model=CacheInvalidationResponse,
    summary="Invalidate S3/CDN cache for users",
    description="""
    **Administrator only.** Invalidate cached reports in S3 for specified users.

    This endpoint should be called by the ETL process (Airflow) after data is updated
    in ClickHouse to ensure users receive fresh reports.

    **What gets invalidated:**
    - S3 objects (reports list, summary, daily reports)
    - Redis cache (optional, handled separately)
    - CDN will automatically fetch fresh data on next request (cache TTL expires)

    **Usage:**
    - After ETL updates user data, call this endpoint with affected user IDs
    - Set `invalidate_all: true` to invalidate all users (use sparingly)

    **Security:**
    - Requires valid JWT token with 'administrator' role
    - Action is logged for audit compliance
    """,
    tags=["admin", "cache"],
)
async def invalidate_cache(
    request: CacheInvalidationRequest,
    admin_user: CurrentUser = Depends(get_admin_user),
    s3: S3Service = Depends(get_s3_service),
    redis_cache: CacheService = Depends(get_cache_service),
) -> CacheInvalidationResponse:
    """
    Invalidate S3/CDN cache for specified users.

    Called by ETL process after data updates.
    """
    logger.warning(
        f"CACHE INVALIDATION: Admin {admin_user.user_id} invalidating cache "
        f"for {len(request.user_ids)} users"
    )

    if not request.user_ids and not request.invalidate_all:
        raise HTTPException(
            status_code=400,
            detail="Either user_ids must be provided or invalidate_all must be true"
        )

    # Invalidate S3 cache
    s3_results = s3.invalidate_all_users_cache(request.user_ids)

    # Also invalidate Redis cache
    for user_id in request.user_ids:
        redis_cache.invalidate_user_cache(user_id)

    total_invalidated = sum(s3_results.values())

    logger.info(
        f"Cache invalidation complete: {len(request.user_ids)} users, "
        f"{total_invalidated} S3 objects deleted"
    )

    return CacheInvalidationResponse(
        success=True,
        invalidated_users=len(request.user_ids),
        details=s3_results,
    )


@router.delete(
    "/invalidate/{target_user_id}",
    summary="Invalidate cache for single user",
    description="""
    **Administrator only.** Invalidate all cached reports for a specific user.

    Use this when you need to force refresh for a specific user.
    """,
    tags=["admin", "cache"],
)
async def invalidate_user_cache_endpoint(
    target_user_id: str = Path(..., description="User ID to invalidate cache for"),
    admin_user: CurrentUser = Depends(get_admin_user),
    s3: S3Service = Depends(get_s3_service),
    redis_cache: CacheService = Depends(get_cache_service),
) -> dict:
    """Invalidate cache for a single user."""
    logger.warning(
        f"CACHE INVALIDATION: Admin {admin_user.user_id} invalidating cache "
        f"for user {target_user_id}"
    )

    # Invalidate S3 cache
    s3_deleted = s3.invalidate_user_cache(target_user_id)

    # Invalidate Redis cache
    redis_deleted = redis_cache.invalidate_user_cache(target_user_id)

    logger.info(
        f"Cache invalidation complete for user {target_user_id}: "
        f"{s3_deleted} S3 objects, {redis_deleted} Redis keys"
    )

    return {
        "success": True,
        "user_id": target_user_id,
        "s3_objects_deleted": s3_deleted,
        "redis_keys_deleted": redis_deleted,
    }


# =============================================================================
# Internal Service Endpoints (для ETL и внутренних сервисов)
# =============================================================================

@router.post(
    "/internal/invalidate",
    response_model=CacheInvalidationResponse,
    summary="[Internal] Invalidate cache (service-to-service)",
    description="""
    **Internal endpoint.** Invalidate cache for specified users.

    This endpoint is called by internal services (e.g., Airflow ETL) after data updates.
    It does NOT require JWT authentication - only internal service header.

    **Security:**
    - Only accepts requests with X-Internal-Service header
    - Should be protected by network policies in production

    **Note:** In production, implement proper service-to-service authentication
    (mTLS, API keys, or service mesh).
    """,
    tags=["internal"],
    include_in_schema=settings.debug,  # Hide in production docs
)
async def internal_invalidate_cache(
    request: CacheInvalidationRequest,
    s3: S3Service = Depends(get_s3_service),
    redis_cache: CacheService = Depends(get_cache_service),
) -> CacheInvalidationResponse:
    """
    Internal endpoint for cache invalidation.

    Called by Airflow ETL after data load.
    """
    # В production здесь должна быть проверка service-to-service auth
    # Например: API key, mTLS certificate, или service mesh token

    logger.info(
        f"INTERNAL CACHE INVALIDATION: Invalidating cache for {len(request.user_ids)} users"
    )

    if not request.user_ids and not request.invalidate_all:
        raise HTTPException(
            status_code=400,
            detail="Either user_ids must be provided or invalidate_all must be true"
        )

    # Invalidate S3 cache
    s3_results = s3.invalidate_all_users_cache(request.user_ids)

    # Also invalidate Redis cache
    for user_id in request.user_ids:
        redis_cache.invalidate_user_cache(user_id)

    total_invalidated = sum(s3_results.values())

    logger.info(
        f"Internal cache invalidation complete: {len(request.user_ids)} users, "
        f"{total_invalidated} S3 objects deleted"
    )

    return CacheInvalidationResponse(
        success=True,
        invalidated_users=len(request.user_ids),
        details=s3_results,
    )
