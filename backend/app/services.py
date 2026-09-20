"""业务逻辑层：占用锁、冲突判定、跨天查询、删除/越权拦截。"""

import json
import time
import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models
from .config import settings
from .redis_client import client, release_lock

WEEK_START_MONDAY = 0


class BizError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, extra: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.extra = extra or {}


# ---------------- 楼栋 / 楼层 ----------------

def list_buildings(db: Session) -> list[models.Building]:
    return list(
        db.scalars(
            select(models.Building)
            .options(selectinload(models.Building.floors))
            .order_by(models.Building.id)
        ).all()
    )


def get_building_or_404(db: Session, building_id: int) -> models.Building:
    b = db.get(models.Building, building_id)
    if b is None:
        # 明确报错，前端拿这个信息显示提示页而不是空白页
        raise BizError("building_not_found", f"楼栋 #{building_id} 不存在，可能已被删除或编号有误。", 404)
    return b


def create_building(db: Session, name: str, code: str) -> models.Building:
    if db.scalar(select(models.Building).where(models.Building.code == code)):
        raise BizError("building_code_exists", f"楼栋编号「{code}」已存在。", 409)
    b = models.Building(name=name, code=code)
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def create_floor(db: Session, building_id: int, level: int, name: str) -> models.Floor:
    get_building_or_404(db, building_id)
    exists = db.scalar(
        select(models.Floor).where(
            models.Floor.building_id == building_id, models.Floor.level == level
        )
    )
    if exists:
        raise BizError("floor_exists", f"该楼栋已有 {level} 层。", 409)
    f = models.Floor(building_id=building_id, level=level, name=name)
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


# ---------------- 场地 ----------------

def list_venues(db: Session, building_id: int) -> list[models.Venue]:
    get_building_or_404(db, building_id)
    return list(
        db.scalars(
            select(models.Venue)
            .options(selectinload(models.Venue.floor))
            .where(models.Venue.building_id == building_id)
            .order_by(models.Venue.floor_id, models.Venue.room_no)
        ).all()
    )


def get_venue(db: Session, venue_id: int) -> models.Venue:
    v = db.get(models.Venue, venue_id)
    if v is None:
        raise BizError("venue_not_found", f"场地 #{venue_id} 不存在，可能已被删除。", 404)
    return v


def _authorize_building(db: Session, venue: models.Venue, building_id: int) -> None:
    """跨楼栋访问拦截：当前楼栋上下文与场地所属楼栋不一致时挡回。"""
    current = db.get(models.Building, building_id)
    if current is None:
        raise BizError(
            "building_not_found",
            f"当前楼栋 #{building_id} 不存在，无法查看档期，请先选择有效楼栋。",
            404,
        )
    if venue.building_id != building_id:
        owner = db.get(models.Building, venue.building_id)
        owner_name = owner.name if owner else f"#{venue.building_id}"
        raise BizError(
            "cross_building_denied",
            f"场地「{venue.name}」属于{owner_name}，不属于当前楼栋「{current.name}」，"
            "不能跨楼栋查看或操作其档期。请切换到对应楼栋后再试。",
            403,
            {"owner_building_id": venue.building_id, "owner_building_name": owner_name},
        )


def create_venue(db: Session, data: dict) -> models.Venue:
    building = get_building_or_404(db, data["building_id"])
    floor = db.get(models.Floor, data["floor_id"])
    if floor is None or floor.building_id != building.id:
        raise BizError(
            "floor_not_in_building",
            f"楼层 #{data['floor_id']} 不属于楼栋「{building.name}」，场地无法挂到该楼层。",
            400,
        )
    dup = db.scalar(
        select(models.Venue).where(
            models.Venue.floor_id == floor.id, models.Venue.room_no == data["room_no"]
        )
    )
    if dup:
        raise BizError("room_no_exists", f"该楼层已有门牌「{data['room_no']}」的场地。", 409)
    v = models.Venue(**data)
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def update_venue(db: Session, venue_id: int, data: dict) -> models.Venue:
    v = get_venue(db, venue_id)
    if data.get("floor_id") is not None:
        floor = db.get(models.Floor, data["floor_id"])
        if floor is None or floor.building_id != v.building_id:
            raise BizError(
                "floor_not_in_building", "目标楼层不存在或不属于该场地所在楼栋。", 400
            )
    for key, val in data.items():
        if val is not None:
            setattr(v, key, val)
    db.commit()
    db.refresh(v)
    return v


