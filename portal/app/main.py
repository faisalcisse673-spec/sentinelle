"""Portail d'administration Sentinelle : accès réservé au rôle `admin-si` (Keycloak + 2FA)."""
from __future__ import annotations

import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from .config import Settings
from .db import Database
from .keycloak import KeycloakAdmin
from .service import DEMO_PASSWORD, LEVELS, ROLES, AgentService, ValidationError
from .synapse import SynapseAdmin

log = logging.getLogger("portail")
HERE = os.path.dirname(__file__)
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))


def _fmt_ts(ts: int | None) -> str:
    if not ts:
        return "-"
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%d/%m/%Y %H:%M:%S UTC")


templates.env.filters["ts"] = _fmt_ts


class AccessDenied(Exception):
    pass


def is_admin(claims: dict | None, admin_role: str) -> bool:
    """Seul un utilisateur authentifié portant le rôle d'administrateur passe."""
    if not claims:
        return False
    roles = claims.get("roles") or []
    return isinstance(roles, list) and admin_role in roles


async def _wait_ready(settings: Settings, kc: KeycloakAdmin, sy: SynapseAdmin) -> None:
    last: Exception | None = None
    for attempt in range(90):  # ~3 minutes : Keycloak met du temps à démarrer
        try:
            await kc._bearer()
            await sy.ensure_admin_token()
            return
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt % 10 == 0:
                log.info("En attente de Keycloak / Synapse... (%s)", exc)
            await asyncio.sleep(2)
    raise RuntimeError(f"Services indisponibles : {last}")


