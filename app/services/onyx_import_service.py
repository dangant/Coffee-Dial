"""Import coffee data from an Onyx Coffee Lab product page.

Onyx runs on Shopify and server-renders product data, so we can fetch two sources
with no browser/JS and no API token:

  * ``{url}.js``  — Shopify product JSON: title, vendor (roaster), tags
                     (origin/process), and variants (bag sizes + price in cents).
  * ``{url}``     — HTML: tasting notes (``p.tasting-notes span.note``) and the
                     espresso / pour-over recipes (``.guide-text`` blocks plus
                     ``li.kapra.step`` pour steps carrying data-time / data-weight).

This parser is intentionally specific to Onyx's current theme. If they redesign the
site the selectors below may stop matching; every field is best-effort and returns
None/empty rather than raising, so a partial parse still produces an editable preview.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.schemas.template import TemplateCreate
from app.services import inventory_service, lookup_service, template_service

ALLOWED_HOST = "onyxcoffeelab.com"
ROASTER = "Onyx Coffee Lab"
# Onyx is behind Cloudflare, which 403s bot-shaped User-Agents. Send ordinary
# browser headers so the same public pages a customer can open also load here.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
_GRAMS_PER_OZ = 28.3495
_GRAMS_PER_LB = 453.592


class OnyxImportError(Exception):
    """Raised when the URL is not importable (bad host, network error, not found)."""


def _normalize(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise OnyxImportError("Enter a full Onyx product URL, e.g. https://onyxcoffeelab.com/products/…")
    host = parsed.netloc.lower().split(":")[0]
    if host != ALLOWED_HOST and not host.endswith("." + ALLOWED_HOST):
        raise OnyxImportError(f"That link isn't an {ALLOWED_HOST} product URL.")
    if "/products/" not in parsed.path:
        raise OnyxImportError("That doesn't look like an Onyx product page (expected /products/…).")
    # Drop query/fragment for a clean base URL.
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def _fetch(url: str) -> httpx.Response:
    try:
        resp = httpx.get(url, headers=_HEADERS, follow_redirects=True, timeout=15.0)
        resp.raise_for_status()
        return resp
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise OnyxImportError("Onyx returned 404 for that URL — check the link.") from e
        raise OnyxImportError(f"Onyx returned HTTP {e.response.status_code}.") from e
    except httpx.HTTPError as e:
        raise OnyxImportError(f"Couldn't reach Onyx: {e}") from e


def _grams_for_label(label: str) -> float | None:
    m = re.search(r"([\d.]+)\s*(oz|lb|lbs|g)\b", label, re.I)
    if not m:
        return None
    qty, unit = float(m.group(1)), m.group(2).lower()
    if unit == "oz":
        return round(qty * _GRAMS_PER_OZ, 1)
    if unit in ("lb", "lbs"):
        return round(qty * _GRAMS_PER_LB, 1)
    return round(qty, 1)


def _units_for_label(label: str) -> int:
    """Bags per variant. Onyx sells case packs as "10oz Case Pack (6)"."""
    m = re.search(r"\((\d+)\)|(\d+)\s*-?\s*pack\b", label, re.I)
    if not m:
        return 1
    count = int(m.group(1) or m.group(2))
    return count if count > 0 else 1


def _sizes_from_js(js: dict) -> list[dict]:
    """Sizes normalized to a single bag: grams and price are both per-bag.

    ``_grams_for_label`` already reads the leading "10oz" of a case-pack label, but
    Shopify's price covers the whole case — divide it by the pack count so the two
    numbers describe the same thing and quantity is the only multiplier.
    """
    sizes = []
    for v in js.get("variants") or []:
        label = (v.get("title") or v.get("option1") or "").strip()
        if not label:
            continue
        units = _units_for_label(label)
        sizes.append({
            "label": label,
            "grams": _grams_for_label(label),
            "price": round((v.get("price") or 0) / 100.0 / units, 2),
            "units": units,
        })
    return sizes


def _tag_value(tags: list[str], prefix: str) -> str | None:
    vals = [t.split(":", 1)[1].strip() for t in tags if t.lower().startswith(prefix)]
    # De-dupe while preserving order.
    seen, out = set(), []
    for v in vals:
        if v.lower() not in seen:
            seen.add(v.lower())
            out.append(v)
    return ", ".join(out) or None


def _num(pattern: str, text: str, group: int = 1, cast=float):
    m = re.search(pattern, text, re.I)
    if not m:
        return None
    try:
        return cast(m.group(group))
    except (ValueError, IndexError):
        return None


def _parse_pour_over(guide_text: str, steps: list[dict], html: str) -> dict:
    grind = _num(r"grind-size-calculator\?um=(\d+)", html, cast=int)
    if grind is None:
        grind = _num(r"(\d+)\s*[µu]m", guide_text, cast=int)
    device = None
    m = re.search(r"Overview\s+(.+?)\s+Coffee:", guide_text, re.I | re.S)
    if m:
        device = re.sub(r"\s+", " ", m.group(1)).strip() or None
    return {
        "coffee_g": _num(r"Coffee:\s*([\d.]+)\s*g", guide_text),
        "water_g": _num(r"Water:\s*([\d.]+)\s*g", guide_text),
        "temp_f": _num(r"Water:[^@]*@\s*([\d.]+)", guide_text),
        "grind_um": grind,
        "device": device,
        "steps": steps,
    }


# Onyx's product page draws an "attribute wheel" whose entries carry a stable
# data-stat-id, so the values are keyed rather than matched on their visible labels.
# "inventory" is deliberately absent: it is Onyx's warehouse stock on the day of the
# import, not a property of the bag, and it is stale the moment it is stored.
_WHEEL_FIELDS = {
    "variety": "bean_variety",
    "drying": "drying_method",
    "harvest": "harvest_season",
    "roaster": "production_roaster",
    "extraction": "preferred_extraction",
    "agtron": "roast_level",
    "caffeine": "caffeine_mg",
}


def _wheel_stats(soup: BeautifulSoup) -> dict:
    """Read the attribute wheel into template fields, best-effort like everything here."""
    out = {field: None for field in _WHEEL_FIELDS.values()}
    for stat in soup.select("div.stat-col .a-stat"):
        field = _WHEEL_FIELDS.get(stat.get("data-stat-id") or "")
        if not field:
            continue
        para = stat.find("p")
        if not para:
            continue
        # The <label> is the caption ("VARIETY"); the value is the text beside it.
        label = para.find("label")
        if label:
            label.extract()
        value = re.sub(r"\s+", " ", para.get_text(" ", strip=True)).strip()
        out[field] = value or None

    # The wheel's abstract entry only reads "Coffee Summary" — the prose is in the
    # centre panel, so it needs its own selector.
    paragraphs = [
        re.sub(r"\s+", " ", p.get_text(" ", strip=True))
        for p in soup.select(".hero-intro .desktop-only p")
    ]
    long_form = [p for p in paragraphs if len(p) > 80]
    out["coffee_summary"] = max(long_form, key=len) if long_form else None
    return out


def _parse_espresso(guide_text: str) -> dict:
    return {
        "dose_g": _num(r"Coffee:\s*([\d.]+)\s*g", guide_text),
        "yield_g": _num(r"Yield:\s*([\d.]+)\s*g", guide_text),
        "time_s": _num(r"Bar:\s*(\d+)\s*s", guide_text, cast=int)
        or _num(r"(\d+)\s*s\b", guide_text, cast=int),
    }


def parse_onyx(url: str) -> dict:
    """Fetch and parse an Onyx product page into a structured, best-effort dict."""
    base = _normalize(url)

    # Structured basics from the Shopify product JSON.
    try:
        js = _fetch(base + ".js").json()
    except (ValueError, OnyxImportError):
        js = {}
    tags = js.get("tags") or []

    soup = BeautifulSoup(_fetch(base).text, "html.parser")

    notes = [s.get_text(strip=True) for s in soup.select("p.tasting-notes span.note")]
    notes = [n for n in notes if n]

    steps = []
    for li in soup.select("li.kapra.step"):
        w = li.get("data-weight") or ""
        steps.append({
            "time_s": int(li["data-time"]) if li.get("data-time", "").isdigit() else None,
            "weight_g": int(w) if w.isdigit() else None,
            "action": (li.get("data-action") or "").strip(),
        })

    # Classify the two recipe blocks by their contents.
    pour_over, espresso = {}, {}
    for block in soup.select(".guide-text"):
        text = re.sub(r"\s+", " ", block.get_text(" ", strip=True))
        if "Yield" in text and "Water" not in text:
            espresso = _parse_espresso(text)
        elif "Water" in text or "Grind" in text:
            # Scope grind lookup to this block so a page-wide grind link can't win.
            pour_over = _parse_pour_over(text, steps, str(block))
    if steps and not pour_over:
        pour_over = _parse_pour_over("", steps, str(soup))

    name = (js.get("title") or "").strip()
    if not name:
        h1 = soup.select_one("h1")
        name = h1.get_text(strip=True) if h1 else ""

    return {
        "url": base,
        "product_name": name,
        "roaster": (js.get("vendor") or ROASTER).strip(),
        "bean_origin": _tag_value(tags, "origin:"),
        "bean_process": _tag_value(tags, "process:"),
        "flavor_notes": notes,
        "sizes": _sizes_from_js(js),
        "espresso": espresso,
        "pour_over": pour_over,
        **_wheel_stats(soup),
    }


def _recipe_text_pour_over(po: dict) -> str:
    lines = ["Onyx pour-over recipe:"]
    if po.get("device"):
        lines.append(f"Device: {po['device']}")
    parts = []
    if po.get("coffee_g"):
        parts.append(f"{po['coffee_g']:g}g coffee")
    if po.get("water_g"):
        parts.append(f"{po['water_g']:g}g water")
    if po.get("temp_f"):
        parts.append(f"{po['temp_f']:g}°F")
    if po.get("grind_um"):
        parts.append(f"{po['grind_um']}µm")
    if parts:
        lines.append(" · ".join(parts))
    for s in po.get("steps") or []:
        t = s.get("time_s")
        mmss = f"{t // 60}:{t % 60:02d}" if isinstance(t, int) else "?"
        weight = f"{s['weight_g']}g" if s.get("weight_g") else ""
        lines.append(f"  {mmss}  {s.get('action', '')} {weight}".rstrip())
    return "\n".join(lines)


def _recipe_text_espresso(esp: dict) -> str:
    parts = []
    if esp.get("dose_g"):
        parts.append(f"{esp['dose_g']:g}g in")
    if esp.get("yield_g"):
        parts.append(f"{esp['yield_g']:g}g out")
    if esp.get("dose_g") and esp.get("yield_g"):
        parts.append(f"1:{esp['yield_g'] / esp['dose_g']:.1f}")
    if esp.get("time_s"):
        parts.append(f"{esp['time_s']}s @ 9 bar")
    return "Onyx espresso recipe: " + " · ".join(parts) if parts else ""


def _pour_slots(steps: list[dict]) -> dict:
    """Map Onyx's bloom + N pours onto the template's bloom + 3-pour slots."""
    bloom = next((s for s in steps if "bloom" in s.get("action", "").lower()), None)
    pours = [
        s for s in steps
        if s is not bloom and s.get("weight_g") and "drain" not in s.get("action", "").lower()
    ]
    out = {}
    if bloom:
        out["bloom"] = True
        out["bloom_water_ml"] = float(bloom["weight_g"]) if bloom.get("weight_g") else None
        out["bloom_pour_time_seconds"] = bloom.get("time_s")
    if len(pours) >= 1:
        out["first_pour_grams"] = pours[0].get("weight_g")
        out["first_pour_time_seconds"] = pours[0].get("time_s")
    if len(pours) >= 3:
        out["second_pour_grams"] = pours[1].get("weight_g")
        out["second_pour_time_seconds"] = pours[1].get("time_s")
    if len(pours) >= 2:
        out["final_pour_grams"] = pours[-1].get("weight_g")
        out["final_pour_time_seconds"] = pours[-1].get("time_s")
    drain = next((s for s in steps if "drain" in s.get("action", "").lower()), None)
    if drain and drain.get("time_s"):
        out["brew_time_seconds"] = drain["time_s"]
    elif pours:
        out["brew_time_seconds"] = pours[-1].get("time_s")
    return out


def _product_url(url: str | None) -> str | None:
    """Re-validate the product URL before it is stored and later rendered as a link."""
    if not url or not url.strip():
        return None
    return _normalize(url)


def build_templates(data: dict) -> tuple[TemplateCreate, TemplateCreate]:
    """Build (espresso, pour_over) TemplateCreate payloads from an edited import dict."""
    name = (data.get("product_name") or "Onyx Coffee").strip()
    roaster = (data.get("roaster") or ROASTER).strip()
    bean_name = (data.get("bean_name") or name).strip()
    notes = data.get("flavor_notes") or []
    notes_str = ", ".join(n.strip() for n in notes if n and n.strip()) or None
    shared = dict(
        roaster=roaster,
        bean_name=bean_name,
        bean_origin=data.get("bean_origin") or None,
        bean_process=data.get("bean_process") or None,
        flavor_notes_expected=notes_str,
        product_url=_product_url(data.get("url")),
        # The attribute wheel describes the coffee, so both recipes carry it.
        **{field: data.get(field) or None for field in _WHEEL_FIELDS.values()},
        coffee_summary=data.get("coffee_summary") or None,
    )

    esp = data.get("espresso") or {}
    esp_notes = _recipe_text_espresso(esp)
    espresso = TemplateCreate(
        name=f"{name} — Espresso (Onyx)",
        brew_method="Espresso",
        brew_device="Flair Espresso",
        bean_amount_grams=esp.get("dose_g"),
        brew_time_seconds=esp.get("time_s"),
        notes=esp_notes or None,
        **shared,
    )

    po = data.get("pour_over") or {}
    slots = _pour_slots(po.get("steps") or [])
    pour_over = TemplateCreate(
        name=f"{name} — Pour Over (Onyx)",
        brew_method="Pour Over",
        brew_device=po.get("device_mapped") or "Kalita Wave 185",
        bean_amount_grams=po.get("coffee_g"),
        water_amount_ml=po.get("water_g"),
        water_temp_f=po.get("temp_f"),
        grind_suggestion_um=po.get("grind_um"),
        notes=_recipe_text_pour_over(po) or None,
        **slots,
        **shared,
    )
    return espresso, pour_over


def _unique_name(db: Session, name: str) -> str:
    from app.models.template import BrewTemplate

    candidate, n = name, 1
    while db.query(BrewTemplate).filter(BrewTemplate.name == candidate).first():
        n += 1
        candidate = f"{name} ({n})"
    return candidate


def commit_import(db: Session, data: dict) -> dict:
    """Create both templates, register flavor notes, and stock the shelf. Returns a summary."""
    espresso, pour_over = build_templates(data)

    for note in data.get("flavor_notes") or []:
        if note and note.strip():
            lookup_service.add_flavor_note(db, note.strip())

    created = []
    for tpl in (espresso, pour_over):
        tpl.name = _unique_name(db, tpl.name)
        row = template_service.create_template(db, tpl)
        created.append({"id": row.id, "name": row.name})

    shelf = None
    grams = data.get("grams")
    if grams and float(grams) > 0:
        # grams/price arrive per bag; quantity is how many bags were bought.
        quantity = int(data.get("quantity") or 1)
        price = data.get("price")
        total_grams = round(float(grams) * quantity, 2)
        total_price = round(float(price) * quantity, 2) if price not in (None, "") else None
        inv = inventory_service.restock_inventory(
            db,
            bean_name=(data.get("bean_name") or data.get("product_name") or "").strip(),
            roaster=(data.get("roaster") or ROASTER).strip(),
            add_grams=total_grams,
            price=total_price,
        )
        shelf = {
            "bean_name": inv.bean_name,
            "added_grams": total_grams,
            "quantity": quantity,
        }

    return {"templates": created, "shelf": shelf}