def delete_venue(db: Session, venue_id: int) -> None:
    v = get_venue(db, venue_id)
    # 名下还有未来档期 -> 拦下不让删（已取消的不算）
    now = datetime.now()
    future = list(
        db.scalars(
            select(models.Booking)
            .where(
                models.Booking.venue_id == venue_id,
                models.Booking.status == models.BOOKING_CONFIRMED,
                models.Booking.end_at > now,
            )
            .order_by(models.Booking.start_at)
        ).all()
    )
    if future:
        nearest = future[0]
        raise BizError(
            "venue_has_future_bookings",
            f"场地「{v.name}」名下还有 {len(future)} 场未结束的档期，最早一场「{nearest.title}」"
            f"开始于 {nearest.start_at.strftime('%Y-%m-%d %H:%M')}，请先取消这些档期后再删除场地。",
            409,
            {"future_count": len(future), "nearest_booking_id": nearest.id},
        )
    db.delete(v)
    db.commit()
    _invalidate_schedule_cache(venue_id)


# ---------------- 档期 ----------------

def view_range(view: str, date_str: str) -> tuple[datetime, datetime, str]:
    """把日/周视图的入参日期换算成 [start, end) 半开区间。"""
    try:
        day = datetime.strptime(date_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        raise BizError("bad_date", f"日期格式不正确: {date_str!r}，应为 YYYY-MM-DD。", 400)
    if view == "day":
        start = datetime.combine(day, datetime.min.time())
        return start, start + timedelta(days=1), day.strftime("%Y-%m-%d")
    if view == "week":
        monday = day - timedelta(days=day.weekday())  # weekday(): 周一=0
        start = datetime.combine(monday, datetime.min.time())
        return start, start + timedelta(days=7), monday.strftime("%Y-%m-%d")
    raise BizError("bad_view", f"未知视图类型: {view!r}，仅支持 day / week。", 400)


def _cache_key(venue_id: int, view: str, anchor: str) -> str:
    return f"schedule:venue:{venue_id}:{view}:{anchor}"


def _invalidate_schedule_cache(venue_id: int) -> None:
    prefix = f"schedule:venue:{venue_id}:"
    for key in client.scan_iter(prefix + "*"):
        client.delete(key)


def get_schedule(
    db: Session, venue_id: int, building_id: int, view: str, date_str: str
) -> dict:
    range_start, range_end, anchor = view_range(view, date_str)
    v = (
        db.scalars(
            select(models.Venue)
            .options(selectinload(models.Venue.floor))
            .where(models.Venue.id == venue_id)
        )
        .first()
    )
    if v is None:
        raise BizError("venue_not_found", f"场地 #{venue_id} 不存在，可能已被删除。", 404)
    # 跨楼栋访问必须先于缓存/查询挡回来
    _authorize_building(db, v, building_id)

    key = _cache_key(venue_id, view, anchor)
    cached = client.get(key)
    if cached:
        payload = json.loads(cached)
        payload["cached"] = True
        return payload

    # 区间重叠：start_at < range_end AND end_at > range_start
    # 跨天场次在日/周视图中都会被整条取出，不会被切成两截或丢失。
    bookings = list(
        db.scalars(
            select(models.Booking)
            .where(
                models.Booking.venue_id == venue_id,
                models.Booking.status == models.BOOKING_CONFIRMED,
                models.Booking.start_at < range_end,
                models.Booking.end_at > range_start,
            )
            .order_by(models.Booking.start_at)
        ).all()
    )
    payload = {
        "view": view,
        "date": date_str,
        "range_start": range_start.isoformat(),
        "range_end": range_end.isoformat(),
        "venue": _venue_dict(v),
        "bookings": [_booking_dict(b) for b in bookings],
        "cached": False,
    }
    client.set(key, json.dumps(payload), ex=settings.SCHEDULE_CACHE_TTL_SECONDS)
    return payload


def _overlap_clause(start: datetime, end: datetime):
    return [
        models.Booking.status == models.BOOKING_CONFIRMED,
        models.Booking.start_at < end,
        models.Booking.end_at > start,
    ]


def create_booking(db: Session, data: dict) -> models.Booking:
    start: datetime = data["start_at"]
    end: datetime = data["end_at"]
    if end <= start:
        raise BizError("bad_time_range", "结束时间必须晚于开始时间。", 400)
    if (end - start) > timedelta(days=30):
        raise BizError("bad_time_range", "单场档期最长不能超过 30 天。", 400)

    venue_id = data["venue_id"]
    lock_key = f"lock:venue:{venue_id}"
    token = uuid.uuid4().hex

    # ---- Redis 占用锁：同一场地同时只放一个下单请求进临界区 ----
    deadline = time.time() + 3.0  # 最多等 3 秒，避免前台长时间挂起
    acquired = False
    while time.time() < deadline:
        if client.set(lock_key, token, nx=True, ex=settings.LOCK_TTL_SECONDS):
            acquired = True
            break
        time.sleep(0.1)
    if not acquired:
        raise BizError(
            "venue_busy",
            "该场地正有另一个场次在下单，请几秒后重试。",
            409,
            {"retryable": True},
        )

    try:
        v = (
            db.scalars(
                select(models.Venue)
                .where(models.Venue.id == venue_id)
                .with_for_update()
            )
            .first()
        )
        if v is None:
            raise BizError("venue_not_found", f"场地 #{venue_id} 不存在，无法下单。", 404)
        if v.status != models.STATUS_AVAILABLE:
            reason = {"renovating": "装修中", "disabled": "已停用"}.get(v.status, v.status)
            raise BizError(
                "venue_not_bookable",
                f"场地「{v.name}」当前状态为{reason}，暂不可预订。",
                409,
            )

        # ---- 时段冲突判定（[start,end) 与已确认场次重叠即撞） ----
        conflict = db.scalar(
            select(models.Booking)
            .where(models.Booking.venue_id == venue_id, *_overlap_clause(start, end))
            .order_by(models.Booking.start_at)
        )
        if conflict is not None:
            raise BizError(
                "time_conflict",
                f"时段冲突：{start.strftime('%Y-%m-%d %H:%M')} ~ {end.strftime('%m-%d %H:%M')} "
                f"已被「{conflict.title}」（占用方：{conflict.organizer}，"
                f"{conflict.start_at.strftime('%Y-%m-%d %H:%M')} ~ "
                f"{conflict.end_at.strftime('%m-%d %H:%M')}）占用，请换个时段。",
                409,
                {
                    "conflict_booking_id": conflict.id,
                    "conflict_title": conflict.title,
                    "conflict_organizer": conflict.organizer,
                    "conflict_start": conflict.start_at.isoformat(),
                    "conflict_end": conflict.end_at.isoformat(),
                },
            )

        booking = models.Booking(
            venue_id=venue_id,
            title=data["title"],
            organizer=data["organizer"],
            venue_name=v.name,
            start_at=start,
            end_at=end,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
    finally:
        # WATCH 事务释放；锁本身带 TTL，即使释放失败也不会死锁
        release_lock(lock_key, token)

    _invalidate_schedule_cache(venue_id)
    return booking


def cancel_booking(db: Session, booking_id: int, building_id: int) -> None:
    b = db.get(models.Booking, booking_id)
    if b is None:
        raise BizError("booking_not_found", f"档期 #{booking_id} 不存在。", 404)
    v = get_venue(db, b.venue_id)
    _authorize_building(db, v, building_id)
    if b.status == models.BOOKING_CANCELED:
        raise BizError("booking_already_canceled", "该档期已取消，无需重复操作。", 409)
    b.status = models.BOOKING_CANCELED
    db.commit()
    _invalidate_schedule_cache(b.venue_id)


def _venue_dict(v: models.Venue) -> dict:
    return {
        "id": v.id,
        "name": v.name,
        "room_no": v.room_no,
        "capacity": v.capacity,
        "venue_type": v.venue_type,
        "facilities": v.facilities,
        "status": v.status,
        "building_id": v.building_id,
        "floor_id": v.floor_id,
        "floor": {"id": v.floor.id, "level": v.floor.level, "name": v.floor.name}
        if v.floor
        else None,
    }


def _booking_dict(b: models.Booking) -> dict:
    return {
        "id": b.id,
        "venue_id": b.venue_id,
        "title": b.title,
        "organizer": b.organizer,
        "venue_name": b.venue_name,
        "start_at": b.start_at.isoformat(),
        "end_at": b.end_at.isoformat(),
        "status": b.status,
    }
