def _create_rated_brew(client, roaster="Onyx", method="Pour Over", score=7.5, taste=None, bean="Test"):
    brew = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": roaster,
        "bean_name": bean,
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": method,
        "water_temp_f": 205.0,
    })
    brew_id = brew.json()["id"]
    payload = {"overall_score": score, "bitterness": 3.0, "acidity": 2.5}
    if taste is not None:
        payload["taste_score"] = taste
    client.post(f"/api/v1/brews/{brew_id}/rating/", json=payload)
    return brew_id


def test_summary(client):
    _create_rated_brew(client, score=8.0)
    _create_rated_brew(client, score=6.0)
    resp = client.get("/api/v1/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_brews"] == 2
    assert data["average_score"] == 7.0


def test_summary_taste(client):
    # Nepal enjoyed most (taste 9), Iloma best executed (exec 9, no taste).
    _create_rated_brew(client, bean="Nepal", score=6.0, taste=9.0)
    _create_rated_brew(client, bean="Iloma", score=9.0)
    data = client.get("/api/v1/analytics/summary").json()
    assert data["average_taste_score"] == 9.0
    assert data["most_enjoyed_bean"]["name"] == "Onyx — Nepal"
    assert data["highest_rated_bean"]["name"] == "Onyx — Iloma"


def test_trends(client):
    _create_rated_brew(client)
    resp = client.get("/api/v1/analytics/trends?group_by=day")
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


def test_correlations(client):
    _create_rated_brew(client)
    resp = client.get("/api/v1/analytics/correlations?x=water_temp_f&y=overall_score")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["x"] == 205.0


def test_distributions(client):
    _create_rated_brew(client, method="Pour Over")
    _create_rated_brew(client, method="Espresso")
    resp = client.get("/api/v1/analytics/distributions?field=brew_method")
    data = resp.json()
    assert len(data) == 2
