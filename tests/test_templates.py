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


def test_unlisted_process_and_roast_survive_the_forms(client):
    """Onyx states "Thermal-Shock" and "Light Agtron #129"; neither is on a fixed list.

    Both fields used to render as a <select>. A stored value matching no option showed
    as blank and was written back as blank on the next save, so editing a template
    quietly erased what the import had fetched.
    """
    created = client.post("/api/v1/templates/", json={
        "name": "India Ratnagiri Thermal-Shock — Pour Over",
        "roaster": "Onyx",
        "bean_name": "India Ratnagiri Thermal-Shock",
        "bean_process": "Thermal-Shock",
        "roast_level": "Light Agtron #129",
        "brew_method": "Pour Over",
    })
    assert created.status_code == 201, created.text
    template_id = created.json()["id"]

    # The edit form shows both values instead of an empty dropdown.
    page = client.get(f"/templates/{template_id}/edit")
    assert page.status_code == 200
    assert "Thermal-Shock" in page.text
    assert "Light Agtron #129" in page.text

    # And the brew form offers them as free text, so a loaded template can assign them.
    form = client.get("/brews/new")
    assert 'name="bean_process"' in form.text
    assert 'list="process-options"' in form.text
    assert 'name="roast_level"' in form.text
    assert 'list="roast-options"' in form.text
    assert "<select name=\"bean_process\"" not in form.text
    assert "<select name=\"roast_level\"" not in form.text


def test_template_read_exposes_its_bean_id(client):
    """The brew form needs it to preselect the bean picker when a template loads."""
    created = client.post("/api/v1/templates/", json={
        "name": "Ratnagiri Espresso",
        "roaster": "Onyx",
        "bean_name": "India Ratnagiri Thermal-Shock",
        "brew_method": "Espresso",
    })
    template_id = created.json()["id"]
    read = client.get(f"/api/v1/templates/{template_id}").json()
    assert read["bean_id"]


def test_prefill_fills_template_gaps_from_last_brew(client):
    """Dialing in iterates: a new brew picks up where the last one from this template left off."""
    tid = client.post("/api/v1/templates/", json={
        "name": "JBC Blueberry", "roaster": "JBC", "bean_name": "Blueberry",
        "brew_method": "Pour Over", "bean_amount_grams": 20.0, "water_temp_c": 94.0,
    }).json()["id"]
    base = {"roaster": "JBC", "bean_name": "Blueberry", "brew_method": "Pour Over",
            "bean_amount_grams": 20.0, "water_amount_ml": 318.0, "template_id": tid}
    client.post("/api/v1/brews/", json={**base, "brew_date": "2026-10-01", "grind_setting": "2.5.0"})
    client.post("/api/v1/brews/", json={
        **base, "brew_date": "2026-10-06", "grind_setting": "2.5.7",
        "bean_amount_grams": 18.0, "water_temp_f": 205.0, "notes": "a bit sour",
    })

    data = client.get(f"/api/v1/templates/{tid}/prefill").json()
    assert data["grind_setting"] == "2.5.7"       # gap filled from the latest brew
    assert data["water_amount_ml"] == 318.0
    assert data["bean_amount_grams"] == 20.0      # the template's own value wins
    assert data["water_temp_c"] == 94.0
    assert data["water_temp_f"] is None           # template temp isn't overridden in another unit
    assert data["notes"] is None                  # one cup's notes aren't the recipe


def test_prefill_without_brews_is_just_the_template(client):
    tid = client.post("/api/v1/templates/", json={"name": "Fresh"}).json()["id"]
    data = client.get(f"/api/v1/templates/{tid}/prefill").json()
    assert data["name"] == "Fresh"
    assert data["grind_setting"] is None
    assert client.get("/api/v1/templates/9999/prefill").status_code == 404
