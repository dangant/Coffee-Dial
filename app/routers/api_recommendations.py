from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import brew_service, rating_service, recommendation_service

router = APIRouter(prefix="/api/v1/brews/{brew_id}/recommendations", tags=["recommendations"])


@router.get("/")
def get_recommendations(brew_id: int, db: Session = Depends(get_db)):
    brew = brew_service.get_brew(db, brew_id)
    if not brew:
        raise HTTPException(status_code=404, detail="Brew not found")
    rating = rating_service.get_rating(db, brew_id)
    if not rating:
        raise HTTPException(status_code=404, detail="No rating found for this brew")
    return recommendation_service.get_recommendations(db, brew, rating)
