"""The coffee tier board: what lands on it, and what the placements average out to."""
from app.services import tier_service


def _template(client, bean_name, method="Pour Over", roaster="Onyx Coffee Lab",
              origin=None, notes=None, name=None):
    return client.post("/api/v1/templates/", json={
        "name": name or f"{bean_name} — {method}",
        "bean_name": bean_name,
        "roaster": roaster,
        "bean_origin": origin,
        "flavor_notes_expected": notes,
        "brew_method": method,
        "bean_amount_grams": 18.0,
    })


def _brew(client, bean_name, roaster="Onyx"):
    return client.post("/api/v1/brews/", json={
        "brew_date": "2025-01-15",
        "bean_name": bean_name,
        "roaster": roaster,
        "bean_amount_grams": 18.0,
        "water_amount_ml": 300.0,
        "brew_method": "Pour Over",
    })


def _keys(rows):
    return [r["coffee_key"] for r in rows]


def test_a_coffee_with_two_templates_is_one_chip(db, client):
    """An Onyx import writes an espresso and a pour-over template for one bean —
    ranking it twice would also double its weight in the analytics."""
    _template(client, "India Ratnagiri", method="Pour Over")
    _template(client, "India Ratnagiri", method="Espresso")

    candidates = tier_service.list_candidates(db)

    assert _keys(candidates) == ["india ratnagiri"]


def test_brew_only_beans_are_rankable(db, client):
    """Coffees brewed without a template still belong on the board."""
    _brew(client, "Mexico Santuario", roaster="Wonderstate")

    assert "mexico santuario" in _keys(tier_service.list_candidates(db))


def test_placing_a_coffee_moves_it_off_the_tray(db, client):
    _template(client, "India Ratnagiri")

    tier_service.place(db, "india ratnagiri", "S")

    board = tier_service.get_board(db)
    s_row = next(r for r in board["tiers"] if r["tier"] == "S")
    assert [e["bean_name"] for e in s_row["entries"]] == ["India Ratnagiri"]
    assert "india ratnagiri" not in _keys(board["unranked"])


def test_a_coffee_can_be_moved_between_tiers(db, client):
    _template(client, "India Ratnagiri")
    tier_service.place(db, "india ratnagiri", "S")

    tier_service.place(db, "india ratnagiri", "C")

    board = tier_service.get_board(db)
    assert next(r for r in board["tiers"] if r["tier"] == "S")["entries"] == []
    assert len(next(r for r in board["tiers"] if r["tier"] == "C")["entries"]) == 1


def test_unranking_returns_a_coffee_to_the_tray(db, client):
    _template(client, "India Ratnagiri")
    tier_service.place(db, "india ratnagiri", "S")

    tier_service.place(db, "india ratnagiri", None)

    assert "india ratnagiri" in _keys(tier_service.get_board(db)["unranked"])


def test_manual_coffees_rank_like_any_other(db):
    """A coffee from before the app existed — no template, no brews."""
    tier_service.add_manual(db, {
        "bean_name": "Kenya Nyeri AA", "roaster": "Some Roaster",
        "bean_origin": "Kenya", "tier": "A",
    })

    board = tier_service.get_board(db)
    a_row = next(r for r in board["tiers"] if r["tier"] == "A")
    assert [e["bean_name"] for e in a_row["entries"]] == ["Kenya Nyeri AA"]


def test_template_edits_flow_through_to_the_board(db, client):
    """The entry stores a copy, but a linked template is the live source."""
    tpl = _template(client, "India Ratnagiri", origin="India").json()
    tier_service.place(db, "india ratnagiri", "S")

    client.put(f"/api/v1/templates/{tpl['id']}", json={"bean_origin": "India (Ratnagiri)"})

    board = tier_service.get_board(db)
    entry = next(r for r in board["tiers"] if r["tier"] == "S")["entries"][0]
    assert entry["bean_origin"] == "India (Ratnagiri)"


def test_origin_analytics_average_the_tiers(db, client):
    """Two Colombians at S and A average to 6.5 — the claim "Colombia I like"."""
    _template(client, "Colombia One", origin="Colombia", name="c1")
    _template(client, "Colombia Two", origin="Colombia", name="c2")
    tier_service.place(db, "colombia one", "S")  # 7
    tier_service.place(db, "colombia two", "A")  # 6

    rows = tier_service.tier_analytics(db, "bean_origin")

    assert rows[0]["label"] == "Colombia"
    assert rows[0]["avg_tier"] == 6.5
    assert rows[0]["count"] == 2
    assert rows[0]["thin"] is False


def test_flavor_notes_are_split_across_bars(db, client):
    _template(client, "Peachy One", notes="Peach, Chocolate", name="p1")
    tier_service.place(db, "peachy one", "S")

    labels = [r["label"] for r in tier_service.tier_analytics(db, "flavor_note")]

    assert sorted(labels) == ["Chocolate", "Peach"]


def test_single_coffee_groups_are_flagged_thin(db, client):
    """One coffee is not a preference, so the page can fade it."""
    _template(client, "Lonely Bean", origin="Peru")
    tier_service.place(db, "lonely bean", "S")

    row = tier_service.tier_analytics(db, "bean_origin")[0]
    assert row["count"] == 1 and row["thin"] is True


def test_unranked_coffees_stay_out_of_the_analytics(db, client):
    _template(client, "Unranked Bean", origin="Brazil")

    assert tier_service.tier_analytics(db, "bean_origin") == []


def test_average_maps_back_to_a_tier_letter(db, client):
    _template(client, "Bean One", origin="Kenya", name="b1")
    _template(client, "Bean Two", origin="Kenya", name="b2")
    tier_service.place(db, "bean one", "S")  # 7
    tier_service.place(db, "bean two", "B")  # 5

    row = tier_service.tier_analytics(db, "bean_origin")[0]
    assert row["avg_tier"] == 6.0
    assert row["avg_tier_letter"] == "A"


def test_board_api_and_place_endpoint(client):
    _template(client, "India Ratnagiri")

    board = client.get("/api/v1/tiers/board").json()
    assert [t["tier"] for t in board["tiers"]] == ["S", "A", "B", "C", "D", "E", "F"]

    resp = client.post("/api/v1/tiers/place",
                       json={"coffee_key": "india ratnagiri", "tier": "S"})
    assert resp.status_code == 200
    assert len(resp.json()["tiers"][0]["entries"]) == 1


def test_unknown_tier_is_rejected(client):
    _template(client, "India Ratnagiri")

    resp = client.post("/api/v1/tiers/place",
                       json={"coffee_key": "india ratnagiri", "tier": "Z"})
    assert resp.status_code == 400


def test_unknown_coffee_is_404(client):
    resp = client.post("/api/v1/tiers/place",
                       json={"coffee_key": "nope", "tier": "S"})
    assert resp.status_code == 404


def test_unknown_grouping_is_rejected(client):
    assert client.get("/api/v1/tiers/analytics?group_by=nonsense").status_code == 400
