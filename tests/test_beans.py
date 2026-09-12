"""Beans have an id, and one coffee gets exactly one of them.

The case these guard is real: a template saved "Dota " with a trailing space while the
shelf held "Dota", so the template vanished from the new-brew form and its brews stopped
drawing down the bag.
"""
from app.models.bean import Bean
from app.models.brew import Brew
from app.models.inventory import BeanInventory
from app.services import bean_service, inventory_service


def _brew(client, bean_name, roaster="George Howell", grams=18.0, day="2025-01-15"):
    resp = client.post("/api/v1/brews/", json={
        "brew_date": day,
        "roaster": roaster,
        "bean_name": bean_name,
        "bean_amount_grams": grams,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_spellings_resolve_to_one_bean(db):
    """"Dota", "Dota " and "dota" are one coffee — the George Howell case exactly."""
    first = bean_service.get_or_create(db, "Dota", "George Howell")
    assert bean_service.get_or_create(db, "Dota ", "George Howell").id == first.id
    assert bean_service.get_or_create(db, " dota", "george howell").id == first.id
    db.commit()
    assert db.query(Bean).count() == 1
    # The first spelling seen is the one kept, not the last.
    assert db.query(Bean).one().name == "Dota"


def test_a_different_coffee_is_a_different_bean(db):
    a = bean_service.get_or_create(db, "Dota", "George Howell")
    b = bean_service.get_or_create(db, "Dota Lot 3", "George Howell")
    c = bean_service.get_or_create(db, "Dota", "Onyx")
    db.commit()
    assert len({a.id, b.id, c.id}) == 3


def test_nameless_row_gets_no_bean(db):
    """A template with no bean is a generic recipe, not a coffee."""
    assert bean_service.get_or_create(db, None, "Onyx") is None
    assert bean_service.get_or_create(db, "   ", "Onyx") is None


def test_brews_are_linked_on_write(client, db):
    _brew(client, "Dota")
    _brew(client, "Dota ", day="2025-01-16")
    brews = db.query(Brew).all()
    assert len(brews) == 2
    assert brews[0].bean_id and brews[0].bean_id == brews[1].bean_id


def test_editing_the_name_moves_the_brew_to_the_right_bean(client, db):
    brew = _brew(client, "Dota")
    original = db.query(Brew).filter(Brew.id == brew["id"]).one().bean_id

    resp = client.put(f"/api/v1/brews/{brew['id']}", json={"bean_name": "Dota Lot 3"})
    assert resp.status_code == 200
    db.expire_all()
    moved = db.query(Brew).filter(Brew.id == brew["id"]).one().bean_id
    assert moved and moved != original


def test_shelf_draws_down_across_spellings(client, db):
    """A bag stocked as "Dota" is used up by brews logged as "Dota "."""
    client.post("/api/v1/shelf", json={
        "bean_name": "Dota", "roaster": "George Howell",
        "initial_amount_grams": 100.0,
    })
    _brew(client, "Dota ", grams=25.0)

    row = next(r for r in inventory_service.list_shelf(db) if r["tracked"])
    assert row["used_grams"] == 25.0
    assert row["remaining_grams"] == 75.0
    assert row["bean_id"]


def test_merge_folds_two_beans_into_one(client, db):
    """"Dota" and "Dota Lot 3" are one coffee typed two ways; merging combines the bags."""
    for name, grams in (("Dota", 100.0), ("Dota Lot 3", 250.0)):
        client.post("/api/v1/shelf", json={
            "bean_name": name, "roaster": "George Howell",
            "initial_amount_grams": grams, "price": 20.0,
        })
    _brew(client, "Dota")

    beans = {b["name"]: b for b in bean_service.list_beans(db)}
    assert beans["Dota"]["brews"] == 1 and beans["Dota"]["shelf"] == 1

    result = bean_service.merge_beans(
        db, beans["Dota"]["id"], beans["Dota Lot 3"]["id"]
    )
    assert result["target"]["name"] == "Dota Lot 3"

    db.expire_all()
    assert db.query(Bean).count() == 1
    # One shelf row, holding both bags' grams and both prices.
    rows = db.query(BeanInventory).all()
    assert len(rows) == 1
    assert rows[0].initial_amount_grams == 350.0
    assert rows[0].price == 40.0
    # The brew moved over, name and id together.
    brew = db.query(Brew).one()
    assert brew.bean_name == "Dota Lot 3"
    assert brew.bean_id == rows[0].bean_id


def test_merge_rejects_nonsense(client, db):
    bean = bean_service.get_or_create(db, "Dota", "George Howell")
    db.commit()
    for source, target in ((bean.id, bean.id), (bean.id, 9999)):
        try:
            bean_service.merge_beans(db, source, target)
        except ValueError:
            continue
        raise AssertionError(f"merging {source} into {target} should have been refused")


def test_bean_endpoints(client):
    _brew(client, "Dota")
    _brew(client, "Dota Lot 3", day="2025-01-16")

    listed = client.get("/api/v1/data/beans").json()
    assert {b["name"] for b in listed} == {"Dota", "Dota Lot 3"}

    source = next(b for b in listed if b["name"] == "Dota")
    target = next(b for b in listed if b["name"] == "Dota Lot 3")
    resp = client.post("/api/v1/data/beans/merge", json={
        "source_id": source["id"], "target_id": target["id"],
    })
    assert resp.status_code == 200
    assert resp.json()["updated"]["brews"] == 1
    assert len(client.get("/api/v1/data/beans").json()) == 1


def test_form_picks_an_existing_bean_instead_of_minting_one(client, db):
    _brew(client, "Dota")
    bean_id = db.query(Bean).one().id

    # Posting the id with a sloppy retype: the bean's own spelling wins.
    resp = client.post("/brews/new", data={
        "brew_date": "2025-02-01",
        "bean_id": str(bean_id),
        "roaster": "george howell",
        "bean_name": "dota  ",
        "bean_amount_grams": "18",
        "water_amount_ml": "300",
        "brew_method": "Pour Over",
    }, follow_redirects=False)
    assert resp.status_code == 303

    db.expire_all()
    assert db.query(Bean).count() == 1
    latest = db.query(Brew).order_by(Brew.id.desc()).first()
    assert latest.bean_name == "Dota"
    assert latest.roaster == "George Howell"
    assert latest.bean_id == bean_id


def test_form_without_an_id_mints_exactly_one_bean(client, db):
    resp = client.post("/brews/new", data={
        "brew_date": "2025-02-01",
        "bean_id": "",
        "roaster": "Onyx",
        "bean_name": "Monarch",
        "bean_amount_grams": "18",
        "water_amount_ml": "300",
        "brew_method": "Espresso",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert db.query(Bean).count() == 1


def test_new_brew_form_offers_the_picker(client):
    _brew(client, "Dota")
    page = client.get("/brews/new")
    assert page.status_code == 200
    assert 'name="bean_id"' in page.text
    assert "+ New bean" in page.text
    assert "George Howell — Dota" in page.text


def test_backfill_links_drifted_spellings_and_is_idempotent(db):
    """The startup migration: rows written before beans existed get one id between them."""
    from sqlalchemy import text

    from app.services.bean_service import backfill_bean_ids

    # Insert past-the-service, the way rows predating this feature actually look:
    # a bean_name and no bean_id.
    db.execute(text(
        "INSERT INTO brews (brew_date, roaster, bean_name, bean_amount_grams, "
        "water_amount_ml, brew_method, bloom, brewed_for_friend, is_first_brew, "
        "created_at, updated_at) VALUES "
        "('2025-01-15', 'George Howell', 'Dota ', 18, 300, 'Pour Over', 0, 0, 0, "
        "'2025-01-15 00:00:00', '2025-01-15 00:00:00'), "
        "('2025-01-16', 'George Howell', 'Dota', 18, 300, 'Pour Over', 0, 0, 0, "
        "'2025-01-16 00:00:00', '2025-01-16 00:00:00')"
    ))
    db.execute(text(
        "INSERT INTO bean_inventory (bean_name, roaster, initial_amount_grams, "
        "used_offset_grams, created_at, updated_at) VALUES "
        "('Dota', 'George Howell', 250, 0, '2025-01-15 00:00:00', '2025-01-15 00:00:00')"
    ))
    db.commit()

    tables = ("brews", "bean_inventory")
    result = backfill_bean_ids(db.connection(), tables)
    assert result["beans_created"] == 1

    db.expire_all()
    ids = {b.bean_id for b in db.query(Brew).all()}
    assert len(ids) == 1 and None not in ids
    assert db.query(BeanInventory).one().bean_id == ids.pop()

    # Booting again must not mint a second bean or move anything.
    again = backfill_bean_ids(db.connection(), tables)
    assert again["beans_created"] == 0
    assert sum(again["rows_linked"].values()) == 0
    assert db.query(Bean).count() == 1


def test_beans_are_relinked_after_restoring_a_backup(client, db):
    """An export carries names, not ids, and a restore wipes the rows the ids pointed at."""
    import json

    _brew(client, "Dota")
    _brew(client, "Dota ", day="2025-01-16")
    client.post("/api/v1/shelf", json={
        "bean_name": "Dota", "roaster": "George Howell", "initial_amount_grams": 250.0,
    })

    dump = client.get("/api/v1/data/export").json()
    resp = client.post(
        "/api/v1/data/import",
        files={"file": ("backup.json", json.dumps(dump), "application/json")},
    )
    assert resp.status_code == 200, resp.text

    db.expire_all()
    # One bean, and every restored row points at it — without waiting for a restart.
    assert db.query(Bean).count() == 1
    bean_id = db.query(Bean).one().id
    assert {b.bean_id for b in db.query(Brew).all()} == {bean_id}
    assert db.query(BeanInventory).one().bean_id == bean_id


def test_tier_entries_are_linked_when_placed(client, db):
    """The board is a fourth surface that records a coffee, and it writes rows itself."""
    from app.models.tier_entry import TierEntry

    resp = client.post("/api/v1/tiers/entries", json={
        "bean_name": "Dota", "roaster": "George Howell", "tier": "A",
    })
    assert resp.status_code in (200, 201), resp.text

    entry = db.query(TierEntry).one()
    assert entry.bean_id, "a newly placed coffee should point at its bean immediately"
    assert db.query(Bean).filter(Bean.id == entry.bean_id).one().name == "Dota"

    # And it follows a rename rather than pointing at the old coffee.
    before = entry.bean_id
    client.put(f"/api/v1/tiers/entries/{entry.id}", json={"bean_name": "Dota Lot 3"})
    db.expire_all()
    assert db.query(TierEntry).one().bean_id not in (None, before)
