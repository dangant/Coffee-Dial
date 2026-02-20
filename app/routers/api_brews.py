from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.brew import BrewCreate, BrewListRead, BrewRead, BrewUpdate
from app.services import brew_service

router = APIRouter(prefix="/api/v1/brews", tags=["brews"])


@router.post("/", response_model=BrewRead, status_code=201)
def create_brew(data: BrewCreate, db: Session = Depends(get_db)):
    return brew_service.create_brew(db, data)


@router.get("/", response_model=list[BrewListRead])
def list_brews(
    skip: int = 0,
    limit: int = 50,
    roaster: str | None = None,
    brew_method: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: Session = Depends(get_db),
):
    brews = brew_service.list_brews(db, skip, limit, roaster, brew_method, date_from, date_to)
    results = []
    for b in brews:
        results.append(BrewListRead(
            id=b.id,
            brew_date=b.brew_date,
            roaster=b.roaster,
            bean_name=b.bean_name,
            brew_method=b.brew_method,
            overall_score=b.rating.overall_score if b.rating else None,
        ))
    return results


@router.get("/{brew_id}", response_model=BrewRead)
def get_brew(brew_id: int, db: Session = Depends(get_db)):
    brew = brew_service.get_brew(db, brew_id)
    if not brew:
        raise HTTPException(status_code=404, detail="Brew not found")
    return brew


@router.put("/{brew_id}", response_model=BrewRead)
def update_brew(brew_id: int, data: BrewUpdate, db: Session = Depends(get_db)):
    brew = brew_service.update_brew(db, brew_id, data)
    if not brew:
        raise HTTPException(status_code=404, detail="Brew not found")
    return brew


@router.delete("/{brew_id}", status_code=204)
def delete_brew(brew_id: int, db: Session = Depends(get_db)):
    if not brew_service.delete_brew(db, brew_id):
        raise HTTPException(status_code=404, detail="Brew not found")
