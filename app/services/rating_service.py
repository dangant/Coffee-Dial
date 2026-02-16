from sqlalchemy.orm import Session

from app.models.rating import Rating
from app.schemas.rating import RatingCreate, RatingUpdate


def create_rating(db: Session, brew_id: int, data: RatingCreate) -> Rating:
    rating = Rating(brew_id=brew_id, **data.model_dump())
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


def get_rating(db: Session, brew_id: int) -> Rating | None:
    return db.query(Rating).filter(Rating.brew_id == brew_id).first()


def update_rating(db: Session, brew_id: int, data: RatingUpdate) -> Rating | None:
    rating = db.query(Rating).filter(Rating.brew_id == brew_id).first()
    if not rating:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(rating, key, value)
    db.commit()
    db.refresh(rating)
    return rating


def delete_rating(db: Session, brew_id: int) -> bool:
    rating = db.query(Rating).filter(Rating.brew_id == brew_id).first()
    if not rating:
        return False
    db.delete(rating)
    db.commit()
    return True
