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
    bean_name: Optional[str] = None
    roaster: Optional[str] = None
    bean_origin: Optional[str] = None
    bean_process: Optional[str] = None
    flavor_notes: list[str] = []
    espresso: dict[str, Any] = {}
    pour_over: dict[str, Any] = {}
    grams: Optional[float] = None
    price: Optional[float] = None


@router.post("/onyx/preview")
def preview_onyx(body: PreviewRequest, db: Session = Depends(get_db)):
    try:
        return onyx_import_service.parse_onyx(body.url)
    except OnyxImportError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/onyx/commit")
def commit_onyx(body: CommitRequest, db: Session = Depends(get_db)):
    if not body.product_name.strip():
        raise HTTPException(status_code=400, detail="A name is required.")
    if body.grams is not None and body.grams < 0:
        raise HTTPException(status_code=400, detail="Grams must be non-negative.")
    if body.price is not None and body.price < 0:
        raise HTTPException(status_code=400, detail="Price must be non-negative.")
    try:
        return onyx_import_service.commit_import(db, body.model_dump())
    except OnyxImportError as e:
        raise HTTPException(status_code=400, detail=str(e))
