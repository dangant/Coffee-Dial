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
        "grind_setting": 24.0,
    })
    brew_id = brew.json()["id"]
    resp = client.post(f"/api/v1/templates/from-brew/{brew_id}?name=My+Saved+Recipe")
    assert resp.status_code == 201
    data = resp.json()
    assert data["roaster"] == "Onyx"
    assert data["grind_setting"] == 24.0


def test_delete_template(client):
    create = client.post("/api/v1/templates/", json={"name": "ToDelete"})
    tid = create.json()["id"]
    resp = client.delete(f"/api/v1/templates/{tid}")
    assert resp.status_code == 204
