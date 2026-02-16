def _create_brew(client):
    resp = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })
    return resp.json()["id"]


def test_create_rating(client):
    brew_id = _create_brew(client)
    resp = client.post(f"/api/v1/brews/{brew_id}/rating/", json={
        "overall_score": 8.5,
        "bitterness": 2.0,
        "acidity": 3.0,
        "sweetness": 4.0,
    })
    assert resp.status_code == 201
    assert resp.json()["overall_score"] == 8.5


def test_duplicate_rating(client):
    brew_id = _create_brew(client)
    client.post(f"/api/v1/brews/{brew_id}/rating/", json={"overall_score": 7.0})
    resp = client.post(f"/api/v1/brews/{brew_id}/rating/", json={"overall_score": 8.0})
    assert resp.status_code == 409


def test_update_rating(client):
    brew_id = _create_brew(client)
    client.post(f"/api/v1/brews/{brew_id}/rating/", json={"overall_score": 7.0})
    resp = client.put(f"/api/v1/brews/{brew_id}/rating/", json={"overall_score": 9.0})
    assert resp.status_code == 200
    assert resp.json()["overall_score"] == 9.0


def test_delete_rating(client):
    brew_id = _create_brew(client)
    client.post(f"/api/v1/brews/{brew_id}/rating/", json={"overall_score": 7.0})
    resp = client.delete(f"/api/v1/brews/{brew_id}/rating/")
    assert resp.status_code == 204


def test_brew_cascade_deletes_rating(client):
    brew_id = _create_brew(client)
    client.post(f"/api/v1/brews/{brew_id}/rating/", json={"overall_score": 7.0})
    client.delete(f"/api/v1/brews/{brew_id}")
    resp = client.get(f"/api/v1/brews/{brew_id}/rating/")
    assert resp.status_code == 404
