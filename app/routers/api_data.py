"""Data export / import endpoints for migrating between deployments."""

from datetime import date, datetime
from io import BytesIO
import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.brew import Brew
from app.models.rating import Rating
from app.models.template import BrewTemplate
from app.models.inventory import BeanInventory
from app.models.lookups import FlavorNote, BrewDevice, Grinder

router = APIRouter(prefix="/api/v1/data", tags=["data"])

EXPORT_VERSION = 1


def _serialize(val):
    """Convert non-JSON-serializable types."""
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    return val


def _row_to_dict(row, exclude=("_sa_instance_state",)):
    return {k: _serialize(v) for k, v in row.__dict__.items() if k not in exclude}


@router.get("/export")
def export_all(db: Session = Depends(get_db)):
    """Download all user data as a JSON file."""
    templates = [_row_to_dict(t) for t in db.query(BrewTemplate).all()]
    brews = [_row_to_dict(b) for b in db.query(Brew).all()]
    ratings = [_row_to_dict(r) for r in db.query(Rating).all()]
    inventory = [_row_to_dict(i) for i in db.query(BeanInventory).all()]
    flavor_notes = [_row_to_dict(f) for f in db.query(FlavorNote).all()]
    brew_devices = [_row_to_dict(d) for d in db.query(BrewDevice).all()]
    grinders = [_row_to_dict(g) for g in db.query(Grinder).all()]

    payload = {
        "version": EXPORT_VERSION,
        "exported_at": datetime.utcnow().isoformat(),
        "brew_templates": templates,
        "brews": brews,
        "ratings": ratings,
        "bean_inventory": inventory,
        "flavor_notes": flavor_notes,
        "brew_devices": brew_devices,
        "grinders": grinders,
    }

    buf = BytesIO(json.dumps(payload, indent=2).encode())
    return StreamingResponse(
        buf,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=coffeedata_export.json"},
    )


def _parse_date(val):
    if val is None:
        return None
    return date.fromisoformat(val)


def _parse_datetime(val):
    if val is None:
        return None
    return datetime.fromisoformat(val)


@router.post("/import")
def import_all(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Import data from a previously exported JSON file.

    This REPLACES all existing data — intended for migrating to a fresh database.
    """
    try:
        raw = file.file.read()
        data = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if "version" not in data:
        raise HTTPException(status_code=400, detail="Missing version field — not a valid export file")

    # Clear existing user data (order matters for foreign keys)
    db.query(Rating).delete()
    db.query(Brew).delete()
    db.query(BrewTemplate).delete()
    db.query(BeanInventory).delete()
    db.query(FlavorNote).delete()
    db.query(BrewDevice).delete()
    db.query(Grinder).delete()
    db.flush()

    counts = {}

    # --- Lookups ---
    for item in data.get("flavor_notes", []):
        db.add(FlavorNote(id=item["id"], name=item["name"]))
    counts["flavor_notes"] = len(data.get("flavor_notes", []))

    for item in data.get("brew_devices", []):
        db.add(BrewDevice(id=item["id"], name=item["name"]))
    counts["brew_devices"] = len(data.get("brew_devices", []))

    for item in data.get("grinders", []):
        db.add(Grinder(id=item["id"], name=item["name"]))
    counts["grinders"] = len(data.get("grinders", []))

    db.flush()

    # --- Templates ---
    for t in data.get("brew_templates", []):
        db.add(BrewTemplate(
            id=t["id"],
            name=t["name"],
            roaster=t.get("roaster"),
            bean_name=t.get("bean_name"),
            bean_origin=t.get("bean_origin"),
            bean_process=t.get("bean_process"),
            roast_date=_parse_date(t.get("roast_date")),
            roast_level=t.get("roast_level"),
            flavor_notes_expected=t.get("flavor_notes_expected"),
            bean_amount_grams=t.get("bean_amount_grams"),
            grind_setting=t.get("grind_setting"),
            grinder=t.get("grinder"),
            bloom=t.get("bloom"),
            bloom_time_seconds=t.get("bloom_time_seconds"),
            bloom_water_ml=t.get("bloom_water_ml"),
            water_amount_ml=t.get("water_amount_ml"),
            water_temp_f=t.get("water_temp_f"),
            water_temp_c=t.get("water_temp_c"),
            brew_method=t.get("brew_method"),
            brew_device=t.get("brew_device"),
            brew_time_seconds=t.get("brew_time_seconds"),
            water_filter_type=t.get("water_filter_type"),
            altitude_ft=t.get("altitude_ft"),
            notes=t.get("notes"),
            created_at=_parse_datetime(t.get("created_at")),
            updated_at=_parse_datetime(t.get("updated_at")),
        ))
    counts["brew_templates"] = len(data.get("brew_templates", []))
    db.flush()

    # --- Brews ---
    for b in data.get("brews", []):
        db.add(Brew(
            id=b["id"],
            brew_date=_parse_date(b["brew_date"]),
            roaster=b["roaster"],
            bean_name=b["bean_name"],
            bean_origin=b.get("bean_origin"),
            bean_process=b.get("bean_process"),
            roast_date=_parse_date(b.get("roast_date")),
            roast_level=b.get("roast_level"),
            flavor_notes_expected=b.get("flavor_notes_expected"),
            bean_amount_grams=b["bean_amount_grams"],
            grind_setting=b.get("grind_setting"),
            grinder=b.get("grinder"),
            bloom=b.get("bloom", False),
            bloom_time_seconds=b.get("bloom_time_seconds"),
            bloom_water_ml=b.get("bloom_water_ml"),
            water_amount_ml=b["water_amount_ml"],
            water_temp_f=b.get("water_temp_f"),
            water_temp_c=b.get("water_temp_c"),
            brew_method=b["brew_method"],
            brew_device=b.get("brew_device"),
            brew_time_seconds=b.get("brew_time_seconds"),
            water_filter_type=b.get("water_filter_type"),
            altitude_ft=b.get("altitude_ft"),
            notes=b.get("notes"),
            template_id=b.get("template_id"),
            created_at=_parse_datetime(b.get("created_at")),
            updated_at=_parse_datetime(b.get("updated_at")),
        ))
    counts["brews"] = len(data.get("brews", []))
    db.flush()

    # --- Ratings ---
    for r in data.get("ratings", []):
        db.add(Rating(
            id=r["id"],
            brew_id=r["brew_id"],
            overall_score=r["overall_score"],
            bitterness=r.get("bitterness"),
            acidity=r.get("acidity"),
            sweetness=r.get("sweetness"),
            body=r.get("body"),
            aroma=r.get("aroma"),
            aftertaste=r.get("aftertaste"),
            flavor_notes_experienced=r.get("flavor_notes_experienced"),
            flavor_notes_accuracy=r.get("flavor_notes_accuracy"),
            comments=r.get("comments"),
        ))
    counts["ratings"] = len(data.get("ratings", []))
    db.flush()

    # --- Inventory ---
    for i in data.get("bean_inventory", []):
        db.add(BeanInventory(
            id=i["id"],
            bean_name=i["bean_name"],
            roaster=i.get("roaster"),
            initial_amount_grams=i["initial_amount_grams"],
            created_at=_parse_datetime(i.get("created_at")),
            updated_at=_parse_datetime(i.get("updated_at")),
        ))
    counts["bean_inventory"] = len(data.get("bean_inventory", []))

    db.commit()

    return {"status": "ok", "imported": counts}
