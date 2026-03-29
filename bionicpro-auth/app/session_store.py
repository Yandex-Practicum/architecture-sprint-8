from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from threading import Lock

from .keycloak import TokenSet


UTC = timezone.utc


def utc_now() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True)
class PendingAuthorization:
    state: str
    code_verifier: str
    return_to: str
    expires_at: datetime


@dataclass(frozen=True)
class UserSession:
    session_id: str
    subject: str
    username: str
    email: str | None
    full_name: str | None
    roles: tuple[str, ...]
    identity_provider: str
    access_token: str
    encrypted_refresh_token: bytes
    access_token_expires_at: datetime
    refresh_token_expires_at: datetime
    session_expires_at: datetime
    created_at: datetime


class SessionStore:
    def __init__(self, encryption_key: str, session_ttl_seconds: int, auth_request_ttl_seconds: int) -> None:
        self._key = base64.urlsafe_b64decode(encryption_key.encode("utf-8"))
        self._session_ttl_seconds = session_ttl_seconds
        self._auth_request_ttl_seconds = auth_request_ttl_seconds
        self._pending_auth: dict[str, PendingAuthorization] = {}
        self._sessions: dict[str, UserSession] = {}
        self._lock = Lock()

    def create_pending_authorization(self, return_to: str, code_verifier: str) -> PendingAuthorization:
        state = secrets.token_urlsafe(32)
        pending = PendingAuthorization(
            state=state,
            code_verifier=code_verifier,
            return_to=return_to,
            expires_at=utc_now() + timedelta(seconds=self._auth_request_ttl_seconds),
        )
        with self._lock:
            self._purge_expired()
            self._pending_auth[state] = pending
        return pending

    def pop_pending_authorization(self, state: str) -> PendingAuthorization | None:
        with self._lock:
            pending = self._pending_auth.pop(state, None)
        if pending and pending.expires_at > utc_now():
            return pending
        return None

    def create_session(
        self,
        token_set: TokenSet,
        subject: str,
        username: str,
        email: str | None,
        full_name: str | None,
        roles: tuple[str, ...],
        identity_provider: str,
    ) -> UserSession:
        now = utc_now()
        session_expires_at = now + timedelta(seconds=self._session_ttl_seconds)
        session = UserSession(
            session_id=self._new_session_id(),
            subject=subject,
            username=username,
            email=email,
            full_name=full_name,
            roles=roles,
            identity_provider=identity_provider,
            access_token=token_set.access_token,
            encrypted_refresh_token=self._encrypt(token_set.refresh_token),
            access_token_expires_at=now + timedelta(seconds=token_set.expires_in),
            refresh_token_expires_at=self._refresh_token_deadline(
                now,
                token_set.refresh_expires_in,
                session_expires_at,
            ),
            session_expires_at=session_expires_at,
            created_at=now,
        )
        with self._lock:
            self._purge_expired()
            self._sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> UserSession | None:
        with self._lock:
            self._purge_expired()
            return self._sessions.get(session_id)

    def update_session_tokens(self, session_id: str, token_set: TokenSet) -> UserSession | None:
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                return None
            now = utc_now()
            updated = replace(
                session,
                access_token=token_set.access_token,
                encrypted_refresh_token=self._encrypt(token_set.refresh_token),
                access_token_expires_at=now + timedelta(seconds=token_set.expires_in),
                refresh_token_expires_at=self._refresh_token_deadline(
                    now,
                    token_set.refresh_expires_in,
                    session.session_expires_at,
                ),
            )
            self._sessions[session_id] = updated
            return updated

    def rotate_session(self, session_id: str) -> UserSession | None:
        with self._lock:
            session = self._sessions.pop(session_id, None)
            if session is None:
                return None
            rotated = replace(session, session_id=self._new_session_id())
            self._sessions[rotated.session_id] = rotated
            return rotated

    def delete_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def decrypt_refresh_token(self, session: UserSession) -> str:
        return self._decrypt(session.encrypted_refresh_token)

    def _new_session_id(self) -> str:
        return secrets.token_urlsafe(48)

    def _refresh_token_deadline(
        self,
        now: datetime,
        refresh_expires_in: int,
        session_expires_at: datetime,
    ) -> datetime:
        if refresh_expires_in <= 0:
            return session_expires_at
        return now + timedelta(seconds=refresh_expires_in)

    def _encrypt(self, value: str) -> bytes:
        plaintext = value.encode("utf-8")
        nonce = secrets.token_bytes(16)
        ciphertext = self._xor_with_stream(plaintext, nonce)
        signature = hmac.new(self._key, nonce + ciphertext, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(nonce + signature + ciphertext)

    def _decrypt(self, value: bytes) -> str:
        raw = base64.urlsafe_b64decode(value)
        nonce = raw[:16]
        signature = raw[16:48]
        ciphertext = raw[48:]
        expected = hmac.new(self._key, nonce + ciphertext, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Encrypted token integrity check failed.")
        return self._xor_with_stream(ciphertext, nonce).decode("utf-8")

    def _xor_with_stream(self, payload: bytes, nonce: bytes) -> bytes:
        stream = bytearray()
        counter = 0
        while len(stream) < len(payload):
            block = hashlib.sha256(self._key + nonce + counter.to_bytes(4, "big")).digest()
            stream.extend(block)
            counter += 1
        return bytes(left ^ right for left, right in zip(payload, stream))

    def _purge_expired(self) -> None:
        now = utc_now()
        self._pending_auth = {
            state: pending
            for state, pending in self._pending_auth.items()
            if pending.expires_at > now
        }
        self._sessions = {
            session_id: session
            for session_id, session in self._sessions.items()
            if session.session_expires_at > now and session.refresh_token_expires_at > now
        }
