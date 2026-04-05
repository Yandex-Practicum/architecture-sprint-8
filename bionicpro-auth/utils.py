import base64
import hashlib
import secrets
from dataclasses import dataclass


def random_urlsafe_token() -> str:
    return secrets.token_urlsafe(32)


class Pkce:
    @staticmethod
    def generate_verifier() -> str:
        return random_urlsafe_token()

    @staticmethod
    def code_challenge_s256(verifier: str) -> str:
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


@dataclass(frozen=True)
class SessionContext:
    access_token: str
