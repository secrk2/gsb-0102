from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# 场地类型
TYPE_MEETING = "meeting_room"   # 会议室
TYPE_ROADSHOW = "roadshow_hall"  # 路演厅
TYPE_TRAINING = "training_room"  # 培训室
TYPE_EVENT = "event_space"       # 活动场地
VENUE_TYPES = {TYPE_MEETING, TYPE_ROADSHOW, TYPE_TRAINING, TYPE_EVENT}

# 场地状态
STATUS_AVAILABLE = "available"   # 可订
STATUS_RENOVATING = "renovating"  # 装修中
STATUS_DISABLED = "disabled"     # 停用
VENUE_STATUSES = {STATUS_AVAILABLE, STATUS_RENOVATING, STATUS_DISABLED}

# 配套设备
FACILITY_PROJECTOR = "projector"        # 投影
FACILITY_VIDEO_CONF = "video_conf"      # 视频会议
FACILITY_WHITEBOARD = "whiteboard"      # 白板
FACILITIES = {FACILITY_PROJECTOR, FACILITY_VIDEO_CONF, FACILITY_WHITEBOARD}

# 场次状态
BOOKING_CONFIRMED = "confirmed"
BOOKING_CANCELED = "canceled"


class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)

    floors: Mapped[list["Floor"]] = relationship(
        back_populates="building", cascade="all, delete-orphan", order_by="Floor.level"
    )
    venues: Mapped[list["Venue"]] = relationship(back_populates="building")


class Floor(Base):
    __tablename__ = "floors"
    __table_args__ = (
        UniqueConstraint("building_id", "level", name="uk_floor_building_level"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)  # 楼层数，如 1、3、-1
    name: Mapped[str] = mapped_column(String(32), nullable=False)  # 如 "3F"

    building: Mapped[Building] = relationship(back_populates="floors")
    venues: Mapped[list["Venue"]] = relationship(back_populates="floor")


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        UniqueConstraint("floor_id", "room_no", name="uk_venue_floor_room"),
        CheckConstraint("capacity > 0", name="ck_venue_capacity_positive"),
        Index("ix_venue_building", "building_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    building_id: Mapped[int] = mapped_column(
        ForeignKey("buildings.id", ondelete="RESTRICT"), nullable=False
    )
    floor_id: Mapped[int] = mapped_column(
        ForeignKey("floors.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    room_no: Mapped[str] = mapped_column(String(32), nullable=False)  # 门牌
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    venue_type: Mapped[str] = mapped_column(String(32), nullable=False)
    facilities: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_AVAILABLE)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    building: Mapped[Building] = relationship(back_populates="venues")
    floor: Mapped[Floor] = relationship(back_populates="venues")
    bookings: Mapped[list["Booking"]] = relationship(back_populates="venue")


class Booking(Base):
    """一个场地的一个场次（档期记录）。[start_at, end_at) 半开区间，允许跨天。"""

    __tablename__ = "bookings"
    __table_args__ = (
        Index("ix_booking_venue_time", "venue_id", "start_at", "end_at"),
        Index("ix_booking_start", "start_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # 场地被删时档期记录保留（历史可追溯），外键置空；场地名冗余快照在 venue_name
    venue_id: Mapped[int | None] = mapped_column(
        ForeignKey("venues.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    organizer: Mapped[str] = mapped_column(String(64), nullable=False)  # 占用方
    venue_name: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=BOOKING_CONFIRMED)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    venue: Mapped[Venue] = relationship(back_populates="bookings")
