from datetime import date

from sqlalchemy import desc
from sqlalchemy.orm import Session, joinedload

from app.models.brew import Brew
from app.models.rating import Rating
from app.schemas.brew import BrewCreate, BrewUpdate


def create_brew(db: Session, data: BrewCreate) -> Brew:
    # Auto-convert temperatures
    values = data.model_dump()
    if values.get("water_temp_f") and not values.get("water_temp_c"):
        values["water_temp_c"] = round((values["water_temp_f"] - 32) * 5 / 9, 1)
    elif values.get("water_temp_c") and not values.get("water_temp_f"):
        values["water_temp_f"] = round(values["water_temp_c"] * 9 / 5 + 32, 1)

    brew = Brew(**values)
    db.add(brew)
    db.commit()
    db.refresh(brew)
    return brew


def get_brew(db: Session, brew_id: int) -> Brew | None:
    return (
        db.query(Brew)
        .options(joinedload(Brew.rating))
        .filter(Brew.id == brew_id)
        .first()
    )


def list_brews(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    roaster: str | None = None,
    brew_method: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[Brew]:
    query = db.query(Brew).options(joinedload(Brew.rating))
    if roaster:
        query = query.filter(Brew.roaster.ilike(f"%{roaster}%"))
    if brew_method:
        query = query.filter(Brew.brew_method.ilike(f"%{brew_method}%"))
    if date_from:
        query = query.filter(Brew.brew_date >= date_from)
    if date_to:
        query = query.filter(Brew.brew_date <= date_to)
    return query.order_by(desc(Brew.brew_date), desc(Brew.id)).offset(skip).limit(limit).all()


def update_brew(db: Session, brew_id: int, data: BrewUpdate) -> Brew | None:
    brew = db.query(Brew).filter(Brew.id == brew_id).first()
    if not brew:
        return None
    updates = data.model_dump(exclude_unset=True)
    # Auto-convert temperatures
    if "water_temp_f" in updates and updates["water_temp_f"] and "water_temp_c" not in updates:
        updates["water_temp_c"] = round((updates["water_temp_f"] - 32) * 5 / 9, 1)
    elif "water_temp_c" in updates and updates["water_temp_c"] and "water_temp_f" not in updates:
        updates["water_temp_f"] = round(updates["water_temp_c"] * 9 / 5 + 32, 1)
    for key, value in updates.items():
        setattr(brew, key, value)
    db.commit()
    db.refresh(brew)
    return brew


def delete_brew(db: Session, brew_id: int) -> bool:
    brew = db.query(Brew).filter(Brew.id == brew_id).first()
    if not brew:
        return False
    db.delete(brew)
    db.commit()
    return True
