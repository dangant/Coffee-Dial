from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.brew import BrewCreate
from app.schemas.rating import RatingCreate
from app.schemas.template import TemplateCreate, TemplateUpdate
from app.services import (
    analytics_service,
    brew_service,
    lookup_service,
    rating_service,
    recommendation_service,
    template_service,
)

router = APIRouter(tags=["pages"])
templates = Jinja2Templates(directory="app/templates")


def _get_lookups(db: Session) -> dict:
    return {
        "flavor_notes": lookup_service.list_flavor_notes(db),
        "brew_devices": lookup_service.list_brew_devices(db),
        "grinders": lookup_service.list_grinders(db),
    }


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    summary = analytics_service.get_summary(db)
    recent_brews = brew_service.list_brews(db, limit=5)
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "summary": summary,
        "recent_brews": recent_brews,
    })


@router.get("/brews", response_class=HTMLResponse)
def brew_list(
    request: Request,
    roaster: str | None = None,
    brew_method: str | None = None,
    db: Session = Depends(get_db),
):
    brews = brew_service.list_brews(db, roaster=roaster, brew_method=brew_method)
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse("partials/brew_table.html", {
            "request": request, "brews": brews,
        })
    return templates.TemplateResponse("brew_list.html", {
        "request": request, "brews": brews,
        "roaster": roaster or "", "brew_method": brew_method or "",
    })


@router.get("/brews/new", response_class=HTMLResponse)
def new_brew_form(request: Request, db: Session = Depends(get_db)):
    tpl_list = template_service.list_templates(db)
    lookups = _get_lookups(db)
    return templates.TemplateResponse("brew_form.html", {
        "request": request, "templates_list": tpl_list, "brew": None, **lookups,
    })


@router.post("/brews/new")
def create_brew_form(
    request: Request,
    brew_date: str = Form(...),
    roaster: str = Form(...),
    bean_name: str = Form(...),
    bean_origin: str = Form(""),
    bean_process: str = Form(""),
    roast_date: str = Form(""),
    roast_level: str = Form(""),
    flavor_notes_expected: list[str] = Form([]),
    bean_amount_grams: float = Form(...),
    grind_setting: str = Form(""),
    grinder: str = Form(""),
    bloom: str = Form("off"),
    bloom_time_seconds: str = Form(""),
    bloom_water_ml: str = Form(""),
    water_amount_ml: float = Form(...),
    water_temp: str = Form(""),
    water_temp_unit: str = Form("F"),
    brew_method: str = Form(...),
    brew_device: str = Form(""),
    brew_time_seconds: str = Form(""),
    water_filter_type: str = Form(""),
    altitude_ft: str = Form(""),
    notes: str = Form(""),
    template_id: str = Form(""),
    db: Session = Depends(get_db),
):
    # Convert temp based on chosen unit
    temp_f = None
    temp_c = None
    if water_temp:
        temp_val = float(water_temp)
        if water_temp_unit == "C":
            temp_c = temp_val
        else:
            temp_f = temp_val

    notes_str = ", ".join(flavor_notes_expected) if flavor_notes_expected else None

    data = BrewCreate(
        brew_date=date.fromisoformat(brew_date),
        roaster=roaster,
        bean_name=bean_name,
        bean_origin=bean_origin or None,
        bean_process=bean_process or None,
        roast_date=date.fromisoformat(roast_date) if roast_date else None,
        roast_level=roast_level or None,
        flavor_notes_expected=notes_str,
        bean_amount_grams=bean_amount_grams,
        grind_setting=grind_setting or None,
        grinder=grinder or None,
        bloom=bloom == "on",
        bloom_time_seconds=int(bloom_time_seconds) if bloom_time_seconds else None,
        bloom_water_ml=float(bloom_water_ml) if bloom_water_ml else None,
        water_amount_ml=water_amount_ml,
        water_temp_f=temp_f,
        water_temp_c=temp_c,
        brew_method=brew_method,
        brew_device=brew_device or None,
        brew_time_seconds=int(brew_time_seconds) if brew_time_seconds else None,
        water_filter_type=water_filter_type or None,
        altitude_ft=int(altitude_ft) if altitude_ft else None,
        notes=notes or None,
        template_id=int(template_id) if template_id else None,
    )
    brew = brew_service.create_brew(db, data)
    return RedirectResponse(f"/brews/{brew.id}", status_code=303)


