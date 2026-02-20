from datetime import date

from sqlalchemy import desc, distinct, func
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


def get_distinct_beans(db: Session) -> list[tuple[str, str]]:
    """Return distinct (roaster, bean_name) pairs ordered by most recently brewed."""
    subq = (
        db.query(
            Brew.roaster,
            Brew.bean_name,
            func.max(Brew.brew_date).label("last_date"),
            func.max(Brew.id).label("last_id"),
        )
        .group_by(Brew.roaster, Brew.bean_name)
        .subquery()
    )
    rows = (
        db.query(subq.c.roaster, subq.c.bean_name)
        .order_by(desc(subq.c.last_date), desc(subq.c.last_id))
        .all()
    )
    return [(r[0], r[1]) for r in rows]


def get_distinct_methods(db: Session) -> list[str]:
    """Return distinct brew_method values ordered by most recently used."""
    subq = (
        db.query(
            Brew.brew_method,
            func.max(Brew.brew_date).label("last_date"),
            func.max(Brew.id).label("last_id"),
        )
        .group_by(Brew.brew_method)
        .subquery()
    )
    rows = (
        db.query(subq.c.brew_method)
        .order_by(desc(subq.c.last_date), desc(subq.c.last_id))
        .all()
    )
    return [r[0] for r in rows]


def get_recent_match(
    db: Session,
    roaster: str | None = None,
    bean_name: str | None = None,
    brew_method: str | None = None,
) -> Brew | None:
    """Return the most recent brew matching all provided filters."""
    query = db.query(Brew).options(joinedload(Brew.rating))
    if roaster:
        query = query.filter(Brew.roaster == roaster)
    if bean_name:
        query = query.filter(Brew.bean_name == bean_name)
    if brew_method:
        query = query.filter(Brew.brew_method == brew_method)
    return query.order_by(desc(Brew.brew_date), desc(Brew.id)).first()
