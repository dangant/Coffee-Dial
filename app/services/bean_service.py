"""Beans as rows with ids, rather than as whatever string was typed that day.

Two earlier fixes normalized the bean name harder — trimming it on write (f3ab48a)
and merging roaster names that had drifted (59749ed) — but neither stops a new
spelling from minting a new coffee. This module owns the identity: one row per
bean, a unique key so a second spelling can't create a second row, and a merge for
the duplicates that already exist.

It deliberately mirrors :mod:`app.services.roaster_service`, which solved the same
problem for roasters, down to folding colliding shelf rows rather than failing on
the ``(bean_name, roaster)`` unique constraint.
"""
from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.bean import Bean
from app.models.brew import Brew
from app.models.inventory import BeanInventory
from app.models.template import BrewTemplate
from app.models.tier_entry import TierEntry
from app.services.naming import clean, match_key


def get_or_create(db: Session, name: str | None, roaster: str | None) -> Bean | None:
    """The one place a bean is minted. Returns None for a nameless row.

    A template with no bean is a generic recipe, not a coffee, and stays unlinked —
    the same way ``template_service.list_templates_on_shelf`` already treats it.
    """
    name, roaster = clean(name), clean(roaster)
    if not name:
        return None
    key = match_key(name, roaster)
    bean = db.query(Bean).filter(Bean.match_key == key).first()
    if bean:
        return bean
    bean = Bean(name=name, roaster=roaster, match_key=key)
    db.add(bean)
    db.flush()
    return bean


def get_bean(db: Session, bean_id: int) -> Bean | None:
    return db.query(Bean).filter(Bean.id == bean_id).first()


def list_beans(db: Session) -> list[dict]:
    """Every bean with where it is used — enough to spot a duplicate and merge it."""
    counts: dict[int, dict] = {}
    beans = db.query(Bean).order_by(Bean.roaster, Bean.name).all()
    for bean in beans:
        counts[bean.id] = {
            "id": bean.id, "name": bean.name, "roaster": bean.roaster,
            "brews": 0, "templates": 0, "tier_entries": 0, "shelf": 0, "total": 0,
        }

    for model, field in (
        (Brew, "brews"), (BrewTemplate, "templates"),
        (TierEntry, "tier_entries"), (BeanInventory, "shelf"),
    ):
        rows = (
            db.query(model.bean_id, func.count(model.id))
            .filter(model.bean_id.isnot(None))
            .group_by(model.bean_id)
            .all()
        )
        for bean_id, count in rows:
            entry = counts.get(bean_id)
            if entry is None:
                continue
            entry[field] += count
            entry["total"] += count

    return sorted(
        counts.values(),
        key=lambda b: ((b["roaster"] or "").lower(), b["name"].lower()),
    )


def _merge_inventory(db: Session, source: Bean, target: Bean) -> int:
    """Move shelf rows onto the target bean, folding any that would collide.

    bean_inventory is unique on (bean_name, roaster), so a bean stocked under both
    spellings can't simply be renamed — the two bags are the same coffee and are
    combined, exactly as roaster_service does when merging roasters.
    """
    moved = 0
    for row in db.query(BeanInventory).filter(BeanInventory.bean_id == source.id).all():
        existing = (
            db.query(BeanInventory)
            .filter(
                BeanInventory.bean_name == target.name,
                BeanInventory.roaster == target.roaster,
                BeanInventory.id != row.id,
            )
            .first()
        )
        if existing:
            existing.initial_amount_grams += row.initial_amount_grams
            if row.price is not None:
                existing.price = (existing.price or 0) + row.price
            existing.used_offset_grams = (existing.used_offset_grams or 0) + (
                row.used_offset_grams or 0
            )
            existing.bean_id = target.id
            db.delete(row)
        else:
            row.bean_id = target.id
            row.bean_name = target.name
            if target.roaster is not None:
                row.roaster = target.roaster
        moved += 1
    return moved


def _merge_tier_entries(db: Session, source: Bean, target: Bean) -> int:
    """Move tier entries, dropping any that would duplicate the target's coffee.

    tier_entries is unique on coffee_key, which tier_service derives from the bean
    name. Renaming a source entry onto the target's name would leave two rows for
    one coffee on the board, so the target's ranking wins and the source row goes.
    """
    from app.services.tier_service import coffee_key

    moved = 0
    target_key = coffee_key(target.name)
    for row in db.query(TierEntry).filter(TierEntry.bean_id == source.id).all():
        existing = (
            db.query(TierEntry)
            .filter(TierEntry.coffee_key == target_key, TierEntry.id != row.id)
            .first()
        )
        if existing:
            existing.bean_id = target.id
            db.delete(row)
        else:
            row.bean_id = target.id
            row.bean_name = target.name
            if target.roaster is not None:
                row.roaster = target.roaster
            row.coffee_key = target_key
        moved += 1
    return moved


