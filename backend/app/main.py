import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, data_sources, glossary, query

app = FastAPI(title="DataGenie API", version="0.1.0")

_raw = os.environ.get("ALLOWED_ORIGINS", "*")
allowed_origins = [o.strip() for o in _raw.split(",")] if _raw != "*" else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api")
app.include_router(data_sources.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(glossary.router, prefix="/api")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
