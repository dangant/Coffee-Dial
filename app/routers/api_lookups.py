from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import lookup_service

router = APIRouter(prefix="/api/v1/lookups", tags=["lookups"])


class LookupItem(BaseModel):
    id: int
    name: str
    model_config = {"from_attributes": True}


class LookupCreate(BaseModel):
    name: str


@router.get("/flavor-notes", response_model=list[LookupItem])
def list_flavor_notes(db: Session = Depends(get_db)):
    return lookup_service.list_flavor_notes(db)


@router.post("/flavor-notes", response_model=LookupItem, status_code=201)
def add_flavor_note(data: LookupCreate, db: Session = Depends(get_db)):
    return lookup_service.add_flavor_note(db, data.name.strip())


@router.get("/grinders", response_model=list[LookupItem])
def list_grinders(db: Session = Depends(get_db)):
    return lookup_service.list_grinders(db)


@router.post("/grinders", response_model=LookupItem, status_code=201)
def add_grinder(data: LookupCreate, db: Session = Depends(get_db)):
    return lookup_service.add_grinder(db, data.name.strip())


@router.get("/brew-devices", response_model=list[LookupItem])
def list_brew_devices(db: Session = Depends(get_db)):
    return lookup_service.list_brew_devices(db)


@router.post("/brew-devices", response_model=LookupItem, status_code=201)
def add_brew_device(data: LookupCreate, db: Session = Depends(get_db)):
    return lookup_service.add_brew_device(db, data.name.strip())
