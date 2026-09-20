"""核心业务规则：场地删除保护、档期冲突检测（含跨天）、楼栋越权拦截。"""
import json
from datetime import datetime, time, timedelta
from typing import List, Optional, Tuple

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .config import settings
from .models import BOOKING_STATUS, Booking, Building, Floor, Venue
from .redis_client import kv


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str, extra: dict = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.extra = extra or {}
        super().__init__(message)


# ---------------- 楼栋 / 楼层 ----------------

def get_building_or_404(db: Session, building_id: int) -> Building:
    """所有档期操作都以楼栋为范围。楼栋不存在（或无权访问）时明确报错，
    而不是返回空列表把用户引向一个空白页。"""
    b = db.get(Building, building_id)
    if b is None:
        raise ApiError(
            404,
            "building_not_found",
            f"楼栋不存在或您无权访问（building_id={building_id}），"
            "请从左侧楼栋列表重新选择，不要直接访问陌生楼栋的档期。",
        )
    return b


def get_floor(db: Session, floor_id: int, building: Building) -> Floor:
    floor = db.get(Floor, floor_id)
    if floor is None or floor.building_id != building.id:
        raise ApiError(
            400,
            "floor_mismatch",
            f"楼层不属于楼栋「{building.name}」，不能跨楼栋挂靠场地。",
        )
    return floor


# ---------------- 场地 ----------------

def _venue_to_dict(v: Venue) -> dict:
    return {
        "id": v.id,
        "floor_id": v.floor_id,
        "building_id": v.floor.building_id,
        "name": v.name,
        "door_plate": v.door_plate,
        "capacity": v.capacity,
        "venue_type": v.venue_type,
        "equipment": list(v.equipment or []),
        "status": v.status,
        "floor_name": v.floor.name,
        "building_name": v.floor.building.name,
    }


def list_venues(
    db: Session,
    building_id: int,
    floor_id: Optional[int] = None,
    status: Optional[str] = None,
    q: Optional[str] = None,
) -> List[dict]:
    building = get_building_or_404(db, building_id)
    query = (
        db.query(Venue)
        .join(Floor, Venue.floor_id == Floor.id)
        .filter(Floor.building_id == building.id)
    )
    if floor_id is not None:
        query = query.filter(Venue.floor_id == floor_id)
    if status:
        query = query.filter(Venue.status == status)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Venue.name.like(like), Venue.door_plate.like(like))
        )
    query = query.order_by(Floor.level, Venue.door_plate, Venue.id)
    return [_venue_to_dict(v) for v in query.all()]


def create_venue(db: Session, building_id: int, data) -> dict:
    building = get_building_or_404(db, building_id)
    get_floor(db, data.floor_id, building)
    # 同楼层门牌号唯一
    exists = (
        db.query(Venue.id)
        .filter(Venue.floor_id == data.floor_id, Venue.door_plate == data.door_plate)
        .first()
    )
    if exists:
        raise ApiError(
            409,
            "door_plate_exists",
            f"该楼层已存在门牌 {data.door_plate} 的场地。",
        )
    v = Venue(
        floor_id=data.floor_id,
        name=data.name,
        door_plate=data.door_plate,
        capacity=data.capacity,
        venue_type=data.venue_type,
        equipment=data.equipment,
        status=data.status,
    )
    db.add(v)
    db.commit()
    db.refresh(v)
    invalidate_schedule_cache(building_id)
    return _venue_to_dict(v)


def _get_scoped_venue(db: Session, building_id: int, venue_id: int) -> Tuple[Venue, Building]:
    building = get_building_or_404(db, building_id)
    v = db.get(Venue, venue_id)
    if v is None:
        raise ApiError(404, "venue_not_found", f"场地不存在（venue_id={venue_id}）。")
    if v.floor.building_id != building.id:
        raise ApiError(
            403,
            "cross_building_denied",
            f"场地「{v.name}」挂在别的楼栋（{v.floor.building.name}）下，"
            f"不能在楼栋「{building.name}」里查看或修改，请到它所属的楼栋操作。",
        )
    return v, building


def update_venue(db: Session, building_id: int, venue_id: int, data) -> dict:
    v, building = _get_scoped_venue(db, building_id, venue_id)
    payload = data.model_dump(exclude_unset=True)
    if "floor_id" in payload and payload["floor_id"] != v.floor_id:
        get_floor(db, payload["floor_id"], building)
        dup = (
            db.query(Venue.id)
            .filter(
                Venue.floor_id == payload["floor_id"],
                Venue.door_plate == payload.get("door_plate", v.door_plate),
                Venue.id != v.id,
            )
            .first()
        )
        if dup:
            raise ApiError(409, "door_plate_exists", "目标楼层已存在相同门牌号。")
    for key, value in payload.items():
        setattr(v, key, value)
    db.commit()
    db.refresh(v)
    invalidate_schedule_cache(building_id)
    return _venue_to_dict(v)


