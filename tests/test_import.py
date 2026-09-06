"""Onyx import: size parsing and the per-bag × quantity math that stocks the shelf.

``commit_import`` makes no network calls (only ``parse_onyx`` fetches), so these run
offline against the shared db/client fixtures.
"""
import pytest

from app.models.inventory import BeanInventory
from app.services.onyx_import_service import (
    _sizes_from_js,
    _units_for_label,
    commit_import,
)


def _payload(**overrides):
    data = {
        "product_name": "India Ratnagiri Thermal-Shock",
        "bean_name": "India Ratnagiri Thermal-Shock",
        "roaster": "Onyx Coffee Lab",
        "url": "https://onyxcoffeelab.com/products/india-ratnagiri-natural",
        "flavor_notes": ["Peach"],
        "espresso": {"dose_g": 19.0, "yield_g": 40.0, "time_s": 28},
        "pour_over": {"coffee_g": 18.0, "water_g": 280.0, "steps": []},
    }
    data.update(overrides)
    return data


def _shelf_row(db, name="India Ratnagiri Thermal-Shock"):
    return db.query(BeanInventory).filter(BeanInventory.bean_name == name).first()


@pytest.mark.parametrize(
    "label,expected",
    [
        ("2oz", 1),
        ("10oz", 1),
        ("10oz Case Pack (6)", 6),
        ("5lbs Case Pack (8)", 8),
        ("12oz 4-pack", 4),
        ("12oz 4 pack", 4),
    ],
)
def test_units_for_label(label, expected):
    assert _units_for_label(label) == expected


def test_sizes_are_per_bag():
    """A case pack's Shopify price covers the whole case; grams are one bag's."""
    sizes = _sizes_from_js({
        "variants": [
            {"title": "10oz", "price": 3700},
            {"title": "10oz Case Pack (6)", "price": 22150},
        ]
    })
    single, case = sizes
    assert single == {"label": "10oz", "grams": 283.5, "price": 37.0, "units": 1}
    # 221.50 / 6 — per bag, matching the per-bag grams beside it.
    assert case == {
        "label": "10oz Case Pack (6)", "grams": 283.5, "price": 36.92, "units": 6,
    }


def test_commit_multiplies_grams_and_price_by_quantity(db):
    result = commit_import(db, _payload(grams=56.7, price=10.0, quantity=2))

    assert result["shelf"] == {
        "bean_name": "India Ratnagiri Thermal-Shock",
        "added_grams": 113.4,
        "quantity": 2,
    }
    row = _shelf_row(db)
    assert row.initial_amount_grams == 113.4
    assert row.price == 20.0


def test_commit_defaults_to_one_bag(db):
    """Quantity omitted behaves exactly as before the field existed."""
    commit_import(db, _payload(grams=56.7, price=10.0))

    row = _shelf_row(db)
    assert row.initial_amount_grams == 56.7
    assert row.price == 10.0


def test_commit_case_pack_quantity(db):
    """The 10oz case pack: 6 × 283.5 g at 6 × $36.92."""
    commit_import(db, _payload(grams=283.5, price=36.92, quantity=6))

    row = _shelf_row(db)
    assert row.initial_amount_grams == 1701.0
    assert row.price == 221.52


def test_commit_without_grams_skips_shelf(db):
    """Quantity alone shouldn't stock anything."""
    result = commit_import(db, _payload(quantity=3))

    assert result["shelf"] is None
    assert _shelf_row(db) is None
    assert len(result["templates"]) == 2


def test_api_rejects_quantity_below_one(client):
    resp = client.post(
        "/api/v1/import/onyx/commit",
        json=_payload(grams=56.7, quantity=0),
    )
    assert resp.status_code == 400
    assert "Quantity" in resp.json()["detail"]


def test_api_commit_with_quantity(client, db):
    resp = client.post(
        "/api/v1/import/onyx/commit",
        json=_payload(grams=56.7, price=10.0, quantity=2),
    )
    assert resp.status_code == 200
    assert resp.json()["shelf"]["added_grams"] == 113.4


# --- Onyx attribute wheel ------------------------------------------------


def _wheel_html(stats, abstract="A long coffee summary paragraph " * 4):
    """A cut-down copy of Onyx's wheel markup: keyed .a-stat entries plus the prose."""
    entries = "".join(
        f'<div class="a-stat" data-stat-id="{key}"><span class="stat-text"><p>'
        f'{value}<br><label>{key.upper()}</label></p></span></div>'
        for key, value in stats.items()
    )
    return (
        f'<div class="hero-intro"><div class="stage">'
        f'<div class="left-col stat-col">{entries}</div>'
        f'<div class="desktop-only"><p>{abstract}</p></div>'
        f"</div></div>"
    )


def _soup(html):
    from bs4 import BeautifulSoup

    return BeautifulSoup(html, "html.parser")


