from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.idea import IdeaCreate, IdeaRead, IdeaUpdate
from app.services import idea_service

router = APIRouter(prefix="/api/v1/ideas", tags=["ideas"])


@router.get("", response_model=list[IdeaRead])
def list_ideas(db: Session = Depends(get_db)):
    return idea_service.list_ideas(db)


@router.post("", response_model=IdeaRead, status_code=201)
def create_idea(data: IdeaCreate, db: Session = Depends(get_db)):
    data.title = data.title.strip()
    if not data.title:
        raise HTTPException(status_code=400, detail="An idea needs a title.")
    data.details = (data.details or "").strip() or None
    return idea_service.create_idea(db, data)


@router.put("/{idea_id}", response_model=IdeaRead)
def update_idea(idea_id: int, data: IdeaUpdate, db: Session = Depends(get_db)):
    if data.title is not None:
        data.title = data.title.strip()
        if not data.title:
            raise HTTPException(status_code=400, detail="An idea needs a title.")
    if data.details is not None:
        data.details = data.details.strip() or None
    idea = idea_service.update_idea(db, idea_id, data)
    if not idea:
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea


@router.delete("/{idea_id}", status_code=204)
def delete_idea(idea_id: int, db: Session = Depends(get_db)):
    if not idea_service.delete_idea(db, idea_id):
        raise HTTPException(status_code=404, detail="Idea not found")
