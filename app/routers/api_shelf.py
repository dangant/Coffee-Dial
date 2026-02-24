from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import inventory_service

router = APIRouter(prefix="/api/v1/shelf", tags=["shelf"])


class InventorySet(BaseModel):
    initial_amount_grams: float


@router.get("/lp")
def get_lp(db: Session = Depends(get_db)):
    return inventory_service.get_lp_data(db)


@router.get("")
def list_shelf(db: Session = Depends(get_db)):
    return inventory_service.list_shelf(db)


@router.post("/{template_id}")
def set_inventory(template_id: int, body: InventorySet, db: Session = Depends(get_db)):
    if body.initial_amount_grams < 0:
        raise HTTPException(status_code=400, detail="Amount must be non-negative")
    inv = inventory_service.upsert_inventory(db, template_id, body.initial_amount_grams)
    return {"template_id": inv.template_id, "initial_amount_grams": inv.initial_amount_grams}


@router.delete("/{template_id}")
def remove_inventory(template_id: int, db: Session = Depends(get_db)):
    ok = inventory_service.delete_inventory(db, template_id)
    if not ok:
        raise HTTPException(status_code=404, detail="No inventory entry found")
    return {"ok": True}
