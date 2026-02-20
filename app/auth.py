from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

templates = Jinja2Templates(directory="app/templates")
serializer = URLSafeSerializer(settings.secret_key, salt="auth")

COOKIE_NAME = "coffee_session"
EXCLUDED_PREFIXES = ("/login", "/static", "/health")

router = APIRouter()


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@router.post("/login")
def login_submit(request: Request, password: str = Form(...)):
    if password == settings.app_password:
        token = serializer.dumps("authenticated")
        response = RedirectResponse(url="/", status_code=303)
        is_https = request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https"
        response.set_cookie(COOKIE_NAME, token, httponly=True, samesite="lax", secure=is_https)
        return response
    return templates.TemplateResponse(
        "login.html", {"request": request, "error": "Wrong password"}, status_code=401
    )


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in EXCLUDED_PREFIXES):
            return await call_next(request)

        cookie = request.cookies.get(COOKIE_NAME)
        if cookie:
            try:
                serializer.loads(cookie)
                return await call_next(request)
            except Exception:
                pass

        return RedirectResponse(url="/login", status_code=303)
