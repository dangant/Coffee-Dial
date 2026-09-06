from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.tier_entry import TIERS
from app.services import tier_service

router = APIRouter(prefix="/api/v1/tiers", tags=["tiers"])


class PlaceRequest(BaseModel):
    coffee_key: str
    tier: Optional[str] = None
    position: int = 0


class EntryCreate(BaseModel):
    bean_name: str
    roaster: Optional[str] = None
    bean_origin: Optional[str] = None
    bean_process: Optional[str] = None
    flavor_notes: Optional[str] = None
    notes: Optional[str] = None
    tier: Optional[str] = None


class EntryUpdate(BaseModel):
    tier: Optional[str] = None
    position: Optional[int] = None
    notes: Optional[str] = None
    bean_name: Optional[str] = None
    roaster: Optional[str] = None
    bean_origin: Optional[str] = None
    bean_process: Optional[str] = None
    flavor_notes: Optional[str] = None


@router.get("/board")
def get_board(db: Session = Depends(get_db)):
    return tier_service.get_board(db)


@router.get("/tiers")
def list_tiers():
    return TIERS


@router.post("/place")
def place(body: PlaceRequest, db: Session = Depends(get_db)):
    try:
        entry = tier_service.place(db, body.coffee_key, body.tier, body.position)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not entry:
        raise HTTPException(status_code=404, detail="No coffee matches that key.")
    return tier_service.get_board(db)


@router.post("/entries", status_code=201)
def create_entry(body: EntryCreate, db: Session = Depends(get_db)):
    if not body.bean_name.strip():
        raise HTTPException(status_code=400, detail="A coffee needs a name.")
    if body.tier is not None and body.tier not in TIERS:
        raise HTTPException(status_code=400, detail=f"Unknown tier: {body.tier}")
    entry = tier_service.add_manual(db, body.model_dump())
    return {"id": entry.id, "coffee_key": entry.coffee_key, "tier": entry.tier}


@router.put("/entries/{entry_id}")
def update_entry(entry_id: int, body: EntryUpdate, db: Session = Depends(get_db)):
    if body.tier is not None and body.tier not in TIERS:
        raise HTTPException(status_code=400, detail=f"Unknown tier: {body.tier}")
    entry = tier_service.update_entry(db, entry_id, body.model_dump(exclude_unset=True))
    if not entry:
        raise HTTPException(status_code=404, detail="Tier entry not found")
    return {"id": entry.id, "tier": entry.tier}


@router.delete("/entries/{entry_id}", status_code=204)
def delete_entry(entry_id: int, db: Session = Depends(get_db)):
    if not tier_service.delete_entry(db, entry_id):
        raise HTTPException(status_code=404, detail="Tier entry not found")


@router.get("/analytics")
def analytics(
    group_by: str = Query("bean_origin"),
    db: Session = Depends(get_db),
):
    try:
        return tier_service.tier_analytics(db, group_by)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
