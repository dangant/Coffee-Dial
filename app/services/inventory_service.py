import math

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.inventory import BeanInventory
from app.services.naming import bean_key, clean

POUR_OVER_GRAMS = 25.0
ESPRESSO_GRAMS = 18.0


def upsert_inventory(
    db: Session,
    bean_name: str,
    roaster: str | None,
    initial_grams: float,
    price: float | None = None,
) -> BeanInventory:
    bean_name, roaster = clean(bean_name), clean(roaster)
    inv = (
        db.query(BeanInventory)
        .filter(BeanInventory.bean_name == bean_name, BeanInventory.roaster == roaster)
        .first()
    )
    if inv:
        inv.initial_amount_grams = initial_grams
        if price is not None:
            inv.price = price
    else:
        inv = BeanInventory(
            bean_name=bean_name, roaster=roaster,
            initial_amount_grams=initial_grams, price=price,
            # Anchor tracking: don't count brews made before this bean was added.
            used_offset_grams=_grams_used(db, bean_name, roaster),
        )
        db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


def restock_inventory(
    db: Session,
    bean_name: str,
    roaster: str | None,
    add_grams: float,
    price: float | None = None,
) -> BeanInventory:
    """Add another bag: accumulate grams (and price = total spent) onto the running total."""
    bean_name, roaster = clean(bean_name), clean(roaster)
    inv = (
        db.query(BeanInventory)
        .filter(BeanInventory.bean_name == bean_name, BeanInventory.roaster == roaster)
        .first()
    )
    if inv:
        inv.initial_amount_grams += add_grams
        if price is not None:
            inv.price = (inv.price or 0) + price
    else:
        inv = BeanInventory(
            bean_name=bean_name, roaster=roaster,
            initial_amount_grams=add_grams, price=price,
            # Anchor tracking: don't count brews made before this bean was added.
            used_offset_grams=_grams_used(db, bean_name, roaster),
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


def _dose_lookup(db: Session) -> dict:
    """Per-bean brew doses, taken from that bean's own templates.

    Beans don't share a dose — an Onyx pour over might call for 16g or 25g depending
    on the coffee — so the shelf prices a cup using the recipe saved for that bean
    rather than one number applied to everything. Keyed by (bean_name, roaster) and
    also by bean_name alone, so a shelf entry still matches when the roaster differs.
    The most recently created template wins when a bean has several for one method.
    """
    from app.models.template import BrewTemplate

    rows = (
        db.query(
            BrewTemplate.bean_name,
            BrewTemplate.roaster,
            BrewTemplate.brew_method,
            BrewTemplate.bean_amount_grams,
        )
        .filter(
            BrewTemplate.bean_name.isnot(None),
            BrewTemplate.bean_amount_grams.isnot(None),
        )
        .order_by(BrewTemplate.id)
        .all()
    )

    lookup: dict = {}
    for bean_name, roaster, method, grams in rows:
        field = "espresso_dose" if (method or "").strip().lower() == "espresso" else "pour_over_dose"
        for key in (bean_key(bean_name, roaster), bean_key(bean_name, None)):
            lookup.setdefault(key, {})[field] = grams
    return lookup


def _doses_for(lookup: dict, bean_name: str, roaster: str | None) -> dict:
    match = (
        lookup.get(bean_key(bean_name, roaster))
        or lookup.get(bean_key(bean_name, None))
        or {}
    )
    return {
        "pour_over_dose": match.get("pour_over_dose"),
        "espresso_dose": match.get("espresso_dose"),
    }


def _grams_used(db: Session, bean_name: str, roaster: str | None) -> float:
    bean, roast = bean_key(bean_name, roaster)
    q = db.query(func.sum(Brew.bean_amount_grams)).filter(
        func.lower(func.trim(Brew.bean_name)) == bean
    )
    if roast:
        q = q.filter(func.lower(func.trim(Brew.roaster)) == roast)
    return q.scalar() or 0.0


def list_shelf(db: Session) -> list[dict]:
    """
    Returns every tracked bean (has inventory entry) plus any beans seen in brew history
    that have no inventory entry yet (marked as untracked).
    """
    inventory = db.query(BeanInventory).order_by(BeanInventory.bean_name).all()
    inv_keys = {bean_key(i.bean_name, i.roaster) for i in inventory}
    doses = _dose_lookup(db)

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
        # Only count brews since this bean was added to the shelf (offset out prior history).
        used = max(0.0, _grams_used(db, inv.bean_name, inv.roaster) - (inv.used_offset_grams or 0.0))
        remaining = max(0.0, inv.initial_amount_grams - used)
        result.append(
            {
                "id": inv.id,
                "bean_name": inv.bean_name,
                "roaster": inv.roaster,
                "initial_grams": inv.initial_amount_grams,
                "price": inv.price,
                # Blended cost across every bag stocked, so the page can price a dose.
                "price_per_gram": (
                    inv.price / inv.initial_amount_grams
                    if inv.price and inv.initial_amount_grams
                    else None
                ),
                "used_grams": round(used, 1),
                "remaining_grams": round(remaining, 1),
                "tracked": True,
                **_doses_for(doses, inv.bean_name, inv.roaster),
            }
        )

    seen = set(inv_keys)
    for bean_name, roaster in brew_beans:
        key = bean_key(bean_name, roaster)
        if key not in seen:
            seen.add(key)
            used = _grams_used(db, bean_name, roaster)
            result.append(
                {
                    "id": None,
                    "bean_name": bean_name,
                    "roaster": roaster,
                    "initial_grams": None,
                    "price": None,
                    "price_per_gram": None,
                    "used_grams": round(used, 1),
                    "remaining_grams": None,
                    "tracked": False,
                    **_doses_for(doses, bean_name, roaster),
                }
            )

    return result


def get_lp_data(db: Session, bean_name: str | None = None, pour_over_grams: float | None = None, espresso_grams: float | None = None) -> dict:
    """
    Compute LP tradeoff for pour over vs espresso.
    Maximize total cups x + y
    Subject to: po_g*x + esp_g*y <= remaining_grams, x >= 0, y >= 0

    If bean_name provided, only use that bean's inventory.
    """
    po_g = pour_over_grams if pour_over_grams and pour_over_grams > 0 else POUR_OVER_GRAMS
    esp_g = espresso_grams if espresso_grams and espresso_grams > 0 else ESPRESSO_GRAMS

    shelf = list_shelf(db)
    if bean_name:
        wanted = bean_key(bean_name, None)[0]
        shelf = [r for r in shelf if bean_key(r["bean_name"], None)[0] == wanted]

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
            "pour_over_grams": po_g,
            "espresso_grams": esp_g,
        }

    max_pour_overs = math.floor(total_remaining / po_g)
    max_espressos = math.floor(total_remaining / esp_g)

    x_intercept = total_remaining / po_g
    y_intercept = total_remaining / esp_g

    # Constraint line runs from exact intercept to exact intercept
    steps = 60
    constraint_line = []
    for i in range(steps + 1):
        x = x_intercept * (1 - i / steps)
        y = (total_remaining - po_g * x) / esp_g
        constraint_line.append({"x": round(x, 3), "y": round(y, 3)})

    # Integer frontier: for each integer pour-over count, the max feasible espressos.
    integer_points = []
    for po in range(max_pour_overs + 1):
        esp = math.floor((total_remaining - po_g * po) / esp_g)
        if esp < 0:
            break
        beans_used = round(po * po_g + esp * esp_g, 1)
        leftover = round(total_remaining - beans_used, 1)
        integer_points.append({
            "pour_overs": po,
            "espressos": esp,
            "total_cups": po + esp,
            "beans_used": beans_used,
            "leftover": leftover,
        })

    return {
        "total_remaining_grams": round(total_remaining, 1),
        "x_intercept": round(x_intercept, 3),
        "y_intercept": round(y_intercept, 3),
        "max_pour_overs": max_pour_overs,
        "max_espressos": max_espressos,
        "optimal_pour_overs": 0,
        "optimal_espressos": max_espressos,
        "constraint_line": constraint_line,
        "integer_points": integer_points,
        "breakdown": [r for r in shelf if r["tracked"]],
        "pour_over_grams": po_g,
        "espresso_grams": esp_g,
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