@router.get("/brews/{brew_id}", response_class=HTMLResponse)
def brew_detail(request: Request, brew_id: int, db: Session = Depends(get_db)):
    brew = brew_service.get_brew(db, brew_id)
    if not brew:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    recs = []
    if brew.rating:
        recs = recommendation_service.get_recommendations(db, brew, brew.rating)
    return templates.TemplateResponse("brew_detail.html", {
        "request": request, "brew": brew, "recommendations": recs,
    })


@router.get("/brews/{brew_id}/edit", response_class=HTMLResponse)
def edit_brew_form(request: Request, brew_id: int, db: Session = Depends(get_db)):
    brew = brew_service.get_brew(db, brew_id)
    if not brew:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    lookups = _get_lookups(db)
    return templates.TemplateResponse("brew_form.html", {
        "request": request, "brew": brew, "templates_list": None, **lookups,
    })


@router.post("/brews/{brew_id}/edit")
def update_brew_form(
    request: Request,
    brew_id: int,
    brew_date: str = Form(...),
    roaster: str = Form(...),
    bean_name: str = Form(...),
    bean_origin: str = Form(""),
    bean_process: str = Form(""),
    roast_date: str = Form(""),
    roast_level: str = Form(""),
    flavor_notes_expected: list[str] = Form([]),
    bean_amount_grams: float = Form(...),
    grind_setting: str = Form(""),
    grinder: str = Form(""),
    bloom: str = Form("off"),
    bloom_time_seconds: str = Form(""),
    bloom_water_ml: str = Form(""),
    water_amount_ml: float = Form(...),
    water_temp: str = Form(""),
    water_temp_unit: str = Form("F"),
    brew_method: str = Form(...),
    brew_device: str = Form(""),
    brew_time_seconds: str = Form(""),
    water_filter_type: str = Form(""),
    altitude_ft: str = Form(""),
    notes: str = Form(""),
    template_id: str = Form(""),
    db: Session = Depends(get_db),
):
    temp_f = None
    temp_c = None
    if water_temp:
        temp_val = float(water_temp)
        if water_temp_unit == "C":
            temp_c = temp_val
        else:
            temp_f = temp_val

    notes_str = ", ".join(flavor_notes_expected) if flavor_notes_expected else None

    data = BrewCreate(
        brew_date=date.fromisoformat(brew_date),
        roaster=roaster,
        bean_name=bean_name,
        bean_origin=bean_origin or None,
        bean_process=bean_process or None,
        roast_date=date.fromisoformat(roast_date) if roast_date else None,
        roast_level=roast_level or None,
        flavor_notes_expected=notes_str,
        bean_amount_grams=bean_amount_grams,
        grind_setting=grind_setting or None,
        grinder=grinder or None,
        bloom=bloom == "on",
        bloom_time_seconds=int(bloom_time_seconds) if bloom_time_seconds else None,
        bloom_water_ml=float(bloom_water_ml) if bloom_water_ml else None,
        water_amount_ml=water_amount_ml,
        water_temp_f=temp_f,
        water_temp_c=temp_c,
        brew_method=brew_method,
        brew_device=brew_device or None,
        brew_time_seconds=int(brew_time_seconds) if brew_time_seconds else None,
        water_filter_type=water_filter_type or None,
        altitude_ft=int(altitude_ft) if altitude_ft else None,
        notes=notes or None,
        template_id=int(template_id) if template_id else None,
    )
    brew_service.update_brew(db, brew_id, data)
    return RedirectResponse(f"/brews/{brew_id}", status_code=303)


