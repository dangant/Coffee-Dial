from datetime import datetime

from sqlalchemy.orm import Session

from app.models.idea import Idea
from app.schemas.idea import IdeaCreate, IdeaUpdate


def create_idea(db: Session, data: IdeaCreate) -> Idea:
    idea = Idea(**data.model_dump())
    db.add(idea)
    db.commit()
    db.refresh(idea)
    return idea


def get_idea(db: Session, idea_id: int) -> Idea | None:
    return db.query(Idea).filter(Idea.id == idea_id).first()


def list_ideas(db: Session) -> list[Idea]:
    """Open ideas first, newest first within each group."""
    return db.query(Idea).order_by(Idea.is_done, Idea.created_at.desc()).all()


def update_idea(db: Session, idea_id: int, data: IdeaUpdate) -> Idea | None:
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        return None
    values = data.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(idea, key, value)
    # completed_at follows is_done, so callers only ever send the checkbox state.
    if "is_done" in values:
        idea.completed_at = datetime.utcnow() if values["is_done"] else None
    db.commit()
    db.refresh(idea)
    return idea


def delete_idea(db: Session, idea_id: int) -> bool:
    idea = db.query(Idea).filter(Idea.id == idea_id).first()
    if not idea:
        return False
    db.delete(idea)
    db.commit()
    return True
