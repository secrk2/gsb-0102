from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from .database import Base


class Building(Base):
    __tablename__ = "buildings"

    id = Column(Integer, primary_key=True)
    name = Column(String(64), nullable=False, unique=True, comment="楼栋名称")
    code = Column(String(32), nullable=False, unique=True, comment="楼栋编码")
    sort_order = Column(Integer, nullable=False, default=0)

    floors = relationship(
        "Floor", back_populates="building", cascade="all, delete-orphan"
    )


class Floor(Base):
    __tablename__ = "floors"
    __table_args__ = (UniqueConstraint("building_id", "level", name="uk_floor_level"),)

    id = Column(Integer, primary_key=True)
    building_id = Column(
        Integer, ForeignKey("buildings.id", ondelete="CASCADE"), nullable=False
    )
    level = Column(Integer, nullable=False, comment="楼层号，如 3 表示 3 层")
    name = Column(String(32), nullable=False, comment="显示名，如 F3")

    building = relationship("Building", back_populates="floors")
    venues = relationship(
        "Venue", back_populates="floor", cascade="all, delete-orphan"
    )


# 场地类型 / 状态 / 配套设备：前后端共享的枚举
VENUE_TYPES = ("会议室", "路演厅", "培训室", "活动场地")
VENUE_STATUS = ("可订", "装修中", "停用")
EQUIPMENT_ITEMS = ("投影", "视频会议", "白板")

# 档期状态
BOOKING_STATUS = ("已占用", "已取消")


class Venue(Base):
    __tablename__ = "venues"
    __table_args__ = (
        UniqueConstraint("floor_id", "door_plate", name="uk_door_plate_per_floor"),
    )

    id = Column(Integer, primary_key=True)
    floor_id = Column(
        Integer, ForeignKey("floors.id", ondelete="CASCADE"), nullable=False
    )
    name = Column(String(64), nullable=False, comment="场地名称")
    door_plate = Column(String(32), nullable=False, comment="门牌号")
    capacity = Column(Integer, nullable=False, default=0, comment="容纳人数")
    venue_type = Column(String(16), nullable=False, comment="场地类型")
    equipment = Column(JSON, nullable=False, default=list, comment="配套设备列表")
    status = Column(String(16), nullable=False, default="可订", comment="场地状态")

    floor = relationship("Floor", back_populates="venues")
    bookings = relationship(
        "Booking", back_populates="venue", cascade="all, delete-orphan"
    )


class Booking(Base):
    """档期/占用记录。start_at/end_at 均为带时间的时刻，允许跨天。"""

    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    venue_id = Column(
        Integer, ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title = Column(String(128), nullable=False, comment="场次名称")
    booker = Column(String(64), nullable=False, comment="占用方/预订人")
    start_at = Column(DateTime, nullable=False, index=True)
    end_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(16), nullable=False, default="已占用")
    remark = Column(Text, nullable=False, default="")
    cancelled = Column(Boolean, nullable=False, default=False)

    venue = relationship("Venue", back_populates="bookings")
