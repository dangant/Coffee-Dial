import json


def _add(client, title="Warn me when a bag goes stale", details=None):
    return client.post("/api/v1/ideas", json={"title": title, "details": details})


def test_create_idea(client):
    resp = _add(client, details="Flag bags roasted more than 3 weeks ago")
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "Warn me when a bag goes stale"
    assert body["is_done"] is False
    assert body["completed_at"] is None


def test_blank_title_rejected(client):
    assert _add(client, title="   ").status_code == 400


def test_open_ideas_listed_before_done(client):
    first = _add(client, title="Older idea").json()
    _add(client, title="Newer idea")
    client.put(f"/api/v1/ideas/{first['id']}", json={"is_done": True})

    titles = [i["title"] for i in client.get("/api/v1/ideas").json()]
    assert titles == ["Newer idea", "Older idea"]


def test_completing_and_reopening_tracks_the_date(client):
    idea = _add(client).json()

    done = client.put(f"/api/v1/ideas/{idea['id']}", json={"is_done": True}).json()
    assert done["is_done"] is True
    assert done["completed_at"] is not None

    reopened = client.put(f"/api/v1/ideas/{idea['id']}", json={"is_done": False}).json()
    assert reopened["is_done"] is False
    assert reopened["completed_at"] is None


def test_edit_idea(client):
    idea = _add(client).json()
    resp = client.put(f"/api/v1/ideas/{idea['id']}", json={"title": "Reworded", "details": "More detail"})
    assert resp.status_code == 200
    assert resp.json()["title"] == "Reworded"
    assert resp.json()["details"] == "More detail"


def test_delete_idea(client):
    idea = _add(client).json()
    assert client.delete(f"/api/v1/ideas/{idea['id']}").status_code == 204
    assert client.get("/api/v1/ideas").json() == []
    assert client.delete(f"/api/v1/ideas/{idea['id']}").status_code == 404


def test_ideas_survive_a_backup_round_trip(client):
    idea = _add(client, details="keep me").json()
    client.put(f"/api/v1/ideas/{idea['id']}", json={"is_done": True})

    dump = client.get("/api/v1/data/export").json()
    assert len(dump["ideas"]) == 1

    resp = client.post(
        "/api/v1/data/import",
        files={"file": ("backup.json", json.dumps(dump), "application/json")},
    )
    assert resp.status_code == 200
    restored = client.get("/api/v1/ideas").json()
    assert len(restored) == 1
    assert restored[0]["details"] == "keep me"
    assert restored[0]["is_done"] is True


def test_restoring_a_pre_ideas_backup_keeps_existing_ideas(client):
    """Backups taken before this feature have no "ideas" key — importing one
    must not wipe the list."""
    _add(client, title="Do not lose me")
    old_backup = {"version": 1, "brews": [], "ratings": [], "brew_templates": []}

    resp = client.post(
        "/api/v1/data/import",
        files={"file": ("old.json", json.dumps(old_backup), "application/json")},
    )
    assert resp.status_code == 200
    assert [i["title"] for i in client.get("/api/v1/ideas").json()] == ["Do not lose me"]