@router.post("/brews/{brew_id}/rating")
def submit_rating(
    request: Request,
    brew_id: int,
    overall_score: float = Form(...),
    bitterness: str = Form(""),
    acidity: str = Form(""),
    sweetness: str = Form(""),
    body: str = Form(""),
    aroma: str = Form(""),
    aftertaste: str = Form(""),
    flavor_notes_experienced: str = Form(""),
    comments: str = Form(""),
    db: Session = Depends(get_db),
):
    data = RatingCreate(
        overall_score=overall_score,
        bitterness=float(bitterness) if bitterness else None,
        acidity=float(acidity) if acidity else None,
        sweetness=float(sweetness) if sweetness else None,
        body=float(body) if body else None,
        aroma=float(aroma) if aroma else None,
        aftertaste=float(aftertaste) if aftertaste else None,
        flavor_notes_experienced=flavor_notes_experienced or None,
        comments=comments or None,
    )
    existing = rating_service.get_rating(db, brew_id)
    if existing:
        rating_service.update_rating(db, brew_id, data)
    else:
        rating_service.create_rating(db, brew_id, data)
    return RedirectResponse(f"/brews/{brew_id}", status_code=303)


@router.get("/brews/{brew_id}/delete")
def delete_brew_page(brew_id: int, db: Session = Depends(get_db)):
    brew_service.delete_brew(db, brew_id)
    return RedirectResponse("/brews", status_code=303)


# Template pages
@router.get("/templates", response_class=HTMLResponse)
def template_list(request: Request, db: Session = Depends(get_db)):
    tpl_list = template_service.list_templates(db)
    return templates.TemplateResponse("template_list.html", {
        "request": request, "templates_list": tpl_list,
    })


@router.get("/templates/new", response_class=HTMLResponse)
def new_template_form(request: Request, db: Session = Depends(get_db)):
    lookups = _get_lookups(db)
    return templates.TemplateResponse("template_form.html", {
        "request": request, "template": None, **lookups,
    })


