# app2/monitoring/metrics.py
from fastapi import APIRouter
import time

router = APIRouter(tags=["monitoring"])

@router.get("/metrics")
async def metrics():
    # بعداً Prometheus metrics واقعی اضافه می‌کنیم
    return {
        "uptime": time.time(),
        "status": "ok"
    }