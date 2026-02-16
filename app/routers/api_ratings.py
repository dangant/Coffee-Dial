from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.rating import RatingCreate, RatingRead, RatingUpdate
from app.services import brew_service, rating_service

router = APIRouter(prefix="/api/v1/brews/{brew_id}/rating", tags=["ratings"])


@router.post("/", response_model=RatingRead, status_code=201)
def create_rating(brew_id: int, data: RatingCreate, db: Session = Depends(get_db)):
    if not brew_service.get_brew(db, brew_id):
        raise HTTPException(status_code=404, detail="Brew not found")
    existing = rating_service.get_rating(db, brew_id)
    if existing:
        raise HTTPException(status_code=409, detail="Rating already exists for this brew")
    return rating_service.create_rating(db, brew_id, data)


@router.get("/", response_model=RatingRead)
def get_rating(brew_id: int, db: Session = Depends(get_db)):
    rating = rating_service.get_rating(db, brew_id)
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    return rating


@router.put("/", response_model=RatingRead)
def update_rating(brew_id: int, data: RatingUpdate, db: Session = Depends(get_db)):
    rating = rating_service.update_rating(db, brew_id, data)
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    return rating


@router.delete("/", status_code=204)
def delete_rating(brew_id: int, db: Session = Depends(get_db)):
    if not rating_service.delete_rating(db, brew_id):
        raise HTTPException(status_code=404, detail="Rating not found")
