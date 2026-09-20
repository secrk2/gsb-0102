from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import FACILITIES, VENUE_STATUSES, VENUE_TYPES


# ---------- 楼栋 / 楼层 ----------
class FloorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    level: int
    name: str


class BuildingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    floors: list[FloorOut] = []


class BuildingCreate(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=32)


class FloorCreate(BaseModel):
    level: int
    name: str = Field(min_length=1, max_length=32)


# ---------- 场地 ----------
class VenueBase(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    room_no: str = Field(min_length=1, max_length=32)
    capacity: int = Field(gt=0)
    venue_type: str
    facilities: list[str] = []
    status: str = "available"

    @field_validator("venue_type")
    @classmethod
    def _check_type(cls, v: str) -> str:
        if v not in VENUE_TYPES:
            raise ValueError(f"非法场地类型: {v}")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str) -> str:
        if v not in VENUE_STATUSES:
            raise ValueError(f"非法场地状态: {v}")
        return v

    @field_validator("facilities")
    @classmethod
    def _check_facilities(cls, v: list[str]) -> list[str]:
        bad = [x for x in v if x not in FACILITIES]
        if bad:
            raise ValueError(f"非法配套设备: {bad}")
        return v


class VenueCreate(VenueBase):
    building_id: int
    floor_id: int


class VenueUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=64)
    room_no: str | None = Field(default=None, min_length=1, max_length=32)
    capacity: int | None = Field(default=None, gt=0)
    venue_type: str | None = None
    facilities: list[str] | None = None
    status: str | None = None
    floor_id: int | None = None

    @field_validator("venue_type")
    @classmethod
    def _check_type(cls, v: str | None) -> str | None:
        if v is not None and v not in VENUE_TYPES:
            raise ValueError(f"非法场地类型: {v}")
        return v

    @field_validator("status")
    @classmethod
    def _check_status(cls, v: str | None) -> str | None:
        if v is not None and v not in VENUE_STATUSES:
            raise ValueError(f"非法场地状态: {v}")
        return v

    @field_validator("facilities")
    @classmethod
    def _check_facilities(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        bad = [x for x in v if x not in FACILITIES]
        if bad:
            raise ValueError(f"非法配套设备: {bad}")
        return v


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    building_id: int
    floor_id: int
    name: str
    room_no: str
    capacity: int
    venue_type: str
    facilities: list[str]
    status: str
    floor: FloorOut | None = None


# ---------- 档期 / 场次 ----------
class BookingCreate(BaseModel):
    venue_id: int
    title: str = Field(min_length=1, max_length=128)
    organizer: str = Field(min_length=1, max_length=64)
    start_at: datetime
    end_at: datetime


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    venue_id: int | None = None
    title: str
    organizer: str
    venue_name: str = ""
    start_at: datetime
    end_at: datetime
    status: str
    venue: VenueOut | None = None
