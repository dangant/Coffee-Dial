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
