from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from . import models, services
from .database import Base, engine, get_db
from .schemas import (
    BookingCreate,
    BuildingCreate,
    FloorCreate,
    VenueCreate,
    VenueUpdate,
)
from .redis_client import client as redis_client

Base.metadata.create_all(bind=engine)

app = FastAPI(title="汇堂 · 场地档期平台", version="1.0.0")


@app.exception_handler(services.BizError)
async def biz_error_handler(request: Request, exc: services.BizError):
    # 统一错误信封，前端直接展示 message
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                **exc.extra,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # 参数校验错误也走统一信封，前端能直接展示中文可读信息
    parts = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", []) if x != "body")
        msg = err.get("msg", "")
        parts.append(f"{loc}：{msg}" if loc else msg)
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "提交数据有误：" + "；".join(parts)}},
    )


@app.get("/api/health")
def health():
    try:
        redis_ok = bool(redis_client.ping())
    except Exception as e:  # noqa: BLE001
        return {"api": "ok", "redis": False, "redis_error": str(e)}
    return {"api": "ok", "redis": redis_ok}


# ---------------- 楼栋 / 楼层 ----------------
@app.get("/api/buildings")
def api_list_buildings(db: Session = Depends(get_db)):
    return services.list_buildings(db)


@app.post("/api/buildings", status_code=201)
def api_create_building(payload: BuildingCreate, db: Session = Depends(get_db)):
    return services.create_building(db, payload.name, payload.code)


@app.post("/api/buildings/{building_id}/floors", status_code=201)
def api_create_floor(building_id: int, payload: FloorCreate, db: Session = Depends(get_db)):
    return services.create_floor(db, building_id, payload.level, payload.name)


# ---------------- 场地 ----------------
@app.get("/api/buildings/{building_id}/venues")
def api_list_venues(building_id: int, db: Session = Depends(get_db)):
    return services.list_venues(db, building_id)


@app.post("/api/buildings/{building_id}/venues", status_code=201)
def api_create_venue(building_id: int, payload: VenueCreate, db: Session = Depends(get_db)):
    if payload.building_id != building_id:
        raise services.BizError(
            "cross_building_denied",
            "请求体中的楼栋与路径楼栋不一致，场地必须挂在所选楼栋的楼层下。",
            400,
        )
    return services.create_venue(db, payload.model_dump())


@app.patch("/api/venues/{venue_id}")
def api_update_venue(venue_id: int, payload: VenueUpdate, db: Session = Depends(get_db)):
    data = {k: v for k, v in payload.model_dump().items() if v is not None}
    return services.update_venue(db, venue_id, data)


@app.delete("/api/venues/{venue_id}", status_code=204)
def api_delete_venue(venue_id: int, db: Session = Depends(get_db)):
    services.delete_venue(db, venue_id)


# ---------------- 档期 ----------------
@app.get("/api/buildings/{building_id}/venues/{venue_id}/schedule")
def api_get_schedule(
    building_id: int,
    venue_id: int,
    view: str = "day",           # day | week
    date: str = None,            # YYYY-MM-DD，默认当天（默认值放到函数内，避免进程启动时刻固化）
    db: Session = Depends(get_db),
):
    from datetime import date as _date

    date_str = date or _date.today().isoformat()
    return services.get_schedule(db, venue_id, building_id, view, date_str)


@app.post("/api/bookings", status_code=201)
def api_create_booking(payload: BookingCreate, db: Session = Depends(get_db)):
    return services.create_booking(db, payload.model_dump())


@app.post("/api/buildings/{building_id}/bookings/{booking_id}/cancel")
def api_cancel_booking(building_id: int, booking_id: int, db: Session = Depends(get_db)):
    services.cancel_booking(db, booking_id, building_id)
    return {"ok": True}
