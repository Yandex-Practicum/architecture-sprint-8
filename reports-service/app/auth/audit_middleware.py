"""
Audit middleware for logging access to reports endpoints.

Provides security audit trail for compliance and incident investigation.
"""

import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("audit")

# Configure audit logger with specific format
audit_handler = logging.StreamHandler()
audit_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s - AUDIT - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
)
logger.addHandler(audit_handler)
logger.setLevel(logging.INFO)


class AuditMiddleware(BaseHTTPMiddleware):
    """
    Middleware for auditing access to reports API.

    Logs:
    - Request ID for tracing
    - Client IP address
    - User ID (from JWT if available)
    - Requested endpoint and method
    - Response status code
    - Request duration
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]
        request.state.request_id = request_id

        # Record start time
        start_time = time.time()

        # Extract client IP
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        # Extract user ID from Authorization header (if present)
        user_id = "anonymous"
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            # Extract user_id from token without full validation (for logging only)
            try:
                import base64
                import json
                token = auth_header.split(" ")[1]
                # Decode payload (middle part of JWT)
                payload_b64 = token.split(".")[1]
                # Add padding if needed
                padding = 4 - len(payload_b64) % 4
                if padding != 4:
                    payload_b64 += "=" * padding
                payload = json.loads(base64.urlsafe_b64decode(payload_b64))
                user_id = payload.get("preferred_username") or payload.get("sub", "unknown")
            except Exception:
                user_id = "invalid_token"

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log audit entry for /api/reports endpoints
        if request.url.path.startswith("/api/reports"):
            log_message = (
                f"request_id={request_id} "
                f"user={user_id} "
                f"ip={client_ip} "
                f"method={request.method} "
                f"path={request.url.path} "
                f"status={response.status_code} "
                f"duration_ms={duration_ms:.2f}"
            )

            # Log level based on status code
            if response.status_code >= 500:
                logger.error(log_message)
            elif response.status_code >= 400:
                logger.warning(log_message)
            else:
                logger.info(log_message)

        # Add request ID to response headers for tracing
        response.headers["X-Request-ID"] = request_id

        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware for adding security headers to responses.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        return response
