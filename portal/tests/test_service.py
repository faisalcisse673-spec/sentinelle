"""Tests des fonctions de sécurité : enrôlement, révocation, canaux classifiés."""
import pytest

from app.service import LEVELS, ValidationError


async def enrol(service, username="awa.ouedraogo", ministere="MTDPCE", role="agent"):
    return await service.enrol("admin.si", username, "Awa Ouedraogo", ministere, "Directrice", role)


# ---- enrôlement ---------------------------------------------------------------------
async def test_enrol_cree_compte_keycloak_et_matrix_lies(service, kc, sy):
    password = await enrol(service)
    assert len(password) >= 12
    assert kc.users["kc-awa.ouedraogo"]["temporary"] is True  # mot de passe provisoire
    assert sy.accounts["@awa.ouedraogo:sentinelle.local"]["kc"] == "kc-awa.ouedraogo"
    row = service.db.one("SELECT * FROM agents WHERE username='awa.ouedraogo'")
    assert row["status"] == "actif" and row["role"] == "agent"
    assert service.db.one("SELECT action FROM audit")["action"] == "enrolement"


@pytest.mark.parametrize("bad", ["", "AB", "Awa Ouedraogo", "1abc", "a" * 40, "x;drop", "é.nom"])
async def test_enrol_refuse_identifiant_invalide(service, bad):
    with pytest.raises(ValidationError):
        await service.enrol("admin.si", bad, "Nom Prenom", "MTDPCE", "Chef", "agent")


async def test_enrol_refuse_role_inconnu_et_doublon(service):
    with pytest.raises(ValidationError):
        await enrol(service, role="superuser")
    await enrol(service)
    with pytest.raises(ValidationError):
        await enrol(service)


async def test_enrol_annule_le_compte_keycloak_si_matrix_echoue(service, kc, sy):
    sy.fail_provision = True
    with pytest.raises(RuntimeError):
        await enrol(service)
    assert kc.users == {}  # pas de compte orphelin
    assert service.db.one("SELECT 1 FROM agents") is None


# ---- révocation ---------------------------------------------------------------------
async def test_revocation_complete_et_verifiee(service, kc, sy):
    await enrol(service)
    agent = service.db.one("SELECT id FROM agents")
    report = await service.revoke("admin.si", agent["id"])
    assert report.complete
    assert [s.ok for s in report.steps] == [True] * 4
    assert kc.users["kc-awa.ouedraogo"]["enabled"] is False
    acc = sy.accounts["@awa.ouedraogo:sentinelle.local"]
    assert acc["deactivated"] and acc["devices"] == [] and acc["rooms"] == []
    assert service.db.one("SELECT status FROM agents")["status"] == "revoque"


async def test_revocation_coupe_keycloak_avant_matrix(service, kc, sy):
    await enrol(service)
    aid = service.db.one("SELECT id FROM agents")["id"]
    await service.revoke("admin.si", aid)
    order = [c for c in kc.calls + sy.calls if c.startswith(("disable", "deactivate"))]
    # l'agent ne peut plus se réauthentifier avant même la coupure côté Matrix
    assert order[0].startswith("disable")


async def test_revocation_continue_si_keycloak_echoue_et_le_signale(service, kc, sy):
    await enrol(service)
    aid = service.db.one("SELECT id FROM agents")["id"]
    kc.fail_disable = True
    report = await service.revoke("admin.si", aid)
    assert not report.complete
    assert report.steps[0].ok is False
    assert sy.accounts["@awa.ouedraogo:sentinelle.local"]["deactivated"]  # Matrix coupé quand même
    assert service.db.one("SELECT status FROM agents")["status"] == "revocation_partielle"
    # nouvelle tentative : possible et idempotente
    kc.fail_disable = False
    report = await service.revoke("admin.si", aid)
    assert report.complete
    assert service.db.one("SELECT status FROM agents")["status"] == "revoque"


async def test_revocation_detecte_un_appareil_restant(service, sy):
    await enrol(service)
    aid = service.db.one("SELECT id FROM agents")["id"]

    async def delete_devices_noop(mxid, ids):  # simule un échec silencieux
        return None

    sy.delete_devices = delete_devices_noop
    sy.accounts["@awa.ouedraogo:sentinelle.local"]["devices"] = ["D1"]
    report = await service.revoke("admin.si", aid)
    assert not report.complete and "appareil" in report.steps[-1].detail


async def test_un_admin_ne_peut_pas_se_revoquer_lui_meme(service):
    await service.enrol("admin.si", "admin.si", "Admin Securite", "MTDPCE", "Admin", "admin-si")
    aid = service.db.one("SELECT id FROM agents")["id"]
    with pytest.raises(ValidationError):
        await service.revoke("admin.si", aid)


async def test_revocation_agent_inconnu(service):
    with pytest.raises(ValidationError):
        await service.revoke("admin.si", 999)


# ---- canaux classifiés --------------------------------------------------------------
async def test_canal_confidentiel_invite_le_ministere_et_expire_en_24h(service, sy):
    await enrol(service, "awa.ouedraogo", "MTDPCE")
    await enrol(service, "ibrahim.sawadogo", "MTDPCE")
    await enrol(service, "moussa.traore", "Finances")
    await service.create_channel("admin.si", "Cabinet", "confidentiel", "MTDPCE", "awa.ouedraogo")
    room = sy.rooms_created[0]
    assert room["name"].startswith("[CONFIDENTIEL]")
    assert room["max_lifetime_ms"] == 24 * 3600 * 1000
    assert set(room["invitees"]) == {"@awa.ouedraogo:sentinelle.local", "@ibrahim.sawadogo:sentinelle.local"}
    assert room["owner"] == "@awa.ouedraogo:sentinelle.local"


async def test_canal_n_invite_pas_les_agents_revoques(service, sy):
    await enrol(service, "awa.ouedraogo", "MTDPCE")
    await enrol(service, "ibrahim.sawadogo", "MTDPCE")
    iid = service.db.one("SELECT id FROM agents WHERE username='ibrahim.sawadogo'")["id"]
    await service.revoke("admin.si", iid)
    await service.create_channel("admin.si", "Cabinet", "restreinte", "*", "awa.ouedraogo")
    assert sy.rooms_created[0]["invitees"] == ["@awa.ouedraogo:sentinelle.local"]


async def test_canal_refuse_niveau_inconnu_et_responsable_revoque(service):
    await enrol(service)
    with pytest.raises(ValidationError):
        await service.create_channel("admin.si", "X", "secret-defense", "*", "awa.ouedraogo")
    aid = service.db.one("SELECT id FROM agents")["id"]
    await service.revoke("admin.si", aid)
    with pytest.raises(ValidationError):
        await service.create_channel("admin.si", "X", "restreinte", "*", "awa.ouedraogo")


def test_niveaux_de_classification():
    assert LEVELS["confidentiel"].max_lifetime_ms < LEVELS["restreinte"].max_lifetime_ms
    assert LEVELS["demo"].max_lifetime_ms == 300_000


# ---- conformité 2FA -----------------------------------------------------------------
async def test_conformite_signale_les_agents_sans_second_facteur(service, kc):
    await enrol(service, "awa.ouedraogo")
    await enrol(service, "ibrahim.sawadogo")
    kc.otp.add("kc-awa.ouedraogo")
    rows = {r["username"]: r["otp"] for r in await service.compliance()}
    assert rows == {"awa.ouedraogo": True, "ibrahim.sawadogo": False}
