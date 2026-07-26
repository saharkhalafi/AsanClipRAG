# app2/monitoring/metrics.py
import time

from fastapi import APIRouter

router = APIRouter(tags=["monitoring"])

@router.get("/metrics")
async def metrics():
    # بعداً Prometheus metrics واقعی اضافه می‌کنیم
    return {
        "uptime": time.time(),
        "status": "ok"
    }
