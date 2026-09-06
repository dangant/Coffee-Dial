#!/usr/bin/env python
"""Read-only fetch of the open enhancement ideas from wherever Coffee Dial stores them.

Ideas are entered on the deployed site, so they live in Railway Postgres, not the local
SQLite file. No credentials are needed: auth middleware is disabled on the deployed app
(app/main.py), so GET /api/v1/ideas is readable directly.

Screenshots attached to an idea are downloaded to disk and reported as ``local_path``, so
they can be opened with the Read tool — an idea explained by a picture is only useful if
the picture actually reaches the reader.

Sources, in order:

  1. ``IDEAS_DATABASE_URL`` / ``DATABASE_URL`` in the repo-root ``.env``, if it is Postgres.
     An explicit override — use it to point at a different deployment.
  2. HTTP against ``COFFEE_URL`` (defaults to the production app below).
  3. Local ``coffee.db``, last, and only if it actually holds ideas.

Usage:
    python fetch_ideas.py [--out DIR] [--no-images]

Read-only by construction: SELECT only, and over HTTP only GETs apart from the POST /login
that authentication would require. It never writes an idea, and never marks one done.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

# .claude/skills/review-ideas/fetch_ideas.py → repo root
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

DEFAULT_URL = "https://coffee-dial-production.up.railway.app"
EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

SETUP_HELP = f"""Couldn't reach any idea source.

The deployed app is the normal source and needs no credentials:

  COFFEE_URL={DEFAULT_URL}

If that host has moved, put the new one — or a direct Postgres URL from
Railway → Postgres → Variables → DATABASE_PUBLIC_URL — in {ROOT / '.env'} (gitignored):

  COFFEE_URL=https://your-app.up.railway.app
  DATABASE_URL=postgresql://user:pass@host.proxy.rlwy.net:PORT/railway"""


def _load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / ".env")