def merge_beans(db: Session, source_id: int, target_id: int) -> dict:
    """Fold ``source`` into ``target``: repoint every row, then drop the source bean."""
    if source_id == target_id:
        raise ValueError("Those are already the same bean.")
    source = get_bean(db, source_id)
    target = get_bean(db, target_id)
    if not source or not target:
        raise ValueError("Both beans must exist.")

    # Read off what is needed before the source row is deleted below.
    was = {"id": source_id, "name": source.name, "roaster": source.roaster}

    counts = {}
    # The name columns are rewritten alongside the id so the two never disagree —
    # everything still reading by name sees the merge too.
    for model in (Brew, BrewTemplate):
        values = {model.bean_id: target.id, model.bean_name: target.name}
        # Brew.roaster is NOT NULL, so a bean with no roaster leaves the existing
        # one alone rather than blanking it.
        if target.roaster is not None:
            values[model.roaster] = target.roaster
        counts[model.__tablename__] = (
            db.query(model)
            .filter(model.bean_id == source.id)
            .update(values, synchronize_session=False)
        )
    counts["tier_entries"] = _merge_tier_entries(db, source, target)
    counts["bean_inventory"] = _merge_inventory(db, source, target)
    db.delete(source)
    db.commit()

    return {
        "source": was,
        "target": {"id": target.id, "name": target.name, "roaster": target.roaster},
        "updated": counts,
        "total": sum(counts.values()),
    }


def backfill_bean_ids(conn, tables: tuple[str, ...] | list[str], commit: bool = True) -> dict:
    """Give every existing row a bean, once, at startup.

    Idempotent: rows that already carry a bean_id are skipped, so the app can boot
    as many times as it likes. Nothing already stored is rewritten — only the new
    column is filled — which is what makes this safe to run against production and
    trivial to undo.

    Takes a raw Connection because it runs from ``app.main`` alongside the other
    inline migrations, before any session exists. Pass ``commit=False`` when the
    connection belongs to a live Session — committing it underneath would leave that
    session's transaction inactive — and commit through the session instead.
    """
    from datetime import datetime

    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError

    from app.services.naming import match_key

    # One bean per distinct normalized (name, roaster). The spelling kept is the most
    # used one — "Onyx Coffee Lab" beats a single stray "Onyx" — with the longest
    # winning a tie, since the fuller name is the more useful label.
    spellings: dict[str, dict[tuple, int]] = {}
    for table in tables:
        rows = conn.execute(text(
            f"SELECT bean_name, roaster, COUNT(*) FROM {table} "
            "WHERE bean_name IS NOT NULL AND bean_name <> '' "
            "GROUP BY bean_name, roaster"
        )).fetchall()
        for name, roaster, count in rows:
            tally = spellings.setdefault(match_key(name, roaster), {})
            pair = ((name or "").strip(), (roaster or "").strip() or None)
            tally[pair] = tally.get(pair, 0) + count

    existing = {r[0] for r in conn.execute(text("SELECT match_key FROM beans")).fetchall()}
    created = 0
    for key, tally in spellings.items():
        if key in existing:
            continue
        name, roaster = max(tally.items(), key=lambda kv: (kv[1], len(kv[0][0])))[0]
        try:
            conn.execute(
                text("INSERT INTO beans (name, roaster, match_key, created_at, updated_at) "
                     "VALUES (:n, :r, :k, :now, :now)"),
                {"n": name, "r": roaster, "k": key, "now": datetime.utcnow()},
            )
        except IntegrityError:
            # Gunicorn boots several workers and each runs this. match_key is unique,
            # so the loser of the race finds the bean already there — which is the
            # outcome it wanted anyway.
            conn.rollback()
            continue
        created += 1
    if commit:
        conn.commit()

    # Point the rows at their bean, comparing names the way every read path already
    # does: trimmed and case-folded, roaster included when there is one.
    by_key = {k: i for i, k in conn.execute(text("SELECT id, match_key FROM beans")).fetchall()}
    linked = {}
    for table in tables:
        rows = conn.execute(text(
            f"SELECT DISTINCT bean_name, roaster FROM {table} "
            "WHERE bean_name IS NOT NULL AND bean_name <> '' AND bean_id IS NULL"
        )).fetchall()
        count = 0
        for name, roaster in rows:
            bean_id = by_key.get(match_key(name, roaster))
            if not bean_id:
                continue
            clause = "roaster IS NULL" if roaster is None else "roaster = :r"
            result = conn.execute(
                text(f"UPDATE {table} SET bean_id = :b "
                     f"WHERE bean_id IS NULL AND bean_name = :n AND {clause}"),
                {"b": bean_id, "n": name, **({} if roaster is None else {"r": roaster})},
            )
            count += result.rowcount or 0
        linked[table] = count
        if commit:
            conn.commit()

    return {"beans_created": created, "rows_linked": linked}
