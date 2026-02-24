from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import inventory_service

router = APIRouter(prefix="/api/v1/shelf", tags=["shelf"])


class InventoryUpsert(BaseModel):
    bean_name: str
    roaster: Optional[str] = None
    initial_amount_grams: float


@router.get("/lp")
def get_lp(
    bean_name: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return inventory_service.get_lp_data(db, bean_name=bean_name)


@router.get("/beans")
def list_bean_names(db: Session = Depends(get_db)):
    return inventory_service.list_bean_names(db)


@router.get("")
def list_shelf(db: Session = Depends(get_db)):
    return inventory_service.list_shelf(db)


@router.post("")
def set_inventory(body: InventoryUpsert, db: Session = Depends(get_db)):
    if body.initial_amount_grams < 0:
        raise HTTPException(status_code=400, detail="Amount must be non-negative")
    inv = inventory_service.upsert_inventory(
        db, body.bean_name, body.roaster or None, body.initial_amount_grams
    )
    return {
        "id": inv.id,
        "bean_name": inv.bean_name,
        "roaster": inv.roaster,
        "initial_amount_grams": inv.initial_amount_grams,
    }


@router.delete("/{inv_id}")
def remove_inventory(inv_id: int, db: Session = Depends(get_db)):
    ok = inventory_service.delete_inventory(db, inv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="No inventory entry found")
    return {"ok": True}
