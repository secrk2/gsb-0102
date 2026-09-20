from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .. import services
from ..database import get_db
from ..models import EQUIPMENT_ITEMS, VENUE_STATUS, VENUE_TYPES
from ..schemas import VenueCreate, VenueOut, VenueUpdate

router = APIRouter(prefix="/api/buildings/{building_id}/venues", tags=["venues"])


@router.get("/meta")
def venue_meta(building_id: int, db: Session = Depends(get_db)):
    """场地档案表单用枚举（类型/状态/设备）。"""
    services.get_building_or_404(db, building_id)
    return {
        "venue_types": list(VENUE_TYPES),
        "venue_status": list(VENUE_STATUS),
        "equipment_items": list(EQUIPMENT_ITEMS),
    }


@router.get("", response_model=list[VenueOut])
def list_venues(
    building_id: int,
    floor_id: int | None = None,
    status: str | None = None,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    return services.list_venues(db, building_id, floor_id, status, q)


@router.post("", response_model=VenueOut, status_code=201)
def create_venue(building_id: int, data: VenueCreate, db: Session = Depends(get_db)):
    return services.create_venue(db, building_id, data)


@router.put("/{venue_id}", response_model=VenueOut)
def update_venue(
    building_id: int, venue_id: int, data: VenueUpdate,
    db: Session = Depends(get_db),
):
    return services.update_venue(db, building_id, venue_id, data)


@router.delete("/{venue_id}", status_code=204)
def delete_venue(building_id: int, venue_id: int, db: Session = Depends(get_db)):
    services.delete_venue(db, building_id, venue_id)
