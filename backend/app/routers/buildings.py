from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Building, Floor

router = APIRouter(prefix="/api/buildings", tags=["buildings"])


@router.get("")
def list_buildings(db: Session = Depends(get_db)):
    rows = db.query(Building).order_by(Building.sort_order, Building.id).all()
    return [
        {"id": b.id, "name": b.name, "code": b.code, "sort_order": b.sort_order}
        for b in rows
    ]


@router.get("/{building_id}/floors")
def list_floors(building_id: int, db: Session = Depends(get_db)):
    from .. import services

    building = services.get_building_or_404(db, building_id)
    rows = (
        db.query(Floor)
        .filter(Floor.building_id == building.id)
        .order_by(Floor.level)
        .all()
    )
    return [
        {"id": f.id, "building_id": f.building_id, "level": f.level, "name": f.name}
        for f in rows
    ]
