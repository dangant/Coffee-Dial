def _create_rated_brew(client, roaster="Onyx", method="Pour Over", score=7.5, taste=None, bean="Test",
                       brewed_for_friend=False, is_first_brew=False):
    brew = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": roaster,
        "bean_name": bean,
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": method,
        "water_temp_f": 205.0,
        "brewed_for_friend": brewed_for_friend,
        "is_first_brew": is_first_brew,
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


def test_flagged_brews_excluded_from_summary(client):
    _create_rated_brew(client, score=8.0)
    _create_rated_brew(client, score=2.0, brewed_for_friend=True)
    _create_rated_brew(client, score=2.0, is_first_brew=True)

    data = client.get("/api/v1/analytics/summary").json()
    # All three are brews (the beans were used); only the unflagged one is scored.
    assert data["total_brews"] == 3
    assert data["excluded_brews"] == 2
    assert data["average_score"] == 8.0

    included = client.get("/api/v1/analytics/summary?include_excluded=true").json()
    assert included["average_score"] == 4.0


def test_flagged_brews_excluded_from_charts(client):
    _create_rated_brew(client, score=8.0)
    _create_rated_brew(client, score=2.0, brewed_for_friend=True)

    corr = client.get("/api/v1/analytics/correlations?x=bean_amount_grams&y=overall_score").json()
    assert len(corr) == 1
    corr_all = client.get(
        "/api/v1/analytics/correlations?x=bean_amount_grams&y=overall_score&include_excluded=true"
    ).json()
    assert len(corr_all) == 2

    trends = client.get("/api/v1/analytics/trends?group_by=day").json()
    assert trends[0]["avg_score"] == 8.0
    trends_all = client.get("/api/v1/analytics/trends?group_by=day&include_excluded=true").json()
    assert trends_all[0]["avg_score"] == 5.0


def test_flagged_brew_still_deducts_from_shelf(client):
    client.post("/api/v1/shelf", json={
        "bean_name": "Test", "roaster": "Onyx", "initial_amount_grams": 100.0,
    })
    _create_rated_brew(client, score=8.0)
    _create_rated_brew(client, score=2.0, brewed_for_friend=True)

    row = next(r for r in client.get("/api/v1/shelf").json() if r["bean_name"] == "Test")
    assert row["remaining_grams"] == 64.0  # both 18g brews came off the bag
