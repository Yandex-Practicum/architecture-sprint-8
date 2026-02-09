from fastapi import FastAPI

app = FastAPI(title="bionicpro-auth")

@app.get("/health")
def health():
    return {"status": "ok"}
