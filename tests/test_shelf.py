"""Shelf inventory: the per-gram cost the page turns into a price per cup."""
from app.services import inventory_service


def _row(db, bean_name="Ratnagiri"):
    return next(
        r for r in inventory_service.list_shelf(db) if r["bean_name"] == bean_name
    )


def test_price_per_gram_is_computed(db):
    inventory_service.upsert_inventory(
        db, bean_name="Ratnagiri", roaster="Onyx", initial_grams=283.5, price=37.0
    )

    row = _row(db)
    assert row["price_per_gram"] == 37.0 / 283.5
    # A 25 g pour over off this bag, which is what the shelf page renders.
    assert round(row["price_per_gram"] * 25, 2) == 3.26


def test_price_per_gram_is_none_without_a_price(db):
    inventory_service.upsert_inventory(
        db, bean_name="Ratnagiri", roaster="Onyx", initial_grams=283.5, price=None
    )

    assert _row(db)["price_per_gram"] is None


def test_price_per_gram_blends_across_restocks(db):
    """Two bags at different prices average out — grams and dollars both accumulate."""
    inventory_service.restock_inventory(
        db, bean_name="Ratnagiri", roaster="Onyx", add_grams=100.0, price=20.0
    )
    inventory_service.restock_inventory(
        db, bean_name="Ratnagiri", roaster="Onyx", add_grams=100.0, price=30.0
    )

    row = _row(db)
    assert row["initial_grams"] == 200.0
    assert row["price"] == 50.0
    assert row["price_per_gram"] == 0.25


def test_untracked_beans_have_no_price_per_gram(db, client):
    """Beans seen only in brew history carry no inventory, so no cost basis."""
    resp = client.post(
        "/api/v1/brews/",
        json={
            "brew_date": "2025-01-15",
            "bean_name": "Unstocked Bean",
            "roaster": "Someone",
            "bean_amount_grams": 18.0,
            "water_amount_ml": 300.0,
            "brew_method": "Espresso",
        },
    )
    assert resp.status_code == 201

    row = _row(db, "Unstocked Bean")
    assert row["tracked"] is False
    assert row["price_per_gram"] is None


def test_shelf_api_exposes_price_per_gram(client):
    client.post(
        "/api/v1/shelf",
        json={
            "bean_name": "Ratnagiri",
            "roaster": "Onyx",
            "initial_amount_grams": 283.5,
            "price": 37.0,
        },
    )

    rows = client.get("/api/v1/shelf").json()
    assert rows[0]["price_per_gram"] == 37.0 / 283.5