def delete_venue(db: Session, building_id: int, venue_id: int) -> None:
    v, building = _get_scoped_venue(db, building_id, venue_id)
    # 删除保护：名下还有未来档期则拦下
    now = datetime.now()
    future = (
        db.query(Booking)
        .filter(
            Booking.venue_id == v.id,
            Booking.cancelled.is_(False),
            Booking.end_at > now,
        )
        .order_by(Booking.start_at)
        .all()
    )
    if future:
        earliest = future[0]
        raise ApiError(
            409,
            "venue_has_future_bookings",
            f"场地「{v.name}」名下还有 {len(future)} 条未结束的档期，"
            f"最早一条为「{earliest.title}」"
            f"（{earliest.start_at:%Y-%m-%d %H:%M} ~ {earliest.end_at:%Y-%m-%d %H:%M}），"
            "请先取消或改期这些档期后再删除场地。",
            extra={
                "count": len(future),
                "earliest": {
                    "id": earliest.id,
                    "title": earliest.title,
                    "booker": earliest.booker,
                    "start_at": earliest.start_at.isoformat(timespec="minutes"),
                    "end_at": earliest.end_at.isoformat(timespec="minutes"),
                },
            },
        )
    db.delete(v)
    db.commit()
    invalidate_schedule_cache(building_id)


# ---------------- 档期 ----------------

def _touch_dates(start_at: datetime, end_at: datetime) -> List[str]:
    """档期覆盖到的每一个自然日（跨天档期会出现多天）。"""
    days = []
    cur = start_at.date()
    last = (end_at - timedelta(minutes=1)).date()  # 恰好在 00:00 结束不算新一天
    while cur <= last:
        days.append(cur.isoformat())
        cur += timedelta(days=1)
    return days


def _booking_to_dict(b: Booking, range_start: datetime, range_end: datetime) -> dict:
    return {
        "id": b.id,
        "venue_id": b.venue_id,
        "venue_name": b.venue.name,
        "title": b.title,
        "booker": b.booker,
        "start_at": b.start_at.isoformat(timespec="minutes"),
        "end_at": b.end_at.isoformat(timespec="minutes"),
        "remark": b.remark or "",
        "status": b.status,
        "cancelled": b.cancelled,
        # 跨天渲染所需信息
        "touched_dates": _touch_dates(b.start_at, b.end_at),
        "starts_before_range": b.start_at < range_start,
        "ends_after_range": b.end_at > range_end,
    }


def day_range(day: datetime.date) -> Tuple[datetime, datetime, List[str]]:
    start = datetime.combine(day, time.min)
    end = start + timedelta(days=1)
    return start, end, [day.isoformat()]


def week_range(day: datetime.date) -> Tuple[datetime, datetime, List[str]]:
    monday = day - timedelta(days=day.weekday())
    start = datetime.combine(monday, time.min)
    days = [(monday + timedelta(days=i)).isoformat() for i in range(7)]
    return start, start + timedelta(days=7), days


def schedule_cache_key(building_id: int, view: str, day: str, venue_id, floor_id) -> str:
    return f"schedule:{building_id}:{view}:{day}:{venue_id or 'all'}:{floor_id or 'all'}"


def invalidate_schedule_cache(building_id: int) -> None:
    kv.invalidate_pattern(f"schedule:{building_id}:*")


def get_schedule(
    db: Session,
    building_id: int,
    view: str,
    day: datetime.date,
    venue_id: Optional[int] = None,
    floor_id: Optional[int] = None,
) -> dict:
    building = get_building_or_404(db, building_id)  # 陌生楼栋：明确报错，杜绝空白页

    if view == "day":
        range_start, range_end, days = day_range(day)
    elif view == "week":
        range_start, range_end, days = week_range(day)
    else:
        raise ApiError(400, "bad_view", "view 只支持 day 或 week。")

    cache_key = schedule_cache_key(
        building_id, view, day.isoformat(), venue_id, floor_id
    )
    cached = kv.cache_get(cache_key)
    if cached:
        payload = json.loads(cached)
        payload["cached"] = True
        return payload

    venue_query = (
        db.query(Venue)
        .join(Floor, Venue.floor_id == Floor.id)
        .filter(Floor.building_id == building.id)
    )
    if floor_id is not None:
        fl = db.get(Floor, floor_id)
        if fl is None or fl.building_id != building.id:
            raise ApiError(
                400, "floor_mismatch", "筛选的楼层不属于当前楼栋。"
            )
        venue_query = venue_query.filter(Venue.floor_id == floor_id)
    if venue_id is not None:
        target = db.get(Venue, venue_id)
        if target is None:
            raise ApiError(404, "venue_not_found", "场地不存在。")
        if target.floor.building_id != building.id:
            raise ApiError(
                403,
                "cross_building_denied",
                f"场地「{target.name}」属于别的楼栋（{target.floor.building.name}），"
                f"不能在楼栋「{building.name}」的档期表中查看，"
                "请切换到它所属的楼栋，避免拿到空白页。",
            )
        venue_query = venue_query.filter(Venue.id == venue_id)

    venues = venue_query.order_by(Floor.level, Venue.door_plate).all()
    venue_ids = [v.id for v in venues]

    bookings = []
    if venue_ids:
        rows = (
            db.query(Booking)
            .filter(
                Booking.venue_id.in_(venue_ids),
                Booking.cancelled.is_(False),
                # 半开区间重叠：跨天档期只要有任何一刻落在窗口内就返回，
                # 日视图/周视图都拿完整记录，绝不切成两截
                Booking.start_at < range_end,
                Booking.end_at > range_start,
            )
            .order_by(Booking.start_at, Booking.id)
            .all()
        )
        bookings = [_booking_to_dict(b, range_start, range_end) for b in rows]

    floors = (
        db.query(Floor)
        .filter(Floor.building_id == building.id)
        .order_by(Floor.level)
        .all()
    )
    payload = {
        "view": view,
        "building": {"id": building.id, "name": building.name},
        "range_start": range_start.isoformat(timespec="minutes"),
        "range_end": range_end.isoformat(timespec="minutes"),
        "days": days,
        "floors": [
            {"id": f.id, "level": f.level, "name": f.name} for f in floors
        ],
        "venues": [_venue_to_dict(v) for v in venues],
        "bookings": bookings,
        "cached": False,
    }
    kv.cache_set(cache_key, json.dumps(payload, ensure_ascii=False),
                 settings.SCHEDULE_CACHE_TTL)
    return payload


