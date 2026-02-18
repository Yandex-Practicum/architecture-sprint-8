import requests
import jwt
from typing import Dict, Optional
from datetime import datetime, timedelta


class KeycloakService:
    """Сервис для работы с Keycloak"""
    
    def __init__(self, config):
        # Используем словарный доступ к конфигурации Flask
        self.keycloak_url = config.KEYCLOAK_URL
        self.realm = config.KEYCLOAK_REALM
        self.client_id = config.KEYCLOAK_CLIENT_ID
        self.backend_url = config.BACKEND_URL
    
    def get_token_endpoint(self) -> str:
        """Получить URL для обмена токенов"""
        return f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/token"
    
    def exchange_code_for_tokens(self, code: str, code_verifier: str) -> Dict:
        """
        Обмен authorization code на access и refresh токены
        Поддержка PKCE через code_verifier
        """
        try:
            response = requests.post(
                self.get_token_endpoint(),
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'client_id': self.client_id,
                    'redirect_uri': f'{self.backend_url}/auth/callback',
                    'code_verifier': code_verifier  # PKCE
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to exchange code for tokens: {str(e)}")
    
    def refresh_access_token(self, refresh_token: str) -> Dict:
        """Обновить access token используя refresh token"""
        try:
            response = requests.post(
                self.get_token_endpoint(),
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': self.client_id
                },
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to refresh token: {str(e)}")
    
    def decode_token(self, token: str, verify: bool = False) -> Dict:
        """Декодировать JWT токен (без верификации для простоты)"""
        try:
            # Для production нужна верификация с публичным ключом Keycloak
            return jwt.decode(token, options={"verify_signature": verify})
        except jwt.InvalidTokenError as e:
            raise Exception(f"Invalid token: {str(e)}")
    
    def is_token_expired(self, token: str) -> bool:
        """Проверить, истек ли токен"""
        try:
            decoded = self.decode_token(token)
            exp_timestamp = decoded.get('exp', 0)
            # Добавляем буфер 10 секунд
            return datetime.utcnow().timestamp() >= (exp_timestamp - 10)
        except:
            return True
    
    def get_user_info(self, access_token: str) -> Optional[Dict]:
        """Получить информацию о пользователе из Keycloak"""
        try:
            response = requests.get(
                f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/userinfo",
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException:
            return None
