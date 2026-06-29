"""Gateway application entrypoint.

On startup we create database tables and start the SDK's background log shipper;
on shutdown we flush/close the shipper and the HTTP client cleanly.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db import init_models
from .routers import chat
from .sdk_client import get_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_models()
    client = get_client()
    client.start()  # begin shipping inference logs in the background
    try:
        yield
    finally:
        await client.aclose()


app = FastAPI(title="Infera Gateway", lifespan=lifespan)

# Allow the local web app (Next.js dev server) to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router)


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
