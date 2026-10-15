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


def template_for_brew(db: Session, brew: Brew) -> BrewTemplate | None:
    """The template a brew dials in: its own, or the one recipe for its coffee and method.

    A brew logged without picking its template from the dropdown has no link, which
    hid the Dialed Recipe button even though the coffee plainly had a recipe. Match
    those by coffee and method — but only when exactly one template fits; with two
    recipes for the same coffee and method, picking one would be a guess.
    """
    if brew.template_id:
        return brew.template
    key = bean_key(brew.bean_name, brew.roaster)
    matches = [
        tpl for tpl in db.query(BrewTemplate).filter(BrewTemplate.brew_method == brew.brew_method)
        if (tpl.bean_id == brew.bean_id if tpl.bean_id and brew.bean_id
            else tpl.bean_name and bean_key(tpl.bean_name, tpl.roaster) == key)
    ]
    return matches[0] if len(matches) == 1 else None


def update_template_from_brew(db: Session, brew_id: int) -> BrewTemplate | None:
    brew = db.query(Brew).filter(Brew.id == brew_id).first()
    if not brew:
        return None
    template = template_for_brew(db, brew)
    if not template:
        return None
    # Dialing an unlinked brew into its coffee's recipe makes it part of that recipe.
    brew.template_id = template.id
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
    """Per template, how many brews exist of *that template's coffee*.

    Pre-ticks "first brew" on the brew form. Counting per template made a coffee
    brewed as both espresso and pour over look new twice — the second recipe's first
    brew earned a second marker for a bean already brewed. A first brew is about the
    bean, not the recipe, so the count follows the bean.
    """
    from app.services.brew_service import beans_brewed_before

    brewed = beans_brewed_before(db)
    counts = {}
    for tpl in db.query(BrewTemplate).all():
        key = tpl.bean_id or bean_key(tpl.bean_name, tpl.roaster)
        # A template with no bean is a generic recipe — never pre-tick off it.
        counts[tpl.id] = 1 if (not tpl.bean_name or key in brewed) else 0
    return counts


def get_template(db: Session, template_id: int) -> BrewTemplate | None:
    return db.query(BrewTemplate).filter(BrewTemplate.id == template_id).first()


# Notes describe how one particular cup went, not the recipe — never carried forward.
_NOT_CARRIED_FORWARD = {"notes"}


def prefill_values(db: Session, template: BrewTemplate, values: dict) -> dict:
    """Fill the template's blank fields from the latest brew made from it.

    Dialing in is iterative: the next brew starts where the last one left off, so a
    grind setting worked out at the grinder shouldn't have to be retyped because the
    template never recorded one. The template still wins wherever it has a value.
    """
    last = (
        db.query(Brew)
        .filter(Brew.template_id == template.id)
        .order_by(Brew.brew_date.desc(), Brew.id.desc())
        .first()
    )
    if not last:
        return values
    # Water temp is one setting stored in two units; a template's °C must not be
    # overridden by the last brew's °F, which the form would prefer.
    has_temp = values.get("water_temp_f") is not None or values.get("water_temp_c") is not None
    for field in TEMPLATE_FIELDS:
        if field in _NOT_CARRIED_FORWARD or values.get(field) not in (None, ""):
            continue
        if has_temp and field in ("water_temp_f", "water_temp_c"):
            continue
        value = getattr(last, field)
        if value not in (None, ""):
            values[field] = value
    return values


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
