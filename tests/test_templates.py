def test_create_template(client):
    resp = client.post("/api/v1/templates/", json={
        "name": "Onyx Sagastume Family Natural",
        "roaster": "Onyx Coffee Lab",
        "bean_name": "Sagastume Family Natural",
        "brew_method": "Pour Over",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Onyx Sagastume Family Natural"


def test_list_templates(client):
    client.post("/api/v1/templates/", json={"name": "Template A"})
    client.post("/api/v1/templates/", json={"name": "Template B"})
    resp = client.get("/api/v1/templates/")
    assert len(resp.json()) == 2


def test_create_template_from_brew(client):
    brew = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test Bean",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
        "grind_setting": "1.3.5",
    })
    brew_id = brew.json()["id"]
    resp = client.post(f"/api/v1/templates/from-brew/{brew_id}?name=My+Saved+Recipe")
    assert resp.status_code == 201
    data = resp.json()
    assert data["roaster"] == "Onyx"
    assert data["grind_setting"] == "1.3.5"


def test_delete_template(client):
    create = client.post("/api/v1/templates/", json={"name": "ToDelete"})
    tid = create.json()["id"]
    resp = client.delete(f"/api/v1/templates/{tid}")
    assert resp.status_code == 204


def test_template_on_shelf_ignores_stray_whitespace(db, client):
    """A bean name pasted in with a trailing space still matches its bag.

    Nothing joins templates to the shelf by id, so "Dota " and "Dota" used to be
    two different beans and the template vanished from the new-brew form.
    """
    from app.services import inventory_service, template_service

    client.post("/api/v1/templates/", json={
        "name": "George Howell Dota Pour Over",
        "roaster": "George Howell",
        "bean_name": "Dota ",
    })
    inventory_service.upsert_inventory(
        db, bean_name="Dota", roaster="George Howell", initial_grams=340.0
    )

    offered = [t.name for t in template_service.list_templates_on_shelf(db)]
    assert "George Howell Dota Pour Over" in offered


def test_template_bean_name_is_trimmed_on_save(client):
    resp = client.post("/api/v1/templates/", json={
        "name": "Trimmed",
        "roaster": "  George Howell ",
        "bean_name": "Dota ",
    })
    assert resp.json()["bean_name"] == "Dota"
    assert resp.json()["roaster"] == "George Howell"


def test_brew_draws_down_a_bag_stocked_under_an_untrimmed_name(db, client):
    """Grams used matches on the trimmed name, so old rows still count."""
    from app.services import inventory_service

    inventory_service.upsert_inventory(
        db, bean_name="Dota", roaster="George Howell", initial_grams=340.0
    )
    client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "George Howell",
        "bean_name": "Dota ",
        "bean_amount_grams": 25.0,
        "water_amount_ml": 400.0,
        "brew_method": "Pour Over",
    })

    row = next(
        r for r in inventory_service.list_shelf(db) if r["bean_name"] == "Dota"
    )
    assert row["used_grams"] == 25.0
    assert row["remaining_grams"] == 315.0
    # And it is not also listed as a second, untracked bean.
    assert sum(1 for r in inventory_service.list_shelf(db) if "Dota" in r["bean_name"]) == 1
