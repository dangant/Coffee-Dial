"""Merging roaster names that drifted apart ("Onyx" vs "Onyx Coffee Lab")."""
from app.models.inventory import BeanInventory
from app.services import inventory_service, roaster_service, tier_service


def _template(client, name, bean_name, roaster, origin=None):
    return client.post("/api/v1/templates/", json={
        "name": name, "bean_name": bean_name, "roaster": roaster,
        "bean_origin": origin, "brew_method": "Pour Over", "bean_amount_grams": 18.0,
    })


def _brew(client, bean_name, roaster):
    return client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15", "bean_name": bean_name, "roaster": roaster,
        "bean_amount_grams": 18.0, "water_amount_ml": 300.0, "brew_method": "Pour Over",
    })


def test_list_roasters_shows_where_each_name_appears(client, db):
    _template(client, "t1", "Iloma Station", "Onyx")
    _template(client, "t2", "Ratnagiri", "Onyx Coffee Lab")
    _brew(client, "Iloma Station", "Onyx")

    rows = {r["roaster"]: r for r in roaster_service.list_roasters(db)}

    assert rows["Onyx"]["templates"] == 1 and rows["Onyx"]["brews"] == 1
    assert rows["Onyx Coffee Lab"]["templates"] == 1


def test_merge_rewrites_every_table(client, db):
    _template(client, "t1", "Iloma Station", "Onyx")
    _brew(client, "Iloma Station", "Onyx")
    tier_service.add_manual(db, {"bean_name": "Old Bean", "roaster": "Onyx", "tier": "A"})
    inventory_service.upsert_inventory(
        db, bean_name="Iloma Station", roaster="Onyx", initial_grams=250.0, price=32.0
    )

    result = roaster_service.merge_roasters(db, "Onyx", "Onyx Coffee Lab")

    assert result["total"] == 4
    names = {r["roaster"] for r in roaster_service.list_roasters(db)}
    assert names == {"Onyx Coffee Lab"}


def test_merge_folds_a_bean_stocked_under_both_names(client, db):
    """bean_inventory is unique on (bean_name, roaster), so the rows are combined."""
    inventory_service.upsert_inventory(
        db, bean_name="Iloma Station", roaster="Onyx", initial_grams=100.0, price=12.0
    )
    inventory_service.upsert_inventory(
        db, bean_name="Iloma Station", roaster="Onyx Coffee Lab",
        initial_grams=150.0, price=20.0,
    )

    roaster_service.merge_roasters(db, "Onyx", "Onyx Coffee Lab")

    rows = db.query(BeanInventory).filter(BeanInventory.bean_name == "Iloma Station").all()
    assert len(rows) == 1
    assert rows[0].initial_amount_grams == 250.0
    assert rows[0].price == 32.0


def test_merge_unifies_the_tier_roaster_chart(client, db):
    """The bug that prompted this: one roaster reported as two weaker ones."""
    _template(client, "t1", "Bean One", "Onyx", origin="Colombia")
    _template(client, "t2", "Bean Two", "Onyx Coffee Lab", origin="Colombia")
    tier_service.place(db, "bean one", "S")
    tier_service.place(db, "bean two", "A")
    assert len(tier_service.tier_analytics(db, "roaster")) == 2

    roaster_service.merge_roasters(db, "Onyx", "Onyx Coffee Lab")

    rows = tier_service.tier_analytics(db, "roaster")
    assert len(rows) == 1
    assert rows[0]["label"] == "Onyx Coffee Lab"
    assert rows[0]["count"] == 2
    assert rows[0]["avg_tier"] == 6.5


def test_merging_a_roaster_into_itself_is_rejected(client):
    _template(client, "t1", "Iloma Station", "Onyx")

    resp = client.post("/api/v1/data/roasters/merge",
                       json={"source": "Onyx", "target": "Onyx"})
    assert resp.status_code == 400


def test_blank_roaster_is_rejected(client):
    resp = client.post("/api/v1/data/roasters/merge",
                       json={"source": "  ", "target": "Onyx"})
    assert resp.status_code == 400


def test_merge_endpoint_reports_what_it_touched(client, db):
    _template(client, "t1", "Iloma Station", "Onyx")
    _brew(client, "Iloma Station", "Onyx")

    resp = client.post("/api/v1/data/roasters/merge",
                       json={"source": "Onyx", "target": "Onyx Coffee Lab"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"]["brews"] == 1
    assert body["updated"]["brew_templates"] == 1
