# app2/middleware/logging.py
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("app2.request")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time = (time.perf_counter() - start_time) * 1000
        status_code = response.status_code

        logger.info(
            f"{request.method} {request.url.path} "
            f"[{status_code}] {process_time:.2f}ms "
            f"IP={request.client.host if request.client else 'unknown'}"
        )

        return response
