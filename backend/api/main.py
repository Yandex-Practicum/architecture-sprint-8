import os
import tempfile
import traceback
from tempfile import NamedTemporaryFile
from typing import Any, List

import uvicorn
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2AuthorizationCodeBearer
from fpdf import FPDF
from keycloak import KeycloakOpenID
from psycopg2 import pool
from starlette.background import BackgroundTask
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse


class AppSettings():
    def __init__(self):
        self.keycloak_url = os.getenv('KEYCLOAK_URL', 'http://localhost:8080')
        self.realm = os.getenv('KEYCLOAK_REALM', 'reports-realm')
        self.frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:3000')
        self.token_url = "%s/auth/realms/%s/protocol/openid-connect/token" % (self.keycloak_url, self.realm)
        self.client_id = os.getenv('KEYCLOAK_CLIENT_ID', 'reports-api')
        self.client_secret = os.getenv('KEYCLOAK_CLIENT_SECRET', 'oNwoLQdvJAvRcL89SydqCWCe5ry1jMgq')
        self.db_connection = os.getenv("DB_CONNECTION")
        if not self.db_connection > "":
            raise "DB connection (DB_CONNECTION) is required"


settings = AppSettings()

keycloak_openid = KeycloakOpenID(
    server_url=settings.keycloak_url,
    client_id=settings.client_id,
    realm_name=settings.realm,
    client_secret_key=settings.client_secret,  # your backend client secret
    verify=True
)

db_pool = pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=20,
    dsn=settings.db_connection
)

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl=keycloak_openid.auth_url(settings.frontend_url),
    tokenUrl=settings.token_url,
)


class User():

    def __init__(self, username, **attrs):
        self.username = username
        self.name = attrs.get("name", "Undefined")
        self.given_name = attrs.get("given_name", "Undefined")
        self.family_name = attrs.get("family_name", "Undefined")
        self.email = attrs.get("email", "Undefined")


app = FastAPI(
    title="Bionic Report API",
    description="Приложение для скачивания отчетов о протезам Bionic PRO",
    version="0.0.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health",
         description="Возвращает информацию о состоянии системы")
def health_check():
    return {"status": "healthy"}


@app.get("/reports",
         description="Получить отчет текущего пользователя")
def get_report(token: str = Depends(oauth2_scheme)):
    try:
        payload = keycloak_openid.decode_token(
            token
        )
        username = payload.get("preferred_username")
        if not username:
            raise HTTPException(
                status_code=401,
                detail="Invalid token"
            )
        user = User(username, **payload)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
    data = fetch_report_data(username)
    pdf = draw_report(user, data)
    fd = NamedTemporaryFile(delete=False, prefix="report", suffix=username)
    fd.close()
    pdf.output(fd.name)
    return FileResponse(path=fd.name,
                        filename="report %s %s.pdf" % (user.given_name, user.family_name),
                        media_type='multipart/form-data')


def draw_report(user: User, data: List[Any]) -> FPDF:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font('helvetica', size=12)
    pdf.cell(w=200, h=10, txt=("Daily report for %s" % user.name))
    pdf.ln()
    pdf.ln()
    pdf.ln()
    with pdf.table() as table:
        pdf.set_font('helvetica', style="B", size=10)
        header = table.row()
        header.cell("Day", border=1)
        header.cell("Prothesis", border=1)
        header.cell("Person", border=1)
        header.cell("Gender", border=1)
        header.cell("Age", border=1)
        header.cell("Profession", border=1)
        header.cell("Battery Level (avg)", border=1)
        header.cell("Tension (avg)", border=1)
        header.cell("Impedance (avg)", border=1)
        pdf.set_font('helvetica', size=8)
        for item in data:
            row = table.row()
            for value in item:
                row.cell(str(value), border=1, align="L")
    return pdf


def fetch_report_data(username):
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            query = "SELECT " \
                   " day, device_name, first_name || ' ' || last_name, gender, age, profession, avg_battery_level, avg_tension, avg_impedance " \
                   " FROM user_daily_report WHERE username = %s" \
                   " ORDER BY day DESC"
            params = (username,)
            cur.execute(query, params)
            return cur.fetchall()
    finally:
        db_pool.putconn(conn)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
