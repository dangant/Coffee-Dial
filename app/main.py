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
    api_import,
    api_lookups,
    api_ratings,
    api_recommendations,
    api_shelf,
    api_templates,
    pages,
)
from app.services.lookup_service import seed_lookups
from app.services.recommendation_service import seed_rules

# Import all models so Base.metadata knows about them
import app.models.inventory  # noqa: F401

# Create tables
Base.metadata.create_all(bind=engine)

# Migrate: add missing columns / drop replaced tables
from sqlalchemy import text, inspect
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
            "brewed_for_friend": "BOOLEAN DEFAULT 0",
            "is_first_brew": "BOOLEAN DEFAULT 0",
        }
        for col, col_type in pour_columns.items():
            if col not in brew_cols:
                conn.execute(text(f"ALTER TABLE brews ADD COLUMN {col} {col_type}"))
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
        }
        for col, col_type in tpl_columns.items():
            if col not in tpl_cols:
                conn.execute(text(f"ALTER TABLE brew_templates ADD COLUMN {col} {col_type}"))
        conn.commit()

    # Add price column to existing bean_inventory tables
    if "bean_inventory" in tables:
        inv_cols = [c["name"] for c in inspector.get_columns("bean_inventory")]
        if "price" not in inv_cols:
            conn.execute(text("ALTER TABLE bean_inventory ADD COLUMN price FLOAT"))
            conn.commit()
        if "used_offset_grams" not in inv_cols:
            conn.execute(
                text("ALTER TABLE bean_inventory ADD COLUMN used_offset_grams FLOAT DEFAULT 0")
            )
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
app.include_router(api_import.router)
app.include_router(api_data.router)

# Page routers
app.include_router(pages.router)