def test_wheel_stats_are_keyed_not_label_matched():
    from app.services.onyx_import_service import _wheel_stats

    stats = _wheel_stats(_soup(_wheel_html({
        "variety": "Catuai", "drying": "Raised-Bed Dried", "harvest": "December",
        "roaster": "Diedrich CR-35", "extraction": "Filter &amp; Espresso",
        "agtron": "Light Agtron #129",
    })))

    assert stats["bean_variety"] == "Catuai"
    assert stats["drying_method"] == "Raised-Bed Dried"
    assert stats["harvest_season"] == "December"
    assert stats["production_roaster"] == "Diedrich CR-35"
    assert stats["preferred_extraction"] == "Filter & Espresso"
    assert stats["roast_level"] == "Light Agtron #129"


def test_the_caption_is_not_mistaken_for_the_value():
    from app.services.onyx_import_service import _wheel_stats

    stats = _wheel_stats(_soup(_wheel_html({"variety": "Catuai"})))

    assert "VARIETY" not in (stats["bean_variety"] or "")


def test_coffee_summary_comes_from_the_centre_panel():
    from app.services.onyx_import_service import _wheel_stats

    stats = _wheel_stats(_soup(_wheel_html({"variety": "Catuai"}, abstract="x" * 200)))

    assert stats["coffee_summary"] == "x" * 200


def test_onyx_inventory_is_not_stored():
    """1289 LBS is Onyx's warehouse stock, stale the moment it is written down."""
    from app.services.onyx_import_service import _wheel_stats

    stats = _wheel_stats(_soup(_wheel_html({"inventory": "1289 LBS", "variety": "Catuai"})))

    assert "1289 LBS" not in str(stats.values())


def test_a_page_without_the_wheel_degrades_to_none():
    """A redesign must leave the import usable, not raise."""
    from app.services.onyx_import_service import _wheel_stats

    stats = _wheel_stats(_soup("<html><body><h1>Nothing here</h1></body></html>"))

    assert stats["bean_variety"] is None
    assert stats["coffee_summary"] is None


def test_attributes_land_on_both_templates():
    from app.services.onyx_import_service import build_templates

    espresso, pour_over = build_templates(_payload(
        bean_variety="Catuai", drying_method="Raised-Bed Dried",
        harvest_season="December", production_roaster="Diedrich CR-35",
        roast_level="Light Agtron #129", preferred_extraction="Filter & Espresso",
        coffee_summary="About this coffee.",
    ))

    for tpl in (espresso, pour_over):
        assert tpl.bean_variety == "Catuai"
        assert tpl.drying_method == "Raised-Bed Dried"
        assert tpl.harvest_season == "December"
        assert tpl.production_roaster == "Diedrich CR-35"
        assert tpl.roast_level == "Light Agtron #129"
        assert tpl.coffee_summary == "About this coffee."


def test_attributes_are_persisted_by_the_commit(db):
    from app.models.template import BrewTemplate
    from app.services.onyx_import_service import commit_import

    commit_import(db, _payload(bean_variety="Catuai", drying_method="Raised-Bed Dried"))

    rows = db.query(BrewTemplate).all()
    assert len(rows) == 2
    assert all(r.bean_variety == "Catuai" for r in rows)
    assert all(r.drying_method == "Raised-Bed Dried" for r in rows)


# --- Backfilling existing templates from their saved link -----------------

import pytest


@pytest.fixture
def fake_onyx(monkeypatch):
    """Stand in for the network so backfill tests are deterministic and offline."""
    from app.services import onyx_import_service

    calls = []

    def _parse(url):
        calls.append(url)
        return _payload(
            bean_origin="India", bean_process="Thermal-Shock", bean_variety="Catuai",
            drying_method="Raised-Bed Dried", harvest_season="December",
            production_roaster="Diedrich CR-35", roast_level="Light Agtron #129",
            coffee_summary="About this coffee.",
            espresso={"dose_g": 19.0, "yield_g": 40.0, "time_s": 28},
            pour_over={"coffee_g": 18.0, "water_g": 280.0, "temp_f": 202.0, "steps": []},
        )

    monkeypatch.setattr(onyx_import_service, "parse_onyx", _parse)
    return calls


URL = "https://onyxcoffeelab.com/products/india-ratnagiri-natural"


def _stored_template(client, **fields):
    body = {"name": "Ratnagiri — Pour Over", "bean_name": "India Ratnagiri",
            "brew_method": "Pour Over", "product_url": URL}
    body.update(fields)
    return client.post("/api/v1/templates/", json=body).json()


