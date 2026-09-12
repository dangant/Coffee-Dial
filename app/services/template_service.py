from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.template import BrewTemplate
from app.schemas.template import TemplateCreate, TemplateUpdate
from app.services import bean_service
from app.services.naming import bean_key, clean

# Fields shared between Brew and BrewTemplate (excluding id, timestamps, template_id)
TEMPLATE_FIELDS = [
    "roaster", "bean_name", "bean_origin", "bean_process", "roast_date", "roast_level",
    "flavor_notes_expected", "bean_amount_grams", "grind_setting", "grinder",
    "bloom", "bloom_time_seconds", "bloom_water_ml", "bloom_pour_time_seconds",
    "first_pour_grams", "first_pour_time_seconds",
    "second_pour_grams", "second_pour_time_seconds",
    "final_pour_grams", "final_pour_time_seconds", "pour_method",
    "water_amount_ml",
    "water_temp_f", "water_temp_c", "brew_method", "brew_device",
    "brew_time_seconds", "water_filter_type",
    "altitude_ft", "notes",
]


def create_template(db: Session, data: TemplateCreate) -> BrewTemplate:
    values = data.model_dump()
    for field in ("bean_name", "roaster"):
        if field in values:
            values[field] = clean(values[field])
    template = BrewTemplate(**values)
    bean = bean_service.get_or_create(db, values.get("bean_name"), values.get("roaster"))
    template.bean_id = bean.id if bean else None
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def create_template_from_brew(db: Session, brew_id: int, name: str) -> BrewTemplate | None:
    brew = db.query(Brew).filter(Brew.id == brew_id).first()
    if not brew:
        return None
    values = {"name": name}
    for field in TEMPLATE_FIELDS:
        values[field] = getattr(brew, field)
    for field in ("bean_name", "roaster"):
        values[field] = clean(values[field])
    template = BrewTemplate(**values)
    # The brew already knows its coffee; carry the same id rather than re-resolving.
    template.bean_id = brew.bean_id
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template_from_brew(db: Session, brew_id: int) -> BrewTemplate | None:
    brew = db.query(Brew).filter(Brew.id == brew_id).first()
    if not brew or not brew.template_id:
        return None
    template = db.query(BrewTemplate).filter(BrewTemplate.id == brew.template_id).first()
    if not template:
        return None
    for field in TEMPLATE_FIELDS:
        value = getattr(brew, field)
        if field in ("bean_name", "roaster"):
            value = clean(value)
        setattr(template, field, value)
    template.bean_id = brew.bean_id
    db.commit()
    db.refresh(template)
    return template


def brew_counts(db: Session) -> dict[int, int]:
    """How many brews have been logged against each template, keyed by template id.

    Used to pre-tick "first brew" on the brew form for a template nothing has
    been brewed from yet.
    """
    from sqlalchemy import func

    rows = (
        db.query(Brew.template_id, func.count(Brew.id))
        .filter(Brew.template_id.isnot(None))
        .group_by(Brew.template_id)
        .all()
    )
    return {tpl_id: count for tpl_id, count in rows}


def get_template(db: Session, template_id: int) -> BrewTemplate | None:
    return db.query(BrewTemplate).filter(BrewTemplate.id == template_id).first()


def list_templates(db: Session) -> list[BrewTemplate]:
    return db.query(BrewTemplate).order_by(BrewTemplate.name).all()


def list_templates_on_shelf(db: Session) -> list[BrewTemplate]:
    """Templates whose bean is on the shelf with grams remaining.

    Templates without a bean_name are generic recipes, not tied to a bag,
    and are always included.
    """
    from app.services import inventory_service

    stocked = [
        r for r in inventory_service.list_shelf(db)
        if r["tracked"] and (r["remaining_grams"] or 0) > 0
    ]
    # Prefer the bean id, fall back to the name for rows that have no id yet — a
    # template the backfill couldn't resolve must not drop off the new-brew form.
    in_stock_ids = {r["bean_id"] for r in stocked if r["bean_id"]}
    in_stock = {bean_key(r["bean_name"], r["roaster"]) for r in stocked}
    return [
        t for t in list_templates(db)
        if not t.bean_name
        or (t.bean_id and t.bean_id in in_stock_ids)
        or bean_key(t.bean_name, t.roaster) in in_stock
    ]


def update_template(db: Session, template_id: int, data: TemplateUpdate) -> BrewTemplate | None:
    template = db.query(BrewTemplate).filter(BrewTemplate.id == template_id).first()
    if not template:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in ("bean_name", "roaster"):
            value = clean(value)
        setattr(template, key, value)
    updates = data.model_dump(exclude_unset=True)
    if "bean_name" in updates or "roaster" in updates:
        bean = bean_service.get_or_create(db, template.bean_name, template.roaster)
        template.bean_id = bean.id if bean else None
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, template_id: int) -> bool:
    template = db.query(BrewTemplate).filter(BrewTemplate.id == template_id).first()
    if not template:
        return False
    db.delete(template)
    db.commit()
    return True
