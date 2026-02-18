import secrets
from typing import Dict, Optional
from datetime import datetime
from cryptography.fernet import Fernet


class SessionStore:
    """
    Хранилище сессий и токенов
    В production использовать Redis
    """
    
    def __init__(self, encryption_key: Optional[str] = None):
        # Для шифрования refresh_token
        if encryption_key:
            self.cipher = Fernet(encryption_key.encode())
        else:
            # Генерируем ключ (в production передавать через env)
            self.cipher = Fernet(Fernet.generate_key())
        
        # Хранилище: session_id -> token_data
        self._store: Dict[str, Dict] = {}
    
    def create_session(self, access_token: str, refresh_token: str) -> str:
        """Создать новую сессию и сохранить токены"""
        session_id = secrets.token_urlsafe(32)
        
        # Шифруем refresh_token для безопасности
        encrypted_refresh = self.cipher.encrypt(refresh_token.encode()).decode()
        
        self._store[session_id] = {
            'access_token': access_token,  # В памяти (или Redis)
            'refresh_token_encrypted': encrypted_refresh,  # Зашифрованный
            'created_at': datetime.utcnow().isoformat()
        }
        
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Получить данные сессии"""
        return self._store.get(session_id)
    
    def update_session_tokens(self, session_id: str, access_token: str, 
                             refresh_token: Optional[str] = None):
        """Обновить токены в существующей сессии"""
        if session_id in self._store:
            self._store[session_id]['access_token'] = access_token
            
            if refresh_token:
                encrypted_refresh = self.cipher.encrypt(refresh_token.encode()).decode()
                self._store[session_id]['refresh_token_encrypted'] = encrypted_refresh
    
    def rotate_session(self, old_session_id: str) -> str:
        """
        Ротация сессии для защиты от session fixation attack
        Создает новый session_id с теми же токенами
        """
        old_data = self._store.get(old_session_id)
        if not old_data:
            raise ValueError("Session not found")
        
        # Создаем новый session_id
        new_session_id = secrets.token_urlsafe(32)
        
        # Копируем данные
        self._store[new_session_id] = old_data.copy()
        
        # Удаляем старую сессию
        del self._store[old_session_id]
        
        return new_session_id
    
    def delete_session(self, session_id: str):
        """Удалить сессию (logout)"""
        if session_id in self._store:
            del self._store[session_id]
    
    def get_decrypted_refresh_token(self, session_id: str) -> Optional[str]:
        """Получить расшифрованный refresh_token"""
        session_data = self._store.get(session_id)
        if not session_data:
            return None
        
        encrypted = session_data.get('refresh_token_encrypted')
        if not encrypted:
            return None
        
        try:
            return self.cipher.decrypt(encrypted.encode()).decode()
        except:
            return None
