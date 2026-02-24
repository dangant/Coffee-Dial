import math

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.inventory import CoffeeInventory
from app.models.template import BrewTemplate

POUR_OVER_GRAMS = 25.0
ESPRESSO_GRAMS = 18.0


def upsert_inventory(db: Session, template_id: int, initial_grams: float) -> CoffeeInventory:
    inv = db.query(CoffeeInventory).filter(CoffeeInventory.template_id == template_id).first()
    if inv:
        inv.initial_amount_grams = initial_grams
    else:
        inv = CoffeeInventory(template_id=template_id, initial_amount_grams=initial_grams)
        db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def delete_inventory(db: Session, template_id: int) -> bool:
    inv = db.query(CoffeeInventory).filter(CoffeeInventory.template_id == template_id).first()
    if not inv:
        return False
    db.delete(inv)
    db.commit()
    return True


def _grams_used(db: Session, template_id: int) -> float:
    result = (
        db.query(func.sum(Brew.bean_amount_grams))
        .filter(Brew.template_id == template_id)
        .scalar()
    )
    return result or 0.0


def list_shelf(db: Session) -> list[dict]:
    templates = db.query(BrewTemplate).order_by(BrewTemplate.name).all()
    inventory_map = {
        inv.template_id: inv
        for inv in db.query(CoffeeInventory).all()
    }
    result = []
    for tpl in templates:
        inv = inventory_map.get(tpl.id)
        initial = inv.initial_amount_grams if inv else None
        used = _grams_used(db, tpl.id) if inv else 0.0
        remaining = max(0.0, initial - used) if initial is not None else None
        result.append({
            "template_id": tpl.id,
            "template_name": tpl.name,
            "bean_name": tpl.bean_name,
            "roaster": tpl.roaster,
            "brew_method": tpl.brew_method,
            "initial_grams": initial,
            "used_grams": used,
            "remaining_grams": remaining,
        })
    return result


def get_lp_data(db: Session) -> dict:
    """
    Compute LP tradeoff data for pour over vs espresso.
    Maximize total cups x + y
    Subject to: 25x + 18y <= total_remaining_grams, x >= 0, y >= 0
    """
    shelf = list_shelf(db)
    total_remaining = sum(
        item["remaining_grams"]
        for item in shelf
        if item["remaining_grams"] is not None
    )

    if total_remaining <= 0:
        return {
            "total_remaining_grams": 0,
            "max_pour_overs": 0,
            "max_espressos": 0,
            "optimal_pour_overs": 0,
            "optimal_espressos": 0,
            "constraint_line": [],
            "template_breakdown": shelf,
        }

    max_pour_overs = math.floor(total_remaining / POUR_OVER_GRAMS)
    max_espressos = math.floor(total_remaining / ESPRESSO_GRAMS)

    # Optimal: maximize total cups → all espresso (uses fewer grams per cup)
    optimal_espressos = max_espressos
    optimal_pour_overs = 0

    # Constraint boundary points for chart: (x, y) where 25x + 18y = total_remaining
    # From (max_pour_overs, 0) to (0, max_espressos)
    steps = 50
    constraint_line = []
    for i in range(steps + 1):
        x = max_pour_overs * (1 - i / steps)
        y = (total_remaining - POUR_OVER_GRAMS * x) / ESPRESSO_GRAMS
        constraint_line.append({"x": round(x, 2), "y": round(y, 2)})

    return {
        "total_remaining_grams": round(total_remaining, 1),
        "max_pour_overs": max_pour_overs,
        "max_espressos": max_espressos,
        "optimal_pour_overs": optimal_pour_overs,
        "optimal_espressos": optimal_espressos,
        "constraint_line": constraint_line,
        "template_breakdown": shelf,
    }
