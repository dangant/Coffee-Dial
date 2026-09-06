"""The coffee tier board, and what the placements say about your taste.

The board ranks coffees. Everything you have a template for, everything you have brewed,
and anything you type in by hand shows up once, and the analytics turn those placements
into claims: this origin lands high, that note doesn't.
"""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.brew import Brew
from app.models.template import BrewTemplate
from app.models.tier_entry import TIER_SCORES, TIERS, TierEntry


def coffee_key(bean_name: str | None) -> str:
    return (bean_name or "").strip().lower()


def _split_notes(notes: str | None) -> list[str]:
    return [n.strip() for n in (notes or "").split(",") if n.strip()]


def _resolved(entry: TierEntry, templates: dict[int, BrewTemplate]) -> dict:
    """Entry attributes, preferring the linked template so edits there flow through."""
    tpl = templates.get(entry.template_id) if entry.template_id else None
    pick = lambda field: (getattr(tpl, field, None) if tpl else None) or getattr(entry, field)
    return {
        "id": entry.id,
        "coffee_key": entry.coffee_key,
        "bean_name": pick("bean_name"),
        "roaster": pick("roaster"),
        "bean_origin": pick("bean_origin"),
        "bean_process": pick("bean_process"),
        "flavor_notes": (tpl.flavor_notes_expected if tpl else None) or entry.flavor_notes,
        "template_id": entry.template_id,
        "source": entry.source,
        "tier": entry.tier,
        "position": entry.position,
        "notes": entry.notes,
    }


def _templates_by_id(db: Session) -> dict[int, BrewTemplate]:
    return {t.id: t for t in db.query(BrewTemplate).all()}


def list_candidates(db: Session) -> list[dict]:
    """Coffees worth ranking that aren't on the board yet.

    Templates first (they carry origin, process and tasting notes), then beans that only
    appear in brew history. Deduped on the bean name, so a coffee with both an espresso
    and a pour-over template is one candidate, not two.
    """
    placed = {e.coffee_key for e in db.query(TierEntry.coffee_key).all()}
    seen: dict[str, dict] = {}

    for t in db.query(BrewTemplate).order_by(BrewTemplate.id).all():
        key = coffee_key(t.bean_name)
        if not key or key in placed or key in seen:
            continue
        seen[key] = {
            "coffee_key": key,
            "bean_name": t.bean_name,
            "roaster": t.roaster,
            "bean_origin": t.bean_origin,
            "bean_process": t.bean_process,
            "flavor_notes": t.flavor_notes_expected,
            "template_id": t.id,
            "source": "template",
        }

    brewed = db.query(Brew.bean_name, Brew.roaster).distinct().all()
    for bean_name, roaster in brewed:
        key = coffee_key(bean_name)
        if not key or key in placed or key in seen:
            continue
        seen[key] = {
            "coffee_key": key,
            "bean_name": bean_name,
            "roaster": roaster,
            "bean_origin": None,
            "bean_process": None,
            "flavor_notes": None,
            "template_id": None,
            "source": "brew",
        }

    return sorted(seen.values(), key=lambda c: (c["bean_name"] or "").lower())


def get_board(db: Session) -> dict:
    templates = _templates_by_id(db)
    entries = [
        _resolved(e, templates)
        for e in db.query(TierEntry).order_by(TierEntry.position, TierEntry.id).all()
    ]

    by_tier = {tier: [] for tier in TIERS}
    unplaced = []
    for e in entries:
        (by_tier[e["tier"]] if e["tier"] in by_tier else unplaced).append(e)

    return {
        "tiers": [{"tier": tier, "entries": by_tier[tier]} for tier in TIERS],
        # Entries with no tier sit alongside coffees never added to the board at all.
        "unranked": unplaced + list_candidates(db),
    }


def _entry_for_key(db: Session, key: str) -> TierEntry | None:
    return db.query(TierEntry).filter(TierEntry.coffee_key == key).first()


