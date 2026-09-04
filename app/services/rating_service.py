from sqlalchemy.orm import Session

from app.models.rating import Rating
from app.schemas.rating import RatingCreate, RatingUpdate

# The six taste attributes are recorded as Low / Neutral / High rather than a
# fine-grained scale. They keep their numeric column (1 / 3 / 5) so trends,
# correlations and the recommendation rules ("bitterness >= 4", "body <= 2")
# keep working, and so ratings taken on the old 1-5 slider still read back.
ATTRIBUTES = ["bitterness", "acidity", "sweetness", "body", "aroma", "aftertaste"]
LEVELS = [("low", "Low", 1.0), ("neutral", "Neutral", 3.0), ("high", "High", 5.0)]


def level_of(value: float | None) -> str | None:
    """Bucket a stored attribute value into 'low' / 'neutral' / 'high'."""
    if value is None:
        return None
    if value <= 2.5:
        return "low"
    if value >= 4:
        return "high"
    return "neutral"


def level_label(value: float | None) -> str:
    """Human label for a stored attribute value ('—' when unrated)."""
    bucket = level_of(value)
    return next((label for key, label, _ in LEVELS if key == bucket), "—")


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
