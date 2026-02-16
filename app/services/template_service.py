from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.template import BrewTemplate
from app.schemas.template import TemplateCreate, TemplateUpdate

# Fields shared between Brew and BrewTemplate (excluding id, timestamps, template_id)
TEMPLATE_FIELDS = [
    "roaster", "bean_name", "bean_origin", "bean_process", "roast_date", "roast_level",
    "flavor_notes_expected", "bean_amount_grams", "grind_setting", "grinder",
    "bloom", "bloom_time_seconds", "bloom_water_ml", "water_amount_ml",
    "water_temp_f", "water_temp_c", "brew_method", "brew_device",
    "brew_time_seconds", "water_filter_type",
    "altitude_ft", "notes",
]


def create_template(db: Session, data: TemplateCreate) -> BrewTemplate:
    template = BrewTemplate(**data.model_dump())
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
    template = BrewTemplate(**values)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def get_template(db: Session, template_id: int) -> BrewTemplate | None:
    return db.query(BrewTemplate).filter(BrewTemplate.id == template_id).first()


def list_templates(db: Session) -> list[BrewTemplate]:
    return db.query(BrewTemplate).order_by(BrewTemplate.name).all()


def update_template(db: Session, template_id: int, data: TemplateUpdate) -> BrewTemplate | None:
    template = db.query(BrewTemplate).filter(BrewTemplate.id == template_id).first()
    if not template:
        return None
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(template, key, value)
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
