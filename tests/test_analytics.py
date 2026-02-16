def _create_rated_brew(client, roaster="Onyx", method="Pour Over", score=7.5):
    brew = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": roaster,
        "bean_name": "Test",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": method,
        "grind_setting": 24.0,
    })
    brew_id = brew.json()["id"]
    client.post(f"/api/v1/brews/{brew_id}/rating/", json={
        "overall_score": score,
        "bitterness": 3.0,
        "acidity": 2.5,
    })
    return brew_id


def test_summary(client):
    _create_rated_brew(client, score=8.0)
    _create_rated_brew(client, score=6.0)
    resp = client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_brews"] == 2
    assert data["average_score"] == 7.0


def test_trends(client):
    _create_rated_brew(client)
    resp = client.get("/api/v1/analytics/trends?group_by=day")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_correlations(client):
    _create_rated_brew(client)
    resp = client.get("/api/v1/analytics/correlations?x=grind_setting&y=overall_score")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["x"] == 24.0


def test_distributions(client):
    _create_rated_brew(client, method="Pour Over")
    _create_rated_brew(client, method="Espresso")
    resp = client.get("/api/v1/analytics/distributions?field=brew_method")
    data = resp.json()
    assert len(data) == 2
