from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# Auth disabled — app is intentionally open (no login required)
# from app.auth import AuthMiddleware, router as auth_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    api_analytics,
    api_brews,
    api_data,
    api_grind_lab,
    api_ideas,
    api_import,
    api_lookups,
    api_ratings,
    api_recommendations,
    api_shelf,
    api_tiers,
    api_templates,
    pages,
)
from app.services.lookup_service import seed_lookups
from app.services.recommendation_service import seed_rules

# Import all models so Base.metadata knows about them
import app.models.inventory  # noqa: F401
import app.models.idea  # noqa: F401
import app.models.idea_screenshot  # noqa: F401
import app.models.tier_entry  # noqa: F401

# Create tables
Base.metadata.create_all(bind=engine)

# Migrate: add missing columns / drop replaced tables
from sqlalchemy import text, inspect


def _add_column(conn, table: str, column: str, col_type: str, existing: list[str]) -> None:
    """Add a column if it isn't there yet, tolerating a concurrent add.

    Gunicorn runs several workers and each one imports this module, so two of
    them can race on the same ALTER. Postgres has IF NOT EXISTS, which makes the
    statement a no-op for the loser; SQLite has no such clause, but it only runs
    single-process in development.
    """
    if column in existing:
        return
    if conn.dialect.name == "postgresql":
        conn.execute(
            text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {col_type}")
        )
    else:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


