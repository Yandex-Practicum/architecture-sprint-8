import os
from datetime import timedelta


class Config:
    """Application configuration"""

    def __init__(self):
        # Flask settings
        self.SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())

        # Session settings
        self.SESSION_COOKIE_NAME = 'bionicpro_session'
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
        self.SESSION_COOKIE_SAMESITE = 'Lax'
        self.SESSION_COOKIE_DOMAIN = None
        self.PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)

        # Keycloak settings (PKCE - no client_secret)
        self.KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://localhost:8080')
        self.KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'reports-realm')
        self.KEYCLOAK_CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID', 'reports-backend')

        # Frontend URL
        self.FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        self.BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5050')

        # Token settings
        self.ACCESS_TOKEN_LIFETIME = 120

        # ClickHouse (OLAP) settings
        self.CLICKHOUSE_HTTP_URL = os.getenv('CLICKHOUSE_HTTP_URL', 'http://localhost:8123')

        # S3 (Minio) settings
        self.S3_ENDPOINT_URL = os.getenv('S3_ENDPOINT_URL', 'http://localhost:9000')
        self.S3_ACCESS_KEY = os.getenv('S3_ACCESS_KEY', 'minio_user')
        self.S3_SECRET_KEY = os.getenv('S3_SECRET_KEY', 'minio_password')
        self.S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME', 'bionicpro-reports')

        # CDN (Nginx reverse proxy) settings
        self.CDN_BASE_URL = os.getenv('CDN_BASE_URL', 'http://localhost:8888')
