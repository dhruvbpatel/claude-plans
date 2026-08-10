"""Activist Pixel Sim — FastAPI entrypoint."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.sessions import router as sessions_router

load_dotenv()

app = FastAPI(title="Activist Pixel Sim", version="0.1.0")

_origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "debate_provider": os.getenv("DEBATE_PROVIDER", "deterministic"),
    }