with engine.connect() as conn:
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    # Drop the old template-keyed inventory table (replaced by bean_inventory)
    if "coffee_inventory" in tables:
        conn.execute(text("DROP TABLE coffee_inventory"))
        conn.commit()

    rating_cols = [c["name"] for c in inspector.get_columns("ratings")] if "ratings" in tables else []
    if "flavor_notes_accuracy" not in rating_cols:
        conn.execute(text("ALTER TABLE ratings ADD COLUMN flavor_notes_accuracy FLOAT"))
        conn.commit()
    if "taste_score" not in rating_cols:
        conn.execute(text("ALTER TABLE ratings ADD COLUMN taste_score FLOAT"))
        conn.commit()

    # Add per-pour schedule columns to existing brews tables
    if "brews" in tables:
        brew_cols = [c["name"] for c in inspector.get_columns("brews")]
        pour_columns = {
            "bloom_pour_time_seconds": "INTEGER",
            "first_pour_grams": "INTEGER",
            "first_pour_time_seconds": "INTEGER",
            "second_pour_grams": "INTEGER",
            "second_pour_time_seconds": "INTEGER",
            "final_pour_grams": "INTEGER",
            "final_pour_time_seconds": "INTEGER",
            "pour_method": "VARCHAR(50)",
            # No DEFAULT on the booleans: Postgres rejects "DEFAULT 0" for a
            # boolean column (no implicit int -> bool cast), while SQLite accepts
            # it — so the flags are added plain and backfilled below.
            "brewed_for_friend": "BOOLEAN",
            "is_first_brew": "BOOLEAN",
            "grind_suggestion_um": "INTEGER",
        }
        for col, col_type in pour_columns.items():
            _add_column(conn, "brews", col, col_type, brew_cols)
        for col in ("brewed_for_friend", "is_first_brew"):
            conn.execute(text(f"UPDATE brews SET {col} = FALSE WHERE {col} IS NULL"))
        # Seed the micron size on brews logged before the column existed. The
        # template they were brewed from is the only record of it, so it is the
        # best estimate available; brews with no template stay blank.
        if "grind_suggestion_um" not in brew_cols and "brew_templates" in tables:
            conn.execute(text("""
                UPDATE brews SET grind_suggestion_um = (
                    SELECT t.grind_suggestion_um FROM brew_templates t
                    WHERE t.id = brews.template_id
                )
                WHERE grind_suggestion_um IS NULL AND template_id IS NOT NULL
            """))
        conn.commit()

    # Add per-pour schedule + grind suggestion columns to existing brew_templates tables
    if "brew_templates" in tables:
        tpl_cols = [c["name"] for c in inspector.get_columns("brew_templates")]
        tpl_columns = {
            "bloom_pour_time_seconds": "INTEGER",
            "first_pour_grams": "INTEGER",
            "first_pour_time_seconds": "INTEGER",
            "second_pour_grams": "INTEGER",
            "second_pour_time_seconds": "INTEGER",
            "final_pour_grams": "INTEGER",
            "final_pour_time_seconds": "INTEGER",
            "pour_method": "VARCHAR(50)",
            "grind_suggestion_um": "INTEGER",
            "product_url": "VARCHAR(500)",
            # Onyx attribute wheel
            "bean_variety": "VARCHAR(100)",
            "drying_method": "VARCHAR(100)",
            "harvest_season": "VARCHAR(100)",
            "production_roaster": "VARCHAR(100)",
            "preferred_extraction": "VARCHAR(100)",
            "caffeine_mg": "VARCHAR(50)",
            "coffee_summary": "TEXT",
        }
        for col, col_type in tpl_columns.items():
            _add_column(conn, "brew_templates", col, col_type, tpl_cols)
        conn.commit()

    # Add price column to existing bean_inventory tables
    if "bean_inventory" in tables:
        inv_cols = [c["name"] for c in inspector.get_columns("bean_inventory")]
        _add_column(conn, "bean_inventory", "price", "FLOAT", inv_cols)
        _add_column(
            conn, "bean_inventory", "used_offset_grams", "FLOAT DEFAULT 0", inv_cols
        )
        conn.commit()

    # Gate flag on ideas. Added with no DEFAULT and backfilled: Postgres rejects
    # "DEFAULT 0" on a boolean, which is what broke a deploy in 32dbda9.
    if "ideas" in tables:
        idea_cols = [c["name"] for c in inspector.get_columns("ideas")]
        _add_column(conn, "ideas", "needs_review", "BOOLEAN", idea_cols)
        conn.execute(text("UPDATE ideas SET needs_review = TRUE WHERE needs_review IS NULL"))
        conn.commit()

    # Trim stray whitespace off the bean/roaster names. Nothing joins these tables
    # by id, so a trailing space is enough to hide a template from the new-brew form
    # and to stop its brews drawing down the bag on the shelf.
    for table in ("brews", "brew_templates"):
        if table in tables:
            conn.execute(text(
                f"UPDATE {table} SET bean_name = TRIM(bean_name) "
                "WHERE bean_name IS NOT NULL AND bean_name <> TRIM(bean_name)"
            ))
            conn.execute(text(
                f"UPDATE {table} SET roaster = TRIM(roaster) "
                "WHERE roaster IS NOT NULL AND roaster <> TRIM(roaster)"
            ))
            conn.commit()

    # bean_inventory is unique on (bean_name, roaster), so trimming a row could
    # collide with one that already holds the trimmed name. Those are left alone
    # for the user to merge by hand rather than failing the deploy.
    if "bean_inventory" in tables:
        rows = conn.execute(
            text("SELECT id, bean_name, roaster FROM bean_inventory")
        ).fetchall()
        keys = {(r[1], r[2]) for r in rows}
        for inv_id, bean_name, roaster in rows:
            trimmed = (
                bean_name.strip() if bean_name else bean_name,
                roaster.strip() if roaster else roaster,
            )
            if trimmed == (bean_name, roaster) or trimmed in keys:
                continue
            conn.execute(
                text(
                    "UPDATE bean_inventory SET bean_name = :b, roaster = :r WHERE id = :i"
                ),
                {"b": trimmed[0], "r": trimmed[1], "i": inv_id},
            )
            keys.discard((bean_name, roaster))
            keys.add(trimmed)
        conn.commit()

    # Reconcile brew_devices to the current preferred set on already-seeded DBs.
    # brew.brew_device is stored as a plain string, so removing lookup rows does
    # not affect existing brews — it only changes what the dropdown offers.
    if "brew_devices" in tables:
        desired_devices = ["Flair Espresso", "Chemex", "V60 01", "V60 02", "Kalita Wave 185"]
        retired_devices = [
            "V60", "Kalita Wave", "AeroPress", "French Press", "Moka Pot",
            "Clever Dripper", "Origami", "Fellow Stagg", "Siphon",
            "Breville Barista Express",
        ]
        for name in retired_devices:
            conn.execute(text("DELETE FROM brew_devices WHERE name = :n"), {"n": name})
        for name in desired_devices:
            exists = conn.execute(
                text("SELECT 1 FROM brew_devices WHERE name = :n"), {"n": name}
            ).first()
            if not exists:
                conn.execute(text("INSERT INTO brew_devices (name) VALUES (:n)"), {"n": name})
        conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_rules(db)
        seed_lookups(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

# Auth middleware (disabled — no login required)
# app.add_middleware(AuthMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Auth routes (disabled — no login required)
# app.include_router(auth_router)

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}

# API routers
app.include_router(api_brews.router)
app.include_router(api_ratings.router)
app.include_router(api_templates.router)
app.include_router(api_analytics.router)
app.include_router(api_recommendations.router)
app.include_router(api_lookups.router)
app.include_router(api_grind_lab.router)
app.include_router(api_shelf.router)
app.include_router(api_tiers.router)
app.include_router(api_import.router)
app.include_router(api_ideas.router)
app.include_router(api_data.router)

# Page routers
app.include_router(pages.router)
