"""
Pydantic models for Reports Service API.
"""

from datetime import date, datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ============================================================================
# Report Data Models
# ============================================================================

class HourlyStats(BaseModel):
    """Hourly statistics for a prosthesis."""

    hour: int = Field(..., ge=0, le=23, description="Hour of day (0-23)")
    movements_count: int = Field(..., ge=0, description="Total movements in this hour")
    successful_movements: int = Field(..., ge=0, description="Successful movements")
    success_rate: float = Field(..., ge=0, le=100, description="Success rate percentage")
    avg_response_time: float = Field(..., ge=0, description="Average response time in ms")
    avg_battery_level: float = Field(..., ge=0, le=100, description="Average battery level %")
    error_count: int = Field(..., ge=0, description="Number of errors")


class DailyReport(BaseModel):
    """Daily report for a user's prosthesis."""

    report_date: date = Field(..., description="Report date")
    user_id: str = Field(..., description="User identifier")
    customer_name: str = Field(..., description="Customer full name")
    prosthesis_id: int = Field(..., description="Prosthesis ID")
    prosthesis_model: str = Field(..., description="Prosthesis model name")
    prosthesis_serial: str = Field(..., description="Prosthesis serial number")
    customer_region: str = Field(..., description="Customer region")

    # Daily aggregates
    total_movements: int = Field(..., ge=0, description="Total movements for the day")
    total_successful: int = Field(..., ge=0, description="Total successful movements")
    daily_success_rate: float = Field(..., ge=0, le=100, description="Daily success rate %")
    avg_response_time: float = Field(..., ge=0, description="Average response time in ms")
    avg_battery_level: float = Field(..., ge=0, le=100, description="Average battery level %")
    min_battery_level: int = Field(..., ge=0, le=100, description="Minimum battery level %")
    max_actuator_temp: float = Field(..., ge=0, description="Maximum actuator temperature")
    total_errors: int = Field(..., ge=0, description="Total errors for the day")
    active_hours: int = Field(..., ge=0, le=24, description="Number of active hours")

    # Hourly breakdown (optional)
    hourly_stats: Optional[List[HourlyStats]] = Field(None, description="Hourly breakdown")


class ReportSummary(BaseModel):
    """Summary of available reports for a user."""

    report_date: date = Field(..., description="Report date")
    total_movements: int = Field(..., ge=0, description="Total movements")
    total_errors: int = Field(..., ge=0, description="Total errors")
    active_hours: int = Field(..., ge=0, description="Active hours")


class UserReportsList(BaseModel):
    """List of available reports for a user."""

    user_id: str = Field(..., description="User identifier")
    customer_name: str = Field(..., description="Customer name")
    prosthesis_model: str = Field(..., description="Prosthesis model")
    total_reports: int = Field(..., ge=0, description="Total number of available reports")
    date_range: dict = Field(..., description="Available date range")
    reports: List[ReportSummary] = Field(..., description="List of report summaries")


class UserSummary(BaseModel):
    """Overall summary for a user across all time."""

    user_id: str = Field(..., description="User identifier")
    customer_name: str = Field(..., description="Customer name")
    prosthesis_model: str = Field(..., description="Prosthesis model")
    prosthesis_serial: str = Field(..., description="Prosthesis serial number")
    customer_region: str = Field(..., description="Customer region")

    first_activity_date: date = Field(..., description="First recorded activity")
    last_activity_date: date = Field(..., description="Last recorded activity")
    total_days: int = Field(..., ge=0, description="Total days since first activity")
    active_days: int = Field(..., ge=0, description="Days with activity")

    total_movements: int = Field(..., ge=0, description="Total movements all time")
    total_successful: int = Field(..., ge=0, description="Total successful movements")
    overall_success_rate: float = Field(..., ge=0, le=100, description="Overall success rate %")
    avg_response_time: float = Field(..., ge=0, description="Average response time in ms")
    avg_battery_level: float = Field(..., ge=0, le=100, description="Average battery level %")
    total_errors: int = Field(..., ge=0, description="Total errors all time")
    avg_errors_per_day: float = Field(..., ge=0, description="Average errors per active day")


# ============================================================================
# API Response Models
# ============================================================================

class ReportsListResponse(BaseModel):
    """Response for GET /api/reports."""

    success: bool = True
    data: UserReportsList


class ReportDetailResponse(BaseModel):
    """Response for GET /api/reports/{date}."""

    success: bool = True
    data: DailyReport


class UserSummaryResponse(BaseModel):
    """Response for GET /api/reports/summary."""

    success: bool = True
    data: UserSummary


class ErrorResponse(BaseModel):
    """Error response model."""

    success: bool = False
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error info")


# ============================================================================
# CDN Response Models (Задание 3)
# ============================================================================

class CDNReportResponse(BaseModel):
    """Response with CDN URL for pre-generated report."""

    success: bool = True
    cdn_url: str = Field(..., description="CDN URL to fetch the report")
    cached: bool = Field(..., description="Whether report was already cached in S3")
    cache_ttl_seconds: int = Field(300, description="Cache TTL in seconds")
    expires_at: Optional[datetime] = Field(None, description="When cache expires")


class CDNReportsListResponse(BaseModel):
    """Response with CDN URL for reports list."""

    success: bool = True
    cdn_url: str = Field(..., description="CDN URL to fetch reports list")
    cached: bool = Field(..., description="Whether data was already cached")
    user_id: str = Field(..., description="User ID")


class CDNSummaryResponse(BaseModel):
    """Response with CDN URL for user summary."""

    success: bool = True
    cdn_url: str = Field(..., description="CDN URL to fetch summary")
    cached: bool = Field(..., description="Whether data was already cached")
    user_id: str = Field(..., description="User ID")


class CDNDailyReportResponse(BaseModel):
    """Response with CDN URL for daily report."""

    success: bool = True
    cdn_url: str = Field(..., description="CDN URL to fetch daily report")
    cached: bool = Field(..., description="Whether data was already cached")
    user_id: str = Field(..., description="User ID")
    report_date: date = Field(..., description="Report date")


class CacheInvalidationRequest(BaseModel):
    """Request to invalidate cache for users."""

    user_ids: List[str] = Field(..., description="List of user IDs to invalidate")
    invalidate_all: bool = Field(False, description="Invalidate all user data")


class CacheInvalidationResponse(BaseModel):
    """Response for cache invalidation."""

    success: bool = True
    invalidated_users: int = Field(..., description="Number of users invalidated")
    details: Optional[dict] = Field(None, description="Per-user invalidation details")


# ============================================================================
# Auth Models
# ============================================================================

class TokenPayload(BaseModel):
    """JWT token payload."""

    sub: str = Field(..., description="Subject (user ID)")
    exp: int = Field(..., description="Expiration timestamp")
    iat: Optional[int] = Field(None, description="Issued at timestamp")
    preferred_username: Optional[str] = Field(None, description="Username")
    email: Optional[str] = Field(None, description="User email")
    realm_access: Optional[dict] = Field(None, description="Realm roles")


class CurrentUser(BaseModel):
    """Current authenticated user."""

    user_id: str = Field(..., description="User ID (external_id)")
    username: Optional[str] = Field(None, description="Username")
    email: Optional[str] = Field(None, description="Email")
    roles: List[str] = Field(default_factory=list, description="User roles")
