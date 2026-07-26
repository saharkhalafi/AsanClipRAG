# app2/main.py
import logging
from contextlib import asynccontextmanager

# ======================
# Sentry
# ======================
import sentry_sdk
from app2.api.routes import router as search_router

# ======================
# App imports
# ======================
from app2.core.settings import get_settings

# Exceptions
from app2.exceptions.handlers import (
    general_exception_handler,
)
from app2.middleware.logging import LoggingMiddleware

# Middleware
from app2.middleware.request_id import RequestIDMiddleware
from app2.middleware.timing import TimingMiddleware

# Health
from app2.monitoring.health import router as health_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from slowapi import Limiter
from slowapi.util import get_remote_address

# ======================
# Settings & Lifespan
# ======================
settings = get_settings()


# ======================
# Sentry Init
# ======================
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=0.2,          # 20% of requests for performance monitoring
        profiles_sample_rate=0.1,
        environment=settings.ENVIRONMENT,
        send_default_pii=False,          # Don't send sensitive user data
    )
    logging.info("✅ Sentry initialized")
else:
    logging.info("ℹ️ Sentry DSN not set — skipping Sentry")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("🚀 AsanClip RAG System started successfully")
    yield
    logging.info("🛑 AsanClip RAG System shutting down")


# ======================
# App
# ======================
app = FastAPI(
    title="AsanClip RAG System",
    version="1.0.0",
    description="Production RAG Search Engine for Video Templates",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ======================
# Rate Limiter
# ======================
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter

# ======================
# Middleware
# ======================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # در پروداکشن محدود کن
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TimingMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# ======================
# Exception Handlers
# ======================
app.add_exception_handler(Exception, general_exception_handler)

# ======================
# Routes
# ======================
app.include_router(search_router, prefix="/api/v1")
app.include_router(health_router, prefix="/api/v1")

# ======================
# Root
# ======================
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "AsanClip RAG API is running 🚀",
        "version": "1.0.0",
        "docs": "/docs"
    }
# ======================
# Run
# ======================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app2.main:app", host="0.0.0.0", port=8000, reload=True)
