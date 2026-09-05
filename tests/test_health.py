from app.main import app


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_takes_no_db_session():
    """The browser pings /health to wake a sleeping host before it writes.

    It has to answer as soon as the worker is up, so it must not depend on the
    database — a DB call here would make the wake ping fail in exactly the
    situation it exists for.
    """
    route = next(r for r in app.routes if getattr(r, "path", None) == "/health")
    assert route.dependant.dependencies == []
