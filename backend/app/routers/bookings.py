from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import services
from ..database import get_db
from ..schemas import BookingCreate, BookingOut

router = APIRouter(prefix="/api/buildings/{building_id}", tags=["bookings"])


@router.get("/schedule")
def get_schedule(
    building_id: int,
    view: str = Query("day", pattern="^(day|week)$"),
    day: date = Query(..., description="基准日期，周视图取其所在自然周（周一到周日）"),
    venue_id: int | None = None,
    floor_id: int | None = None,
    db: Session = Depends(get_db),
):
    """日/周档期视图。

    返回完整档期对象（跨天不拆段），并带 touched_dates / starts_before_range /
    ends_after_range 供前端跨天连续渲染。
    """
    return services.get_schedule(db, building_id, view, day, venue_id, floor_id)


@router.post("/venues/{venue_id}/bookings", response_model=BookingOut, status_code=201)
def create_booking(
    building_id: int, venue_id: int, data: BookingCreate,
    db: Session = Depends(get_db),
):
    return services.create_booking(db, building_id, venue_id, data)


@router.post("/bookings/{booking_id}/cancel", status_code=204)
def cancel_booking(building_id: int, booking_id: int, db: Session = Depends(get_db)):
    services.cancel_booking(db, building_id, booking_id)
