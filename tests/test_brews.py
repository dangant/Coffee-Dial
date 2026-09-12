from datetime import date


def test_create_brew(client):
    resp = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx Coffee Lab",
        "bean_name": "Sagastume Family Natural",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
        "water_temp_f": 205.0,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["roaster"] == "Onyx Coffee Lab"
    assert data["water_temp_c"] is not None  # auto-converted


def test_list_brews(client):
    client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test Bean",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })
    resp = client.get("/api/v1/brews/")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_get_brew(client):
    create = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Espresso",
    })
    brew_id = create.json()["id"]
    resp = client.get(f"/api/v1/brews/{brew_id}")
    assert resp.status_code == 200
    assert resp.json()["brew_method"] == "Espresso"


def test_delete_brew(client):
    create = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })
    brew_id = create.json()["id"]
    resp = client.delete(f"/api/v1/brews/{brew_id}")
    assert resp.status_code == 204
    resp = client.get(f"/api/v1/brews/{brew_id}")
    assert resp.status_code == 404


def test_filter_brews(client):
    client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "A",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })
    client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-16",
        "roaster": "Counter Culture",
        "bean_name": "B",
        "bean_amount_grams": 20.0,
        "water_amount_ml": 350.0,
        "brew_method": "Espresso",
    })
    resp = client.get("/api/v1/brews/?roaster=Onyx")
    assert len(resp.json()) == 1
    resp = client.get("/api/v1/brews/?brew_method=Espresso")
    assert len(resp.json()) == 1


def test_filter_brews_by_bean_and_grind(client):
    client.post("/api/v1/brews/", json={
        "brew_date": "2025-02-01",
        "roaster": "Onyx",
        "bean_name": "India Ratnagiri Thermal-Shock",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
        "grind_setting": "22",
        "grinder": "Comandante C40",
    })
    client.post("/api/v1/brews/", json={
        "brew_date": "2025-02-02",
        "roaster": "Onyx",
        "bean_name": "Monarch",
        "bean_amount_grams": 20.0,
        "water_amount_ml": 350.0,
        "brew_method": "Espresso",
        "grind_setting": "4.5",
        "grinder": "Niche Zero",
    })

    # Bean filter is a substring match, like the roaster one next to it.
    resp = client.get("/api/v1/brews/?bean_name=Ratnagiri")
    assert [b["bean_name"] for b in resp.json()] == ["India Ratnagiri Thermal-Shock"]

    # One grind box searches the setting and the grinder that gives it meaning.
    resp = client.get("/api/v1/brews/?grind=Comandante")
    assert [b["bean_name"] for b in resp.json()] == ["India Ratnagiri Thermal-Shock"]
    resp = client.get("/api/v1/brews/?grind=4.5")
    assert [b["bean_name"] for b in resp.json()] == ["Monarch"]

    # Filters stack rather than replace each other.
    resp = client.get("/api/v1/brews/?bean_name=Monarch&grind=Comandante")
    assert resp.json() == []

    # The list payload carries the grind, so the CSV export and table agree.
    resp = client.get("/api/v1/brews/?bean_name=Monarch")
    assert resp.json()[0]["grinder"] == "Niche Zero"
    assert resp.json()[0]["grind_setting"] == "4.5"
