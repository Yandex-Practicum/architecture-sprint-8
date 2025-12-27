import os
from base64 import b64decode
from enum import StrEnum
from io import BytesIO
from random import randint
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security.utils import get_authorization_scheme_param
from jwt.algorithms import RSAAlgorithm
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel


KEYCLOAK_URL = os.getenv('KEYCLOAK_URL')
KEYCLOAK_REALM = os.getenv('KEYCLOAK_REALM')

pothetic_reports_db = {
    'prothetic1': [f'prothetic1 report row {i}' for i in range(randint(1, 10))],
    'prothetic2': [f'prothetic2 report row {i}' for i in range(randint(1, 10))],
    'prothetic3': [f'prothetic3 report row {i}' for i in range(randint(1, 10))],
}


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


async def public_key() -> RSAAlgorithm:
    async with httpx.AsyncClient() as client:
        response = await client.get(f'{KEYCLOAK_URL}/realms/{KEYCLOAK_REALM}/protocol/openid-connect/certs')
        response.raise_for_status()
        jwks = response.json()
        return RSAAlgorithm.from_jwk(jwks['keys'][0])


async def bearer_token(request: Request) -> str:
    authorization = request.headers.get('Authorization')
    scheme, param = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != 'bearer':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Not authenticated',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    return param


async def jwt_payload(token: Annotated[str, Depends(bearer_token)], public_key_: Annotated[RSAAlgorithm, Depends(public_key)]) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail='Could not validate credentials',
        headers={'WWW-Authenticate': 'Bearer'},
    )
    try:
        return jwt.decode(token, public_key_, algorithms=['RS256'])
    except InvalidTokenError:
        raise credentials_exception


class Roles(StrEnum):
    prothetic_user = 'prothetic_user'
    user = 'user'
    administrator = 'administrator'


class User(BaseModel):
    id: str
    username: str
    last_name: str
    first_name: str
    email: str
    roles: list[Roles | str]

    @classmethod
    def from_jwt_payload(cls, jwt_payload_: dict) -> 'User':
        return cls(
            id=jwt_payload_['sub'],
            username=jwt_payload_['preferred_username'],
            last_name=jwt_payload_['family_name'],
            first_name=jwt_payload_['given_name'],
            email=jwt_payload_['email'],
            roles=jwt_payload_['realm_access']['roles'],
        )


async def get_current_user(jwt_payload_: dict = Depends(jwt_payload)) -> User:
    return User.from_jwt_payload(jwt_payload_)


async def get_prothetic_user(current_user: User = Depends(get_current_user)) -> User:
    if Roles.prothetic_user not in current_user.roles:
        raise HTTPException(status_code=403, detail='Forbidden')
    return current_user


@app.get('/reports')
async def read_root(prothetic_user: User = Depends(get_prothetic_user)) -> StreamingResponse:
    if not (user_report := pothetic_reports_db.get(prothetic_user.username)):
        raise HTTPException(status_code=404, detail='Report not found')

    file_like = BytesIO(b'\n'.join([r.encode() for r in user_report]))
    return StreamingResponse(file_like, media_type='application/octet-stream', headers={'Content-Disposition': f'attachment; filename=report.txt'})
