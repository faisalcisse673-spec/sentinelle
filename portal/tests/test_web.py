"""Tests du contrôle d'accès du portail : seuls les administrateurs entrent."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app, is_admin
from tests.conftest import session_cookie


def client(settings, service, roles=None):
    app = create_app(settings, service)
    c = TestClient(app, follow_redirects=False)
    c.__enter__()
    if roles is not None:
        c.cookies.set("sentinelle_admin", session_cookie(
            settings.session_secret,
            {"user": {"name": "Test", "username": "admin.si", "roles": roles}, "csrf": "tok"}))
    return c


def test_is_admin():
    assert is_admin({"roles": ["agent", "admin-si"]}, "admin-si")
    assert not is_admin({"roles": ["agent"]}, "admin-si")
    assert not is_admin({"roles": "admin-si"}, "admin-si")  # pas une liste : refusé
    assert not is_admin({}, "admin-si")
    assert not is_admin(None, "admin-si")


@pytest.mark.parametrize("path", ["/", "/agents", "/channels", "/audit", "/conformite"])
def test_intrus_non_authentifie_renvoye_vers_la_connexion(settings, service, path):
    r = client(settings, service).get(path)
    assert r.status_code == 307 and r.headers["location"] == "/login"


@pytest.mark.parametrize("path", ["/", "/agents", "/channels", "/audit", "/conformite"])
def test_agent_simple_recoit_un_refus(settings, service, path):
    r = client(settings, service, roles=["agent"]).get(path)
    assert r.status_code == 403
    assert "Accès refusé" in r.text


def test_admin_accede_au_tableau_de_bord(settings, service):
    r = client(settings, service, roles=["agent", "admin-si"]).get("/")
    assert r.status_code == 200 and "Tableau de bord" in r.text


def test_en_tetes_de_securite(settings, service):
    r = client(settings, service, roles=["admin-si"]).get("/")
    assert "frame-ancestors 'none'" in r.headers["content-security-policy"]
    assert r.headers["x-content-type-options"] == "nosniff"


def test_post_sans_jeton_csrf_est_refuse(settings, service):
    c = client(settings, service, roles=["admin-si"])
    r = c.post("/agents", data={"csrf": "mauvais", "username": "x.y", "full_name": "X Y",
                                "ministere": "M", "fonction": "F"})
    assert r.status_code == 403


def test_agent_simple_ne_peut_pas_enroler_ni_revoquer(settings, service):
    c = client(settings, service, roles=["agent"])
    r = c.post("/agents", data={"csrf": "tok", "username": "x.y", "full_name": "X Y",
                                "ministere": "M", "fonction": "F"})
    assert r.status_code == 403
    assert c.post("/agents/1/revoke", data={"csrf": "tok"}).status_code == 403


def test_enrolement_puis_revocation_via_le_portail(settings, service, kc, sy):
    c = client(settings, service, roles=["admin-si"])
    r = c.post("/agents", data={"csrf": "tok", "username": "awa.ouedraogo", "full_name": "Awa Ouedraogo",
                                "ministere": "MTDPCE", "fonction": "Directrice", "role": "agent"})
    assert r.status_code == 200 and "Mot de passe provisoire" in r.text
    aid = service.db.one("SELECT id FROM agents")["id"]
    r = c.post(f"/agents/{aid}/revoke", data={"csrf": "tok"})
    assert r.status_code == 200 and "Accès révoqué et vérifié" in r.text
    assert sy.accounts["@awa.ouedraogo:sentinelle.local"]["deactivated"]