def test_backfill_fills_empty_fields(client, db, fake_onyx):
    from app.services.onyx_import_service import backfill_templates

    tpl = _stored_template(client)

    result = backfill_templates(db)

    assert result["templates_updated"] == 1
    from app.models.template import BrewTemplate
    row = db.query(BrewTemplate).filter(BrewTemplate.id == tpl["id"]).first()
    db.refresh(row)
    assert row.bean_variety == "Catuai"
    assert row.drying_method == "Raised-Bed Dried"
    assert row.roast_level == "Light Agtron #129"


def test_backfill_never_overwrites_an_existing_value(client, db, fake_onyx):
    """A field you tuned by hand stays yours."""
    from app.models.template import BrewTemplate
    from app.services.onyx_import_service import backfill_templates

    tpl = _stored_template(client, bean_variety="My own note", bean_amount_grams=21.0)

    backfill_templates(db)

    row = db.query(BrewTemplate).filter(BrewTemplate.id == tpl["id"]).first()
    db.refresh(row)
    assert row.bean_variety == "My own note"
    assert row.bean_amount_grams == 21.0


def test_backfill_matches_the_recipe_to_the_brew_method(client, db, fake_onyx):
    """An espresso template must not inherit pour-over water figures."""
    from app.models.template import BrewTemplate
    from app.services.onyx_import_service import backfill_templates

    esp = _stored_template(client, name="Ratnagiri — Espresso", brew_method="Espresso")
    pour = _stored_template(client, name="Ratnagiri — Pour Over 2", brew_method="Pour Over")

    backfill_templates(db)

    e = db.query(BrewTemplate).filter(BrewTemplate.id == esp["id"]).first()
    p = db.query(BrewTemplate).filter(BrewTemplate.id == pour["id"]).first()
    db.refresh(e); db.refresh(p)
    assert e.bean_amount_grams == 19.0  # espresso dose
    assert e.water_amount_ml is None  # espresso has no pour-over water
    assert p.bean_amount_grams == 18.0
    assert p.water_amount_ml == 280.0


def test_backfill_fetches_each_url_once(client, db, fake_onyx):
    """An Onyx import makes two templates per coffee — one fetch should serve both."""
    from app.services.onyx_import_service import backfill_templates

    _stored_template(client, name="Ratnagiri — Espresso", brew_method="Espresso")
    _stored_template(client, name="Ratnagiri — Pour Over 2")

    result = backfill_templates(db)

    assert fake_onyx == [URL]
    assert result["urls_fetched"] == 1
    assert result["templates_updated"] == 2


def test_backfill_ignores_templates_without_a_link(client, db, fake_onyx):
    from app.services.onyx_import_service import backfill_templates

    client.post("/api/v1/templates/", json={"name": "Hand-made", "brew_method": "Pour Over"})

    result = backfill_templates(db)

    assert result["templates_examined"] == 0
    assert fake_onyx == []


def test_dry_run_reports_without_writing(client, db, fake_onyx):
    from app.models.template import BrewTemplate
    from app.services.onyx_import_service import backfill_templates

    tpl = _stored_template(client)

    result = backfill_templates(db, dry_run=True)

    assert result["dry_run"] is True
    assert result["templates_updated"] == 1
    row = db.query(BrewTemplate).filter(BrewTemplate.id == tpl["id"]).first()
    db.refresh(row)
    assert row.bean_variety is None


def test_an_unreachable_page_is_reported_not_raised(client, db, monkeypatch):
    """One dead link must not sink the whole backfill."""
    from app.services import onyx_import_service
    from app.services.onyx_import_service import OnyxImportError, backfill_templates

    _stored_template(client)

    def _boom(url):
        raise OnyxImportError("Onyx returned 404 for that URL — check the link.")

    monkeypatch.setattr(onyx_import_service, "parse_onyx", _boom)

    result = backfill_templates(db)

    assert result["templates_updated"] == 0
    assert result["skipped"][0]["error"].startswith("Onyx returned 404")


def test_backfill_endpoint(client, db, fake_onyx):
    _stored_template(client)

    resp = client.post("/api/v1/import/onyx/backfill?dry_run=true")

    assert resp.status_code == 200
    assert resp.json()["templates_updated"] == 1


@pytest.mark.parametrize("raw", ["N/A", "Unknown Agtron #", "unknown", "TBD", "-", "  "])
def test_placeholder_wheel_values_are_dropped(raw):
    """A blank can still be filled in later; "Unknown" looks like an answer."""
    from app.services.onyx_import_service import _wheel_stats

    stats = _wheel_stats(_soup(_wheel_html({"harvest": raw, "agtron": raw})))

    assert stats["harvest_season"] is None
    assert stats["roast_level"] is None


def test_real_values_that_merely_look_odd_are_kept():
    from app.services.onyx_import_service import _wheel_stats

    stats = _wheel_stats(_soup(_wheel_html({"harvest": "Rotating Microlots",
                                            "agtron": "Light Agtron #130"})))

    assert stats["harvest_season"] == "Rotating Microlots"
    assert stats["roast_level"] == "Light Agtron #130"