def create_booking(db: Session, building_id: int, venue_id: int, data) -> dict:
    building = get_building_or_404(db, building_id)
    venue = db.get(Venue, venue_id)
    if venue is None:
        raise ApiError(404, "venue_not_found", f"场地不存在（venue_id={venue_id}）。")
    if venue.floor.building_id != building.id:
        raise ApiError(
            403,
            "cross_building_denied",
            f"场地「{venue.name}」属于楼栋「{venue.floor.building.name}」，"
            f"不能登记到楼栋「{building.name}」的档期里，请到它所属的楼栋下单。",
        )
    if venue.status != "可订":
        reason = "正在装修" if venue.status == "装修中" else "已停用"
        raise ApiError(
            409,
            "venue_unavailable",
            f"场地「{venue.name}」{reason}，暂不可预订档期。",
        )
    if data.end_at <= data.start_at:
        raise ApiError(400, "bad_time_range", "结束时间必须晚于开始时间。")

    # Redis 分布式锁：同一场地的“查重 + 写入”串行化，防并发双占
    try:
        with kv.venue_lock(venue_id):
            return _insert_booking(db, building_id, venue, data)
    except TimeoutError as exc:
        raise ApiError(409, "venue_busy", f"{exc}，请稍后再试。")


def _insert_booking(db: Session, building_id: int, venue: Venue, data) -> dict:
    # 半开区间重叠判断：a.start < b.end 且 a.end > b.start
    clash = (
        db.query(Booking)
        .filter(
            Booking.venue_id == venue.id,
            Booking.cancelled.is_(False),
            Booking.start_at < data.end_at,
            Booking.end_at > data.start_at,
        )
        .order_by(Booking.start_at)
        .first()
    )
    if clash is not None:
        raise ApiError(
            409,
            "time_conflict",
            f"场地「{venue.name}」在 {data.start_at:%Y-%m-%d %H:%M}"
            f"~{data.end_at:%Y-%m-%d %H:%M} 已被占用："
            f"场次「{clash.title}」（预订人：{clash.booker}，"
            f"{clash.start_at:%Y-%m-%d %H:%M} ~ {clash.end_at:%Y-%m-%d %H:%M}）"
            "与该时段冲突，请换个时段或换间场地。",
            extra={
                "occupier": {
                    "id": clash.id,
                    "title": clash.title,
                    "booker": clash.booker,
                    "start_at": clash.start_at.isoformat(timespec="minutes"),
                    "end_at": clash.end_at.isoformat(timespec="minutes"),
                }
            },
        )

    b = Booking(
        venue_id=venue.id,
        title=data.title,
        booker=data.booker,
        start_at=data.start_at,
        end_at=data.end_at,
        remark=data.remark or "",
        status=BOOKING_STATUS[0],
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    invalidate_schedule_cache(building_id)
    range_start = datetime.combine(b.start_at.date(), time.min)
    range_end = range_start + timedelta(days=1)
    return _booking_to_dict(b, range_start, range_end)


def cancel_booking(db: Session, building_id: int, booking_id: int) -> None:
    get_building_or_404(db, building_id)
    b = db.get(Booking, booking_id)
    if b is None:
        raise ApiError(404, "booking_not_found", f"档期不存在（id={booking_id}）。")
    if b.venue.floor.building_id != building_id:
        raise ApiError(
            403,
            "cross_building_denied",
            f"该档期属于楼栋「{b.venue.floor.building.name}」，"
            "不能在当前楼栋取消。",
        )
    b.cancelled = True
    b.status = "已取消"
    db.commit()
    invalidate_schedule_cache(building_id)