def place(db: Session, key: str, tier: str | None, position: int = 0) -> TierEntry | None:
    """Move a coffee to a tier, creating its entry the first time it's dragged out."""
    if tier is not None and tier not in TIERS:
        raise ValueError(f"Unknown tier: {tier}")

    entry = _entry_for_key(db, key)
    if not entry:
        candidate = next((c for c in list_candidates(db) if c["coffee_key"] == key), None)
        if not candidate:
            return None
        entry = TierEntry(**candidate)
        db.add(entry)

    entry.tier = tier
    entry.position = position
    db.commit()
    db.refresh(entry)
    return entry


def add_manual(db: Session, data: dict) -> TierEntry:
    """A coffee that predates the app — no template, no brews, still rankable."""
    key = coffee_key(data.get("bean_name"))
    existing = _entry_for_key(db, key)
    if existing:
        return existing

    entry = TierEntry(
        coffee_key=key,
        bean_name=(data.get("bean_name") or "").strip(),
        roaster=(data.get("roaster") or "").strip() or None,
        bean_origin=(data.get("bean_origin") or "").strip() or None,
        bean_process=(data.get("bean_process") or "").strip() or None,
        flavor_notes=(data.get("flavor_notes") or "").strip() or None,
        notes=(data.get("notes") or "").strip() or None,
        tier=data.get("tier"),
        source="manual",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def update_entry(db: Session, entry_id: int, data: dict) -> TierEntry | None:
    entry = db.query(TierEntry).filter(TierEntry.id == entry_id).first()
    if not entry:
        return None
    for field in (
        "tier", "position", "notes", "bean_name", "roaster",
        "bean_origin", "bean_process", "flavor_notes",
    ):
        if field in data and data[field] is not None:
            setattr(entry, field, data[field])
    if "bean_name" in data and data["bean_name"]:
        entry.coffee_key = coffee_key(data["bean_name"])
    db.commit()
    db.refresh(entry)
    return entry


def delete_entry(db: Session, entry_id: int) -> bool:
    entry = db.query(TierEntry).filter(TierEntry.id == entry_id).first()
    if not entry:
        return False
    db.delete(entry)
    db.commit()
    return True


def _score_to_letter(score: float) -> str:
    """Nearest tier letter for an average, so a 6.5 reads as A rather than a number."""
    return min(TIERS, key=lambda t: abs(TIER_SCORES[t] - score))


def tier_analytics(db: Session, group_by: str) -> list[dict]:
    """Average tier per flavor note / origin / roaster — the "what do I actually like" view.

    Averages, not counts: five Colombians ranked C says something very different from two
    ranked S, and a count-based chart can't tell them apart. Groups backed by a single
    coffee are returned but flagged ``thin`` — one data point isn't a preference.
    """
    if group_by not in ("flavor_note", "bean_origin", "roaster"):
        raise ValueError(f"Unknown grouping: {group_by}")

    templates = _templates_by_id(db)
    ranked = [
        _resolved(e, templates)
        for e in db.query(TierEntry).filter(TierEntry.tier.isnot(None)).all()
        if e.tier in TIER_SCORES
    ]

    buckets: dict[str, list[dict]] = defaultdict(list)
    for entry in ranked:
        if group_by == "flavor_note":
            labels = _split_notes(entry["flavor_notes"])
        else:
            value = entry["bean_origin"] if group_by == "bean_origin" else entry["roaster"]
            labels = [value.strip()] if value and value.strip() else []
        for label in labels:
            buckets[label].append(entry)

    out = []
    for label, entries in buckets.items():
        scores = [TIER_SCORES[e["tier"]] for e in entries]
        avg = sum(scores) / len(scores)
        out.append({
            "label": label,
            "avg_tier": round(avg, 2),
            "avg_tier_letter": _score_to_letter(avg),
            "count": len(entries),
            "thin": len(entries) < 2,
            "coffees": [
                {"bean_name": e["bean_name"], "tier": e["tier"]}
                for e in sorted(entries, key=lambda e: TIER_SCORES[e["tier"]], reverse=True)
            ],
        })

    # Best first, and a well-evidenced group outranks a lone coffee on the same average.
    return sorted(out, key=lambda r: (-r["avg_tier"], r["thin"], r["label"].lower()))