def create_app(settings: Settings | None = None, service: AgentService | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if service is None:
            os.makedirs(settings.data_dir, exist_ok=True)
            db = Database(os.path.join(settings.data_dir, "portail.db"))
            kc = KeycloakAdmin(settings.keycloak_url, settings.realm,
                               settings.kc_admin_client_id, settings.kc_admin_client_secret)
            sy = SynapseAdmin(settings.synapse_url, settings.server_name, settings.shared_secret,
                              os.path.join(settings.data_dir, "synapse_admin_token"))
            await _wait_ready(settings, kc, sy)
            app.state.service = AgentService(kc, sy, db)
            if settings.seed_demo:
                await app.state.service.seed_demo()
        else:
            app.state.service = service
        yield

    app = FastAPI(title="Sentinelle - portail d'administration", lifespan=lifespan,
                  docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(SessionMiddleware, secret_key=settings.session_secret,
                       same_site="lax", https_only=False, max_age=3600, session_cookie="sentinelle_admin")
    app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")

    oauth = OAuth()
    oauth.register(
        name="keycloak",
        client_id=settings.portal_client_id,
        client_secret=settings.portal_client_secret,
        server_metadata_url=f"{settings.keycloak_url}/realms/{settings.realm}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile"},
    )

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; frame-ancestors 'none'; form-action 'self' "
            f"{settings.keycloak_url}")
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    # ---- sécurité ------------------------------------------------------------------
    def svc(request: Request) -> AgentService:
        return request.app.state.service

    async def require_admin(request: Request) -> dict:
        claims = request.session.get("user")
        if claims is None:
            raise HTTPException(status_code=307, headers={"Location": "/login"})
        if not is_admin(claims, settings.admin_role):
            raise AccessDenied()
        return claims

    @app.exception_handler(AccessDenied)
    async def denied(request: Request, exc: AccessDenied):
        return templates.TemplateResponse(request, "denied.html", {"user": request.session.get("user")},
                                          status_code=403)

    def csrf_token(request: Request) -> str:
        if "csrf" not in request.session:
            request.session["csrf"] = secrets.token_urlsafe(24)
        return request.session["csrf"]

    def check_csrf(request: Request, token: str) -> None:
        expected = request.session.get("csrf", "")
        if not expected or not secrets.compare_digest(expected, token):
            raise HTTPException(status_code=403, detail="Jeton CSRF invalide")

    def render(request: Request, name: str, user: dict, status: int = 200, **ctx):
        ctx.update(user=user, csrf=csrf_token(request), levels=LEVELS, roles=ROLES)
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    # ---- authentification ----------------------------------------------------------
    @app.get("/login")
    async def login(request: Request):
        return await oauth.keycloak.authorize_redirect(request, f"{settings.base_url}/auth/callback")

    @app.get("/auth/callback", name="auth_callback")
    async def auth_callback(request: Request):
        try:
            token = await oauth.keycloak.authorize_access_token(request)
        except Exception:  # noqa: BLE001
            return RedirectResponse("/login")
        claims = dict(token.get("userinfo") or {})
        request.session.clear()
        request.session["user"] = {
            "name": claims.get("name") or claims.get("preferred_username", ""),
            "username": claims.get("preferred_username", ""),
            "roles": claims.get("roles", []),
        }
        return RedirectResponse("/")

    @app.get("/logout")
    async def logout(request: Request):
        request.session.clear()
        return RedirectResponse(
            f"{settings.keycloak_url}/realms/{settings.realm}/protocol/openid-connect/logout"
            f"?client_id={settings.portal_client_id}"
            f"&post_logout_redirect_uri={settings.base_url}/")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    # ---- pages ---------------------------------------------------------------------
    @app.get("/", response_class=HTMLResponse)
    async def home(request: Request, user: dict = Depends(require_admin)):
        db = svc(request).db
        stats = {
            "actifs": db.one("SELECT COUNT(*) c FROM agents WHERE status='actif'")["c"],
            "revoques": db.one("SELECT COUNT(*) c FROM agents WHERE status!='actif'")["c"],
            "canaux": db.one("SELECT COUNT(*) c FROM channels")["c"],
            "ministeres": db.one("SELECT COUNT(DISTINCT ministere) c FROM agents WHERE status='actif'")["c"],
        }
        recent = db.query("SELECT * FROM audit ORDER BY id DESC LIMIT 6")
        return render(request, "home.html", user, stats=stats, recent=recent)

    @app.get("/agents", response_class=HTMLResponse)
    async def agents(request: Request, ministere: str = "", user: dict = Depends(require_admin)):
        db = svc(request).db
        if ministere:
            rows = db.query("SELECT * FROM agents WHERE ministere=? ORDER BY ministere, full_name", (ministere,))
        else:
            rows = db.query("SELECT * FROM agents ORDER BY ministere, full_name")
        ministeres = [r["ministere"] for r in db.query("SELECT DISTINCT ministere FROM agents ORDER BY 1")]
        return render(request, "agents.html", user, agents=rows, ministeres=ministeres,
                      selected=ministere, error=None, created=None)

    @app.post("/agents", response_class=HTMLResponse)
    async def enrol(request: Request, csrf: str = Form(...), username: str = Form(...),
                    full_name: str = Form(...), ministere: str = Form(...), fonction: str = Form(...),
                    role: str = Form("agent"), user: dict = Depends(require_admin)):
        check_csrf(request, csrf)
        service_ = svc(request)
        error, created = None, None
        try:
            password = await service_.enrol(user["username"], username, full_name, ministere, fonction, role)
            created = {"username": username.strip().lower(), "password": password}
        except ValidationError as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001
            log.exception("Échec d'enrôlement")
            error = f"Échec technique : {exc}"
        rows = service_.db.query("SELECT * FROM agents ORDER BY ministere, full_name")
        ministeres = [r["ministere"] for r in service_.db.query("SELECT DISTINCT ministere FROM agents ORDER BY 1")]
        return render(request, "agents.html", user, agents=rows, ministeres=ministeres,
                      selected="", error=error, created=created, status=400 if error else 200)

    @app.get("/agents/{agent_id}/revoke", response_class=HTMLResponse)
    async def revoke_confirm(request: Request, agent_id: int, user: dict = Depends(require_admin)):
        row = svc(request).db.one("SELECT * FROM agents WHERE id=?", (agent_id,))
        if row is None:
            raise HTTPException(404)
        return render(request, "revoke.html", user, agent=row, report=None, error=None)

    @app.post("/agents/{agent_id}/revoke", response_class=HTMLResponse)
    async def revoke(request: Request, agent_id: int, csrf: str = Form(...),
                     user: dict = Depends(require_admin)):
        check_csrf(request, csrf)
        service_ = svc(request)
        row = service_.db.one("SELECT * FROM agents WHERE id=?", (agent_id,))
        if row is None:
            raise HTTPException(404)
        try:
            report = await service_.revoke(user["username"], agent_id)
            return render(request, "revoke.html", user, agent=row, report=report, error=None)
        except ValidationError as exc:
            return render(request, "revoke.html", user, agent=row, report=None, error=str(exc), status=400)

    @app.get("/channels", response_class=HTMLResponse)
    async def channels(request: Request, user: dict = Depends(require_admin)):
        db = svc(request).db
        return render(request, "channels.html", user, channels=db.query("SELECT * FROM channels ORDER BY id DESC"),
                      agents=db.query("SELECT * FROM agents WHERE status='actif' ORDER BY full_name"),
                      ministeres=[r["ministere"] for r in db.query(
                          "SELECT DISTINCT ministere FROM agents WHERE status='actif' ORDER BY 1")],
                      error=None, ok=None)

    @app.post("/channels", response_class=HTMLResponse)
    async def channels_create(request: Request, csrf: str = Form(...), name: str = Form(...),
                              level: str = Form(...), ministere: str = Form("*"), owner: str = Form(...),
                              user: dict = Depends(require_admin)):
        check_csrf(request, csrf)
        service_ = svc(request)
        error, ok = None, None
        try:
            await service_.create_channel(user["username"], name, level, ministere, owner)
            ok = "Canal créé. Les membres reçoivent une invitation dans Sentinelle."
        except ValidationError as exc:
            error = str(exc)
        except Exception as exc:  # noqa: BLE001
            log.exception("Échec de création du canal")
            error = f"Échec technique : {exc}"
        db = service_.db
        return render(request, "channels.html", user, channels=db.query("SELECT * FROM channels ORDER BY id DESC"),
                      agents=db.query("SELECT * FROM agents WHERE status='actif' ORDER BY full_name"),
                      ministeres=[r["ministere"] for r in db.query(
                          "SELECT DISTINCT ministere FROM agents WHERE status='actif' ORDER BY 1")],
                      error=error, ok=ok, status=400 if error else 200)

    @app.get("/conformite", response_class=HTMLResponse)
    async def conformite(request: Request, user: dict = Depends(require_admin)):
        return render(request, "compliance.html", user, rows=await svc(request).compliance())

    @app.get("/audit", response_class=HTMLResponse)
    async def audit(request: Request, user: dict = Depends(require_admin)):
        return render(request, "audit.html", user,
                      rows=svc(request).db.query("SELECT * FROM audit ORDER BY id DESC LIMIT 300"))

    app.state.demo_password = DEMO_PASSWORD
    return app


def app_factory() -> FastAPI:  # uvicorn --factory app.main:app_factory
    return create_app()
