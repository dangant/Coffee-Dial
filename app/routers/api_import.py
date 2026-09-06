from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import onyx_import_service
from app.services.onyx_import_service import OnyxImportError

router = APIRouter(prefix="/api/v1/import", tags=["import"])


class PreviewRequest(BaseModel):
    url: str


class CommitRequest(BaseModel):
    product_name: str
    url: Optional[str] = None
    bean_name: Optional[str] = None
    roaster: Optional[str] = None
    bean_origin: Optional[str] = None
    bean_process: Optional[str] = None
    # Onyx attribute wheel — editable in the preview before the templates are created.
    bean_variety: Optional[str] = None
    drying_method: Optional[str] = None
    harvest_season: Optional[str] = None
    production_roaster: Optional[str] = None
    preferred_extraction: Optional[str] = None
    roast_level: Optional[str] = None
    caffeine_mg: Optional[str] = None
    coffee_summary: Optional[str] = None
    flavor_notes: list[str] = []
    espresso: dict[str, Any] = {}
    pour_over: dict[str, Any] = {}
    grams: Optional[float] = None
    price: Optional[float] = None
    # grams/price are per bag; quantity is how many bags were bought.
    quantity: int = 1


@router.post("/onyx/preview")
def preview_onyx(body: PreviewRequest, db: Session = Depends(get_db)):
    try:
        return onyx_import_service.parse_onyx(body.url)
    except OnyxImportError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/onyx/backfill")
def backfill_onyx(dry_run: bool = False, db: Session = Depends(get_db)):
    """Refill empty fields on every template that still has its Onyx product link.

    Fills blanks only — never overwrites a value you already have.
    """
    return onyx_import_service.backfill_templates(db, dry_run=dry_run)


@router.post("/onyx/commit")
def commit_onyx(body: CommitRequest, db: Session = Depends(get_db)):
    if not body.product_name.strip():
        raise HTTPException(status_code=400, detail="A name is required.")
    if body.grams is not None and body.grams < 0:
        raise HTTPException(status_code=400, detail="Grams must be non-negative.")
    if body.price is not None and body.price < 0:
        raise HTTPException(status_code=400, detail="Price must be non-negative.")
    if body.quantity < 1:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1.")
    try:
        return onyx_import_service.commit_import(db, body.model_dump())
    except OnyxImportError as e:
        raise HTTPException(status_code=400, detail=str(e))
