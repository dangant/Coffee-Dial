from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import analytics_service

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)):
    return analytics_service.get_summary(db)


@router.get("/trends")
def get_trends(group_by: str = "day", db: Session = Depends(get_db)):
    return analytics_service.get_trends(db, group_by)


@router.get("/correlations")
def get_correlations(x: str = "grind_setting", y: str = "overall_score", db: Session = Depends(get_db)):
    return analytics_service.get_correlations(db, x, y)


@router.get("/distributions")
def get_distributions(field: str = "brew_method", db: Session = Depends(get_db)):
    return analytics_service.get_distributions(db, field)
