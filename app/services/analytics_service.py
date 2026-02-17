from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.rating import Rating


def get_summary(db: Session) -> dict:
    total_brews = db.query(func.count(Brew.id)).scalar() or 0
    avg_score = db.query(func.avg(Rating.overall_score)).scalar()
    avg_score = round(avg_score, 2) if avg_score else None

    top_roaster = (
        db.query(Brew.roaster, func.count(Brew.id).label("cnt"))
        .group_by(Brew.roaster)
        .order_by(func.count(Brew.id).desc())
        .first()
    )
    top_bean = (
        db.query(Brew.bean_name, func.count(Brew.id).label("cnt"))
        .group_by(Brew.bean_name)
        .order_by(func.count(Brew.id).desc())
        .first()
    )
    highest_rated = (
        db.query(Brew.bean_name, func.avg(Rating.overall_score).label("avg"))
        .join(Rating)
        .group_by(Brew.bean_name)
        .order_by(func.avg(Rating.overall_score).desc())
        .first()
    )

    return {
        "total_brews": total_brews,
        "average_score": avg_score,
        "top_roaster": top_roaster[0] if top_roaster else None,
        "top_bean": top_bean[0] if top_bean else None,
        "highest_rated_bean": {
            "name": highest_rated[0],
            "avg_score": round(highest_rated[1], 2),
        }
        if highest_rated
        else None,
    }


def _is_sqlite(db: Session) -> bool:
    return "sqlite" in str(db.bind.url)


def get_trends(db: Session, group_by: str = "day") -> list[dict]:
    if _is_sqlite(db):
        if group_by == "month":
            date_expr = func.strftime("%Y-%m", Brew.brew_date)
        elif group_by == "week":
            date_expr = func.strftime("%Y-%W", Brew.brew_date)
        else:
            date_expr = func.strftime("%Y-%m-%d", Brew.brew_date)
    else:
        if group_by == "month":
            date_expr = func.to_char(Brew.brew_date, "YYYY-MM")
        elif group_by == "week":
            date_expr = func.to_char(Brew.brew_date, "IYYY-IW")
        else:
            date_expr = func.to_char(Brew.brew_date, "YYYY-MM-DD")

    rows = (
        db.query(date_expr.label("period"), func.avg(Rating.overall_score).label("avg_score"))
        .join(Rating)
        .group_by("period")
        .order_by("period")
        .all()
    )
    return [{"period": r.period, "avg_score": round(r.avg_score, 2)} for r in rows]


def get_correlations(
    db: Session,
    x_field: str,
    y_field: str,
    bean_name: str | None = None,
    grinder: str | None = None,
) -> list[dict]:
    brew_fields = {
        "bean_amount_grams", "water_amount_ml",
        "water_temp_f", "water_temp_c", "brew_time_seconds",
        "grind_setting",
    }
    rating_fields = {
        "overall_score", "bitterness", "acidity", "sweetness",
        "body", "aroma", "aftertaste",
    }

    if x_field in brew_fields:
        x_col = getattr(Brew, x_field)
    elif x_field in rating_fields:
        x_col = getattr(Rating, x_field)
    else:
        return []

    if y_field in rating_fields:
        y_col = getattr(Rating, y_field)
    elif y_field in brew_fields:
        y_col = getattr(Brew, y_field)
    else:
        return []

    query = (
        db.query(x_col.label("x"), y_col.label("y"))
        .join(Rating)
        .filter(x_col.isnot(None), y_col.isnot(None))
    )
    if bean_name:
        query = query.filter(Brew.bean_name == bean_name)
    if grinder:
        query = query.filter(Brew.grinder == grinder)

    rows = query.all()

    results = []
    for r in rows:
        x_val = r.x
        y_val = r.y
        if x_field == "grind_setting":
            try:
                x_val = int(str(x_val).replace(".", ""))
            except (ValueError, TypeError):
                continue
        if y_field == "grind_setting":
            try:
                y_val = int(str(y_val).replace(".", ""))
            except (ValueError, TypeError):
                continue
        results.append({"x": x_val, "y": y_val})
    return results


def get_filter_options(db: Session) -> dict:
    bean_names = [
        r[0] for r in db.query(Brew.bean_name).distinct().filter(Brew.bean_name.isnot(None)).order_by(Brew.bean_name).all()
    ]
    grinders = [
        r[0] for r in db.query(Brew.grinder).distinct().filter(Brew.grinder.isnot(None)).order_by(Brew.grinder).all()
    ]
    return {"bean_names": bean_names, "grinders": grinders}


def get_distributions(db: Session, field: str) -> list[dict]:
    allowed = {"brew_method", "roaster", "roast_level", "brew_device", "bean_process", "grinder"}
    if field not in allowed:
        return []
    col = getattr(Brew, field)
    rows = (
        db.query(col.label("label"), func.count(Brew.id).label("count"))
        .filter(col.isnot(None))
        .group_by(col)
        .order_by(func.count(Brew.id).desc())
        .all()
    )
    return [{"label": r.label, "count": r.count} for r in rows]
