import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .database import wait_for_database
from .redis_client import kv
from .routers import bookings, buildings, venues
from .seed import init_and_seed
from .services import ApiError

logger = logging.getLogger("huitang")

app = FastAPI(title="汇堂 · 场地档期平台", version="1.0.0")


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    """业务错误统一结构：code 给程序判断，message 直接讲人话、说清原因。"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                **({"details": exc.extra} if exc.extra else {}),
            }
        },
    )


@app.on_event("startup")
def on_startup():
    wait_for_database()
    try:
        kv.ping()
    except Exception:  # pragma: no cover
        logger.warning("Redis 连接失败，请检查 REDIS_URL；锁与缓存将不可用")
    if settings.SEED_ON_START:
        result = init_and_seed()
        logger.info("种子数据: %s", result)


@app.get("/api/health")
def health():
    redis_ok = True
    try:
        kv.ping()
    except Exception:
        redis_ok = False
    return {"status": "ok", "service": "huitang", "redis": redis_ok}


app.include_router(buildings.router)
app.include_router(venues.router)
app.include_router(bookings.router)
