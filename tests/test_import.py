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
