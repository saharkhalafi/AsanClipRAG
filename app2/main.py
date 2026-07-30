# app2/main.py
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi.util import get_remote_address

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

# ======================
# Settings & Lifespan
# ======================
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app2.bootstrap import warm_application

    settings.setup()
    warm_application()
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
    allow_origins=settings.cors_origins,
    allow_credentials="*" not in settings.cors_origins,
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
