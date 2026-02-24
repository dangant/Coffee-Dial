import math

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.inventory import BeanInventory

POUR_OVER_GRAMS = 25.0
ESPRESSO_GRAMS = 18.0


def upsert_inventory(
    db: Session, bean_name: str, roaster: str | None, initial_grams: float
) -> BeanInventory:
    inv = (
        db.query(BeanInventory)
        .filter(BeanInventory.bean_name == bean_name, BeanInventory.roaster == roaster)
        .first()
    )
    if inv:
        inv.initial_amount_grams = initial_grams
    else:
        inv = BeanInventory(
            bean_name=bean_name, roaster=roaster, initial_amount_grams=initial_grams
        )
        db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def delete_inventory(db: Session, inv_id: int) -> bool:
    inv = db.query(BeanInventory).filter(BeanInventory.id == inv_id).first()
    if not inv:
        return False
    db.delete(inv)
    db.commit()
    return True


def _grams_used(db: Session, bean_name: str, roaster: str | None) -> float:
    q = db.query(func.sum(Brew.bean_amount_grams)).filter(Brew.bean_name == bean_name)
    if roaster:
        q = q.filter(Brew.roaster == roaster)
    return q.scalar() or 0.0


def list_shelf(db: Session) -> list[dict]:
    """
    Returns every tracked bean (has inventory entry) plus any beans seen in brew history
    that have no inventory entry yet (marked as untracked).
    """
    inventory = db.query(BeanInventory).order_by(BeanInventory.bean_name).all()
    inv_keys = {(i.bean_name, i.roaster) for i in inventory}

    # Beans from brew history not yet tracked
    brew_beans = (
        db.query(Brew.bean_name, Brew.roaster)
        .distinct()
        .filter(Brew.bean_name.isnot(None))
        .order_by(Brew.bean_name)
        .all()
    )

    result = []

    for inv in inventory:
        used = _grams_used(db, inv.bean_name, inv.roaster)
        remaining = max(0.0, inv.initial_amount_grams - used)
        result.append(
            {
                "id": inv.id,
                "bean_name": inv.bean_name,
                "roaster": inv.roaster,
                "initial_grams": inv.initial_amount_grams,
                "used_grams": round(used, 1),
                "remaining_grams": round(remaining, 1),
                "tracked": True,
            }
        )

    for bean_name, roaster in brew_beans:
        if (bean_name, roaster) not in inv_keys:
            used = _grams_used(db, bean_name, roaster)
            result.append(
                {
                    "id": None,
                    "bean_name": bean_name,
                    "roaster": roaster,
                    "initial_grams": None,
                    "used_grams": round(used, 1),
                    "remaining_grams": None,
                    "tracked": False,
                }
            )

    return result


def get_lp_data(db: Session, bean_name: str | None = None) -> dict:
    """
    Compute LP tradeoff for pour over vs espresso.
    Maximize total cups x + y
    Subject to: 25x + 18y <= remaining_grams, x >= 0, y >= 0

    If bean_name provided, only use that bean's inventory.
    """
    shelf = list_shelf(db)
    if bean_name:
        shelf = [r for r in shelf if r["bean_name"] == bean_name]

    total_remaining = sum(
        r["remaining_grams"] for r in shelf if r["remaining_grams"] is not None
    )

    if total_remaining <= 0:
        return {
            "total_remaining_grams": 0,
            "max_pour_overs": 0,
            "max_espressos": 0,
            "optimal_pour_overs": 0,
            "optimal_espressos": 0,
            "constraint_line": [],
            "breakdown": shelf,
        }

    max_pour_overs = math.floor(total_remaining / POUR_OVER_GRAMS)
    max_espressos = math.floor(total_remaining / ESPRESSO_GRAMS)

    # Optimal: maximize total cups → all espresso (18g < 25g per cup)
    steps = 60
    constraint_line = []
    for i in range(steps + 1):
        x = max_pour_overs * (1 - i / steps)
        y = (total_remaining - POUR_OVER_GRAMS * x) / ESPRESSO_GRAMS
        constraint_line.append({"x": round(x, 2), "y": round(y, 2)})

    return {
        "total_remaining_grams": round(total_remaining, 1),
        "max_pour_overs": max_pour_overs,
        "max_espressos": max_espressos,
        "optimal_pour_overs": 0,
        "optimal_espressos": max_espressos,
        "constraint_line": constraint_line,
        "breakdown": [r for r in shelf if r["tracked"]],
    }


def list_bean_names(db: Session) -> list[str]:
    """All distinct bean names that have inventory entries."""
    return [
        r.bean_name
        for r in db.query(BeanInventory.bean_name)
        .distinct()
        .order_by(BeanInventory.bean_name)
        .all()
    ]