def _rows_via_sqlalchemy(url: str) -> list[dict]:
    """Read through the app's own ordering so this matches what the Ideas page shows."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.services import idea_service

    # Some hosts hand out "postgres://"; SQLAlchemy needs "postgresql://" (app/database.py).
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    engine = create_engine(url, connect_args=connect_args)
    session = sessionmaker(bind=engine)()
    try:
        return [_norm(i) for i in idea_service.list_ideas(session)]
    finally:
        session.close()
        engine.dispose()


def _rows_via_http(base_url: str) -> list[dict]:
    import httpx

    with httpx.Client(base_url=base_url.rstrip("/"), follow_redirects=True, timeout=30.0) as c:
        # Railway sleeps the service; /health has no DB dependency so it answers first (fb8e600).
        for attempt in range(6):
            try:
                if c.get("/health").status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(2 * (attempt + 1))
        else:
            raise SystemExit(f"Couldn't wake the app at {base_url}.")

        resp = c.get("/api/v1/ideas")
        # Auth is disabled today; if it is switched back on the API serves the login page.
        if resp.status_code in (401, 403) or "text/html" in resp.headers.get("content-type", ""):
            password = os.getenv("APP_PASSWORD")
            if not password:
                raise SystemExit(
                    "The app now requires a login. Add APP_PASSWORD to .env and retry."
                )
            login = c.post("/login", data={"password": password})
            if login.status_code == 401:
                raise SystemExit("The app rejected APP_PASSWORD.")
            login.raise_for_status()
            resp = c.get("/api/v1/ideas")

        resp.raise_for_status()
        return [_norm(i) for i in resp.json()]


def _norm_shot(shot) -> dict:
    """Screenshot metadata, carrying either raw bytes (DB) or a path to fetch (HTTP)."""
    get = shot.get if isinstance(shot, dict) else lambda k: getattr(shot, k, None)
    return {
        "id": get("id"),
        "filename": get("filename"),
        "content_type": get("content_type"),
        "width": get("width"),
        "height": get("height"),
        "url": get("url"),
        "data": get("data"),  # only from the direct-database path
    }


def _norm(idea) -> dict:
    get = idea.get if isinstance(idea, dict) else lambda k: getattr(idea, k, None)
    created = get("created_at")
    return {
        "id": get("id"),
        "title": get("title"),
        "details": get("details"),
        "is_done": bool(get("is_done")),
        # A deployment predating the gate must never read as an implement-freely grant.
        "needs_review": bool(get("needs_review")) if get("needs_review") is not None else True,
        "created_at": str(created) if created is not None else None,
        "screenshots": [_norm_shot(s) for s in (get("screenshots") or [])],
    }


def save_images(ideas: list[dict], base_url: str | None, out_dir: Path) -> int:
    """Write every attached screenshot to out_dir, recording local_path on each.

    Always strips the raw ``data`` bytes, which are not JSON serializable.
    """
    import httpx

    saved = 0
    for idea in ideas:
        for shot in idea.get("screenshots") or []:
            raw = shot.pop("data", None)
            try:
                if raw is None and shot.get("url") and base_url:
                    resp = httpx.get(base_url.rstrip("/") + shot["url"], timeout=30.0)
                    resp.raise_for_status()
                    raw = resp.content
                if not raw:
                    continue
                ext = EXTENSIONS.get(shot.get("content_type"), ".img")
                path = out_dir / f"idea{idea['id']}_shot{shot['id']}{ext}"
                path.write_bytes(raw)
                shot["local_path"] = str(path)
                saved += 1
            except Exception as e:  # one bad image shouldn't sink the review
                shot["error"] = f"could not download: {e}"
    return saved


def _strip_images(ideas: list[dict]) -> None:
    for idea in ideas:
        for shot in idea.get("screenshots") or []:
            shot.pop("data", None)


def fetch() -> dict:
    _load_env()

    db_url = os.getenv("IDEAS_DATABASE_URL") or os.getenv("DATABASE_URL") or ""
    if db_url.startswith(("postgres://", "postgresql://")):
        return {
            "source": "railway-postgres",
            "base_url": None,
            "rows": _rows_via_sqlalchemy(db_url),
        }

    coffee_url = os.getenv("COFFEE_URL") or DEFAULT_URL
    try:
        return {
            "source": coffee_url,
            "base_url": coffee_url,
            "rows": _rows_via_http(coffee_url),
        }
    except SystemExit:
        raise
    except Exception as e:
        sys.stderr.write(f"Deployed app unreachable ({e}); trying local coffee.db.\n")

    local = ROOT / "coffee.db"
    if local.exists():
        rows = _rows_via_sqlalchemy(f"sqlite:///{local.as_posix()}")
        if rows:
            return {"source": "local coffee.db", "base_url": None, "rows": rows}

    raise SystemExit(SETUP_HELP)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        default=str(Path(tempfile.gettempdir()) / "coffee-dial-ideas"),
        help="Directory for downloaded screenshots (emptied on each run).",
    )
    parser.add_argument(
        "--no-images", action="store_true", help="Skip downloading screenshots."
    )
    args = parser.parse_args()

    result = fetch()
    open_ideas = [r for r in result["rows"] if not r["is_done"]]
    for r in open_ideas:
        r.pop("is_done")

    if args.no_images:
        _strip_images(open_ideas)
        saved, out_dir = 0, None
    else:
        out_dir = Path(args.out)
        # Start clean so screenshots deleted in the app don't linger from a past run.
        shutil.rmtree(out_dir, ignore_errors=True)
        out_dir.mkdir(parents=True, exist_ok=True)
        saved = save_images(open_ideas, result.get("base_url"), out_dir)

    print(json.dumps({
        "source": result["source"],
        "open_count": len(open_ideas),
        "done_count": len(result["rows"]) - len(open_ideas),
        "screenshots_saved": saved,
        "screenshot_dir": str(out_dir) if out_dir else None,
        "ideas": open_ideas,
    }, indent=2))


if __name__ == "__main__":
    main()
