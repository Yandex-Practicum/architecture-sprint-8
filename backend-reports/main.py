import os
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
import clickhouse_connect
import jwt

app = FastAPI()

#CORS для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

#проверка токена (из realm-export)
KEYCLOAK_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAsS4tyYnjwxujBa/cMcsY+20QcSTg+QQSVrTUWkJ9NzOcUKcEO32kHM0Miq1labXUDioC+d/uMXH0MjNqsTursgNWP8l1p8IDchT2j8Kcef5jLqp/wEqdFIDb3WK8+nNlQv7B9/ASVFlklQcBzP/LyT9yAZQdthpwclgTXhvWaTjeRD9vYFq583ziFUVl/t0kyqWihsO0q2/e3nFPGrMHZ8pIkvl/hCXM/WbPy8tJgx8qhv8GvP/vlWIm6oZ5doVjcIl7m9d+mEa7X4ZGC1Ug5ORTZB/bDDewexYduX5fUdnMPDuJS3pvwgz9JscBLJW0bI7H3xhBOrjyg9ZC+wEMiwIDAQAB-----END PUBLIC KEY-----"""
ALGORITHMS = ["RS256"]

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Декодирует JWT и возвращает user_id (sub). (для задачи 4)"""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        user_id = payload.get("preferred_username")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token: 'sub' claim missing")
        return user_id
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=f"Could not validate credentials: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"error token validation:{e}")

@app.get("/reports")
async def get_report(user_id: str = Depends(verify_token)):
    """Получает отчет из ClickHouse только для текущего пользователя. (для задачи 3 и 4)"""

    try:
        #подключение к ClickHouse
        client = clickhouse_connect.get_client(
            host='clickhouse',
            port=8123,
            username='default',
            password='password123'
        )

        #запрос к витрине,задача 3
        query = f"SELECT * FROM prothetic_reports WHERE user_id = '{user_id}' LIMIT 1"
        result = client.query(query)
        if not result.result_rows:
            #если Airflow еще не обработал данные
            raise HTTPException(
                status_code=404,
                detail="Сообщите, что данные для этого пользователя еще не обработаны"
            )
        #читабельность
        report_row = result.result_rows[0]
        columns = result.column_names
        report_dict = dict(zip(columns, report_row))

        return report_dict
    except Exception as e:
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)