def test_dashboard(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Dashboard" in resp.text


def test_brew_list_page(client):
    resp = client.get("/brews")
    assert resp.status_code == 200
    assert "Brew History" in resp.text


def test_new_brew_page(client):
    resp = client.get("/brews/new")
    assert resp.status_code == 200
    assert "Log New Brew" in resp.text


def test_templates_page(client):
    resp = client.get("/templates")
    assert resp.status_code == 200
    assert "Brew Templates" in resp.text


def test_analytics_page(client):
    resp = client.get("/analytics")
    assert resp.status_code == 200
    assert "Analytics" in resp.text


def test_create_brew_via_form(client):
    resp = client.post("/brews/new", data={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test",
        "bean_amount_grams": "18",
        "water_amount_ml": "300",
        "brew_method": "Pour Over",
        "bloom": "off",
    }, follow_redirects=False)
    assert resp.status_code == 303
    assert "/brews/" in resp.headers["location"]


def test_brew_detail_page(client):
    # Create via API
    brew = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })
    brew_id = brew.json()["id"]
    resp = client.get(f"/brews/{brew_id}")
    assert resp.status_code == 200
    assert "Onyx" in resp.text
    assert "Rate This Brew" in resp.text