@router.post("/templates/new")
def create_template_form(
    request: Request,
    name: str = Form(...),
    roaster: str = Form(""),
    bean_name: str = Form(""),
    bean_origin: str = Form(""),
    bean_process: str = Form(""),
    roast_date: str = Form(""),
    roast_level: str = Form(""),
    flavor_notes_expected: list[str] = Form([]),
    bean_amount_grams: str = Form(""),
    grind_setting: str = Form(""),
    grinder: str = Form(""),
    bloom: str = Form("off"),
    bloom_time_seconds: str = Form(""),
    bloom_water_ml: str = Form(""),
    water_amount_ml: str = Form(""),
    water_temp: str = Form(""),
    water_temp_unit: str = Form("F"),
    brew_method: str = Form(""),
    brew_device: str = Form(""),
    brew_time_seconds: str = Form(""),
    water_filter_type: str = Form(""),
    altitude_ft: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    temp_f = None
    temp_c = None
    if water_temp:
        temp_val = float(water_temp)
        if water_temp_unit == "C":
            temp_c = temp_val
        else:
            temp_f = temp_val

    notes_str = ", ".join(flavor_notes_expected) if flavor_notes_expected else None

    data = TemplateCreate(
        name=name,
        roaster=roaster or None,
        bean_name=bean_name or None,
        bean_origin=bean_origin or None,
        bean_process=bean_process or None,
        roast_date=date.fromisoformat(roast_date) if roast_date else None,
        roast_level=roast_level or None,
        flavor_notes_expected=notes_str,
        bean_amount_grams=float(bean_amount_grams) if bean_amount_grams else None,
        grind_setting=grind_setting or None,
        grinder=grinder or None,
        bloom=bloom == "on" if bloom != "off" else None,
        bloom_time_seconds=int(bloom_time_seconds) if bloom_time_seconds else None,
        bloom_water_ml=float(bloom_water_ml) if bloom_water_ml else None,
        water_amount_ml=float(water_amount_ml) if water_amount_ml else None,
        water_temp_f=temp_f,
        water_temp_c=temp_c,
        brew_method=brew_method or None,
        brew_device=brew_device or None,
        brew_time_seconds=int(brew_time_seconds) if brew_time_seconds else None,
        water_filter_type=water_filter_type or None,
        altitude_ft=int(altitude_ft) if altitude_ft else None,
        notes=notes or None,
    )
    template_service.create_template(db, data)
    return RedirectResponse("/templates", status_code=303)


@router.get("/templates/{template_id}/edit", response_class=HTMLResponse)
def edit_template_form(request: Request, template_id: int, db: Session = Depends(get_db)):
    tpl = template_service.get_template(db, template_id)
    if not tpl:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    lookups = _get_lookups(db)
    return templates.TemplateResponse("template_form.html", {
        "request": request, "template": tpl, **lookups,
    })


@router.post("/templates/{template_id}/edit")
def update_template_form(
    request: Request,
    template_id: int,
    name: str = Form(...),
    roaster: str = Form(""),
    bean_name: str = Form(""),
    bean_origin: str = Form(""),
    bean_process: str = Form(""),
    roast_date: str = Form(""),
    roast_level: str = Form(""),
    flavor_notes_expected: list[str] = Form([]),
    bean_amount_grams: str = Form(""),
    grind_setting: str = Form(""),
    grinder: str = Form(""),
    bloom: str = Form("off"),
    bloom_time_seconds: str = Form(""),
    bloom_water_ml: str = Form(""),
    water_amount_ml: str = Form(""),
    water_temp: str = Form(""),
    water_temp_unit: str = Form("F"),
    brew_method: str = Form(""),
    brew_device: str = Form(""),
    brew_time_seconds: str = Form(""),
    water_filter_type: str = Form(""),
    altitude_ft: str = Form(""),
    notes: str = Form(""),
    db: Session = Depends(get_db),
):
    temp_f = None
    temp_c = None
    if water_temp:
        temp_val = float(water_temp)
        if water_temp_unit == "C":
            temp_c = temp_val
        else:
            temp_f = temp_val

    notes_str = ", ".join(flavor_notes_expected) if flavor_notes_expected else None

    data = TemplateUpdate(
        name=name,
        roaster=roaster or None,
        bean_name=bean_name or None,
        bean_origin=bean_origin or None,
        bean_process=bean_process or None,
        roast_date=date.fromisoformat(roast_date) if roast_date else None,
        roast_level=roast_level or None,
        flavor_notes_expected=notes_str,
        bean_amount_grams=float(bean_amount_grams) if bean_amount_grams else None,
        grind_setting=grind_setting or None,
        grinder=grinder or None,
        bloom=bloom == "on" if bloom != "off" else None,
        bloom_time_seconds=int(bloom_time_seconds) if bloom_time_seconds else None,
        bloom_water_ml=float(bloom_water_ml) if bloom_water_ml else None,
        water_amount_ml=float(water_amount_ml) if water_amount_ml else None,
        water_temp_f=temp_f,
        water_temp_c=temp_c,
        brew_method=brew_method or None,
        brew_device=brew_device or None,
        brew_time_seconds=int(brew_time_seconds) if brew_time_seconds else None,
        water_filter_type=water_filter_type or None,
        altitude_ft=int(altitude_ft) if altitude_ft else None,
        notes=notes or None,
    )
    template_service.update_template(db, template_id, data)
    return RedirectResponse("/templates", status_code=303)


@router.get("/templates/{template_id}/delete")
def delete_template_page(template_id: int, db: Session = Depends(get_db)):
    template_service.delete_template(db, template_id)
    return RedirectResponse("/templates", status_code=303)


@router.post("/brews/{brew_id}/save-template")
def save_brew_as_template(
    brew_id: int,
    name: str = Form(...),
    db: Session = Depends(get_db),
):
    template_service.create_template_from_brew(db, brew_id, name)
    return RedirectResponse(f"/brews/{brew_id}", status_code=303)


# Analytics page
@router.get("/analytics", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    summary = analytics_service.get_summary(db)
    return templates.TemplateResponse("analytics.html", {
        "request": request, "summary": summary,
    })


# Grind Lab page
@router.get("/grind-lab", response_class=HTMLResponse)
def grind_lab_page(request: Request):
    return templates.TemplateResponse("grind_lab.html", {"request": request})
