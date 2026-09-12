from datetime import date

from sqlalchemy import desc, or_
from sqlalchemy.orm import Session, joinedload

from app.models.brew import Brew
from app.models.rating import Rating
from app.schemas.brew import BrewCreate, BrewUpdate
from app.services import bean_service
from app.services.naming import bean_key


def create_brew(db: Session, data: BrewCreate) -> Brew:
    # Auto-convert temperatures
    values = data.model_dump()
    # These two are the join key to templates and the shelf — trim before storing.
    for field in ("bean_name", "roaster"):
        if values.get(field):
            values[field] = values[field].strip()
    if values.get("water_temp_f") and not values.get("water_temp_c"):
        values["water_temp_c"] = round((values["water_temp_f"] - 32) * 5 / 9, 1)
    elif values.get("water_temp_c") and not values.get("water_temp_f"):
        values["water_temp_f"] = round(values["water_temp_c"] * 9 / 5 + 32, 1)

    brew = Brew(**values)
    # Every write goes through get_or_create, so a brew is attached to the coffee
    # itself rather than only to the spelling typed on the day.
    bean = bean_service.get_or_create(db, values.get("bean_name"), values.get("roaster"))
    brew.bean_id = bean.id if bean else None
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
    bean_name: str | None = None,
    grind: str | None = None,
) -> list[Brew]:
    query = db.query(Brew).options(joinedload(Brew.rating))
    if roaster:
        query = query.filter(Brew.roaster.ilike(f"%{roaster}%"))
    if brew_method:
        query = query.filter(Brew.brew_method.ilike(f"%{brew_method}%"))
    if bean_name:
        query = query.filter(Brew.bean_name.ilike(f"%{bean_name}%"))
    if grind:
        # A setting only means something next to its grinder, so one box searches
        # both: "Comandante" and "22" each find the same brew.
        query = query.filter(or_(
            Brew.grind_setting.ilike(f"%{grind}%"),
            Brew.grinder.ilike(f"%{grind}%"),
        ))
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
        if key in ("bean_name", "roaster") and value:
            value = value.strip()
        setattr(brew, key, value)
    # Re-resolve when either half of the identity changed, so an edit that fixes a
    # spelling moves the brew onto the right coffee instead of leaving a stale id.
    if "bean_name" in updates or "roaster" in updates:
        bean = bean_service.get_or_create(db, brew.bean_name, brew.roaster)
        brew.bean_id = bean.id if bean else None
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




def effective_first_brew_ids(db: Session) -> set[int]:
    """Brew ids that genuinely count as a first brew — at most one per coffee.

    The checkbox is per brew, and it used to be pre-ticked from the *template's* brew
    count, so a coffee brewed as both espresso and pour over earned two markers. What
    is actually meant is "the first time I brewed this bean", buying another bag or
    dialling a second method included — so among the flagged brews of one coffee, only
    the earliest survives.

    Derived rather than stored: nothing rewrites the flags, so unticking still works
    and the rule can change without a migration.
    """
    flagged = (
        db.query(Brew)
        .filter(Brew.is_first_brew.is_(True))
        .order_by(Brew.brew_date, Brew.id)
        .all()
    )
    earliest: dict = {}
    for brew in flagged:
        # bean_id is the real identity; fall back to the name for any row the
        # backfill could not resolve, so an unlinked brew still groups sensibly.
        key = brew.bean_id or bean_key(brew.bean_name, brew.roaster)
        earliest.setdefault(key, brew.id)
    return set(earliest.values())


def beans_brewed_before(db: Session) -> set:
    """Identity of every coffee that already has a brew logged against it.

    Feeds the brew form's "first brew" pre-tick. Keyed the same way as
    :func:`effective_first_brew_ids` so the two agree on what one coffee is.
    """
    rows = db.query(Brew.bean_id, Brew.bean_name, Brew.roaster).all()
    seen = set()
    for bean_id, bean_name, roaster in rows:
        seen.add(bean_id or bean_key(bean_name, roaster))
    return seen
