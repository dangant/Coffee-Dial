from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import Base, SessionLocal, engine
from app.routers import (
    api_analytics,
    api_brews,
    api_ratings,
    api_recommendations,
    api_templates,
    pages,
)
from app.services.recommendation_service import seed_rules

# Create tables
Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        seed_rules(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_title, lifespan=lifespan)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API routers
app.include_router(api_brews.router)
app.include_router(api_ratings.router)
app.include_router(api_templates.router)
app.include_router(api_analytics.router)
app.include_router(api_recommendations.router)

# Page routers
app.include_router(pages.router)
