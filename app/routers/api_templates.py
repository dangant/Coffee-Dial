from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.template import TemplateCreate, TemplateRead, TemplateUpdate
from app.services import template_service

router = APIRouter(prefix="/api/v1/templates", tags=["templates"])


@router.post("/", response_model=TemplateRead, status_code=201)
def create_template(data: TemplateCreate, db: Session = Depends(get_db)):
    return template_service.create_template(db, data)


@router.get("/", response_model=list[TemplateRead])
def list_templates(db: Session = Depends(get_db)):
    return template_service.list_templates(db)


@router.get("/{template_id}", response_model=TemplateRead)
def get_template(template_id: int, db: Session = Depends(get_db)):
    template = template_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.put("/{template_id}", response_model=TemplateRead)
def update_template(template_id: int, data: TemplateUpdate, db: Session = Depends(get_db)):
    template = template_service.update_template(db, template_id, data)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.delete("/{template_id}", status_code=204)
def delete_template(template_id: int, db: Session = Depends(get_db)):
    if not template_service.delete_template(db, template_id):
        raise HTTPException(status_code=404, detail="Template not found")


@router.post("/from-brew/{brew_id}", response_model=TemplateRead, status_code=201)
def create_from_brew(brew_id: int, name: str, db: Session = Depends(get_db)):
    template = template_service.create_template_from_brew(db, brew_id, name)
    if not template:
        raise HTTPException(status_code=404, detail="Brew not found")
    return template
