from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.auth import AuthMiddleware, router as auth_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    api_analytics,
    api_brews,
    api_grind_lab,
    api_lookups,
    api_ratings,
    api_recommendations,
    api_templates,
    pages,
)
from app.services.lookup_service import seed_lookups
from app.services.recommendation_service import seed_rules

# Create tables
Base.metadata.create_all(bind=engine)


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

# Auth middleware
app.add_middleware(AuthMiddleware)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Auth routes
app.include_router(auth_router)

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

# Page routers
app.include_router(pages.router)
