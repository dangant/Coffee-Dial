def test_recommendations_high_bitterness(client):
    brew = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })
    brew_id = brew.json()["id"]
    client.post(f"/api/v1/brews/{brew_id}/rating/", json={
        "overall_score": 5.0,
        "bitterness": 4.5,
        "acidity": 2.0,
    })
    resp = client.get(f"/api/v1/brews/{brew_id}/recommendations/")
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) > 0
    suggestions = [r["suggestion"] for r in recs]
    assert any("coarser grind" in s.lower() for s in suggestions)


def test_recommendations_no_rating(client):
    brew = client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "roaster": "Onyx",
        "bean_name": "Test",
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })
    brew_id = brew.json()["id"]
    resp = client.get(f"/api/v1/brews/{brew_id}/recommendations/")
    assert resp.status_code == 404
