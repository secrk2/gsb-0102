from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from .models import EQUIPMENT_ITEMS, VENUE_STATUS, VENUE_TYPES


class BuildingOut(BaseModel):
    id: int
    name: str
    code: str
    sort_order: int


class FloorOut(BaseModel):
    id: int
    building_id: int
    level: int
    name: str


class VenueBase(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    door_plate: str = Field(min_length=1, max_length=32)
    capacity: int = Field(ge=0, le=10000)
    venue_type: str
    equipment: List[str] = Field(default_factory=list)
    status: str = "可订"

    @field_validator("venue_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in VENUE_TYPES:
            raise ValueError(f"场地类型必须是：{'、'.join(VENUE_TYPES)}")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in VENUE_STATUS:
            raise ValueError(f"场地状态必须是：{'、'.join(VENUE_STATUS)}")
        return v

    @field_validator("equipment")
    @classmethod
    def _check_equipment(cls, v: List[str]) -> List[str]:
        bad = [x for x in v if x not in EQUIPMENT_ITEMS]
        if bad:
            raise ValueError(f"未知配套设备：{'、'.join(bad)}")
        return list(dict.fromkeys(v))


class VenueCreate(VenueBase):
    floor_id: int


class VenueUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=64)
    door_plate: Optional[str] = Field(default=None, min_length=1, max_length=32)
    capacity: Optional[int] = Field(default=None, ge=0, le=10000)
    venue_type: Optional[str] = None
    equipment: Optional[List[str]] = None
    status: Optional[str] = None
    floor_id: Optional[int] = None


class VenueOut(BaseModel):
    id: int
    floor_id: int
    building_id: int
    name: str
    door_plate: str
    capacity: int
    venue_type: str
    equipment: List[str]
    status: str
    floor_name: str
    building_name: str


class BookingBase(BaseModel):
    title: str = Field(min_length=1, max_length=128)
    booker: str = Field(min_length=1, max_length=64)
    start_at: datetime
    end_at: datetime
    remark: str = ""


class BookingCreate(BookingBase):
    @field_validator("end_at")
    @classmethod
    def _check_range(cls, v: datetime, info):
        start = info.data.get("start_at")
        if start and v <= start:
            raise ValueError("结束时间必须晚于开始时间")
        return v


class BookingOut(BookingBase):
    id: int
    venue_id: int
    venue_name: str
    status: str
    cancelled: bool
    touched_dates: List[str] = []
    starts_before_range: bool = False
    ends_after_range: bool = False
