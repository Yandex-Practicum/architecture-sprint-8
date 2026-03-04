from fastapi import FastAPI
import uvicorn
from app.routes import auth
from app.config import settings
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="BionicPRO Auth Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth.router)


@app.get("/health")
async def health():
    return {"status": "ok"}


def main():
    print("Hello from bionicpro-auth!")
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
