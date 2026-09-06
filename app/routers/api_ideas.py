from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.idea import IdeaCreate, IdeaRead, IdeaScreenshotRead, IdeaUpdate
from app.services import idea_screenshot_service, idea_service
from app.services.idea_screenshot_service import ScreenshotError

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


# Screenshots. The two-segment "screenshots/{id}" paths can't collide with the
# single-segment "/{idea_id}" routes above, so ordering doesn't matter here.


@router.post(
    "/{idea_id}/screenshots", response_model=IdeaScreenshotRead, status_code=201
)
async def upload_screenshot(
    idea_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)
):
    if not idea_service.get_idea(db, idea_id):
        raise HTTPException(status_code=404, detail="Idea not found")
    try:
        return idea_screenshot_service.add_screenshot(
            db,
            idea_id=idea_id,
            filename=file.filename or "screenshot",
            content_type=file.content_type or "",
            raw=await file.read(),
        )
    except ScreenshotError as e:
        raise HTTPException(status_code=e.status, detail=str(e))


@router.get("/{idea_id}/screenshots", response_model=list[IdeaScreenshotRead])
def list_screenshots(idea_id: int, db: Session = Depends(get_db)):
    if not idea_service.get_idea(db, idea_id):
        raise HTTPException(status_code=404, detail="Idea not found")
    return idea_screenshot_service.list_screenshots(db, idea_id)


@router.get("/screenshots/{screenshot_id}")
def read_screenshot(screenshot_id: int, db: Session = Depends(get_db)):
    shot = idea_screenshot_service.get_screenshot(db, screenshot_id)
    if not shot:
        raise HTTPException(status_code=404, detail="Screenshot not found")
    # Stored bytes never change in place, so let the browser keep them.
    return Response(
        content=shot.data,
        media_type=shot.content_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@router.delete("/screenshots/{screenshot_id}", status_code=204)
def delete_screenshot(screenshot_id: int, db: Session = Depends(get_db)):
    if not idea_screenshot_service.delete_screenshot(db, screenshot_id):
        raise HTTPException(status_code=404, detail="Screenshot not found")
