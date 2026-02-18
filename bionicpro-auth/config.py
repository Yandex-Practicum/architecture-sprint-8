import os
from datetime import timedelta


class Config:
    """Конфигурация приложения"""
    
    def __init__(self):
        # Flask настройки
        self.SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(32).hex())
        
        # Session настройки
        self.SESSION_COOKIE_NAME = 'bionicpro_session'
        self.SESSION_COOKIE_HTTPONLY = True
        self.SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False') == 'True'
        self.SESSION_COOKIE_SAMESITE = 'Lax'
        self.PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
        
        # Keycloak настройки
        self.KEYCLOAK_URL = os.getenv('KEYCLOAK_URL', 'http://localhost:8080')
        self.KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM', 'reports-realm')
        self.KEYCLOAK_CLIENT_ID = os.getenv('KEYCLOAK_CLIENT_ID', 'reports-backend')
        self.KEYCLOAK_CLIENT_SECRET = os.getenv('KEYCLOAK_CLIENT_SECRET', 'your-client-secret')
        
        # Frontend URL
        self.FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        self.BACKEND_URL = os.getenv('BACKEND_URL', 'http://localhost:5050')
        
        # Token настройки
        self.ACCESS_TOKEN_LIFETIME = 120
