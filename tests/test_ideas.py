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


# --- Screenshots ---------------------------------------------------------


def _png(width=40, height=30, mode="RGB", color=(200, 120, 60)):
    """A real encoded PNG, so Pillow has something genuine to decode."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new(mode, (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _upload(client, idea_id, data=None, filename="shot.png", content_type="image/png"):
    return client.post(
        f"/api/v1/ideas/{idea_id}/screenshots",
        files={"file": (filename, data if data is not None else _png(), content_type)},
    )


def test_upload_screenshot(client):
    idea = _add(client).json()

    resp = _upload(client, idea["id"])

    assert resp.status_code == 201
    shot = resp.json()
    assert shot["idea_id"] == idea["id"]
    assert (shot["width"], shot["height"]) == (40, 30)
    assert shot["byte_size"] > 0
    assert shot["url"] == f"/api/v1/ideas/screenshots/{shot['id']}"


def test_screenshot_bytes_are_served_back(client):
    idea = _add(client).json()
    shot = _upload(client, idea["id"]).json()

    resp = client.get(shot["url"])

    assert resp.status_code == 200
    assert resp.headers["content-type"] == shot["content_type"]
    assert len(resp.content) == shot["byte_size"]


def test_screenshots_ride_along_with_the_idea(client):
    """The ideas page loads everything in one GET, so images come with the idea."""
    idea = _add(client).json()
    _upload(client, idea["id"])

    listed = client.get("/api/v1/ideas").json()
    assert len(listed[0]["screenshots"]) == 1
    assert listed[0]["screenshots"][0]["filename"] == "shot.png"


def test_oversized_images_are_downscaled(client):
    idea = _add(client).json()

    shot = _upload(client, idea["id"], data=_png(3000, 1500)).json()

    assert shot["width"] == 1600
    assert shot["height"] == 800


def test_transparency_is_kept_as_png(client):
    idea = _add(client).json()

    shot = _upload(client, idea["id"], data=_png(mode="RGBA", color=(1, 2, 3, 0))).json()

    assert shot["content_type"] == "image/png"


def test_opaque_images_are_stored_as_jpeg(client):
    idea = _add(client).json()

    shot = _upload(client, idea["id"]).json()

    assert shot["content_type"] == "image/jpeg"


def test_non_image_upload_is_rejected(client):
    idea = _add(client).json()

    resp = _upload(client, idea["id"], data=b"not an image",
                   filename="notes.txt", content_type="text/plain")

    assert resp.status_code == 415


def test_bytes_that_are_not_really_an_image_are_rejected(client):
    """A truthful content-type header doesn't mean the payload decodes."""
    idea = _add(client).json()

    resp = _upload(client, idea["id"], data=b"\x89PNG not really")

    assert resp.status_code == 415


def test_screenshot_on_unknown_idea_is_404(client):
    assert _upload(client, 9999).status_code == 404


def test_deleting_an_idea_removes_its_screenshots(client, db):
    from app.models.idea_screenshot import IdeaScreenshot

    idea = _add(client).json()
    _upload(client, idea["id"])
    assert db.query(IdeaScreenshot).count() == 1

    assert client.delete(f"/api/v1/ideas/{idea['id']}").status_code == 204

    db.expire_all()
    assert db.query(IdeaScreenshot).count() == 0


def test_deleting_a_single_screenshot(client):
    idea = _add(client).json()
    shot = _upload(client, idea["id"]).json()

    assert client.delete(shot["url"]).status_code == 204
    assert client.get(shot["url"]).status_code == 404
    assert client.get("/api/v1/ideas").json()[0]["screenshots"] == []


def test_restoring_a_backup_does_not_leave_orphan_screenshots(client, db):
    """Ideas are bulk-deleted on import and restored ids are reused, so screenshots
    must go too — otherwise they would resurface attached to a different idea."""
    from app.models.idea_screenshot import IdeaScreenshot

    idea = _add(client, title="Has an image").json()
    _upload(client, idea["id"])
    dump = client.get("/api/v1/data/export").json()

    resp = client.post(
        "/api/v1/data/import",
        files={"file": ("backup.json", json.dumps(dump), "application/json")},
    )
    assert resp.status_code == 200

    db.expire_all()
    assert db.query(IdeaScreenshot).count() == 0
    assert [i["title"] for i in client.get("/api/v1/ideas").json()] == ["Has an image"]
