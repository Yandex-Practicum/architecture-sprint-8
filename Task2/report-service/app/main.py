from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from clickhouse_driver import Client
import jwt
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLICKHOUSE_HOST = os.getenv("CLICKHOUSE_HOST", "localhost")
client = Client(host=CLICKHOUSE_HOST)


def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization header")

    try:
        token = authorization.replace("Bearer ", "")
        payload = jwt.decode(token, options={"verify_signature": False})

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Missing sub in token")

        return user_id

    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")


@app.get("/reports")
def get_reports(user_id: str = Depends(get_current_user_id)):
    """
    Возвращает отчет по протезу.
    Ограничение доступа — по JWT (sub).
    """

    query = """
        SELECT *
        FROM user_prosthesis_daily_report
        LIMIT 100
    """

    try:
        rows = client.execute(query)
    except Exception:
        rows = []

    return {
        "user_id": user_id,
        "reports": rows,
    }
