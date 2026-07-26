# app2/exceptions/handlers.py
import logging

from app2.exceptions.errors import AppBaseError
from fastapi import Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger("app2.exceptions")


async def app_exception_handler(request: Request, exc: AppBaseError):
    """Handle custom application errors"""
    logger.error(f"App error [{exc.status_code}]: {exc.message}", exc_info=True)

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": exc.message,
            "request_id": getattr(request.state, "request_id", None)
        }
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.exception("Unhandled exception occurred")

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "status": "error",
            "message": "مشکلی پیش آمده است. لطفاً دوباره تلاش کنید.",
            "request_id": getattr(request.state, "request_id", None)
        }
    )
