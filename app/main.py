from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="AI SaaS Starter Kit",
    version="0.1.0",
    description=(
        "Multi-tenant SaaS starter with auth, organization-scoped access, "
        "monthly AI usage metering, and quota enforcement."
    ),
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}
