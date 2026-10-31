"""Tests des clients HTTP réels (transport simulé) : forme des requêtes Keycloak et Synapse."""
import hashlib
import hmac
import json

import httpx

from app.keycloak import KeycloakAdmin
from app.synapse import SynapseAdmin


def reference_mac(secret, nonce, user, password, admin):
    """Algorithme décrit dans la documentation de l'API d'enregistrement de Synapse."""
    mac = hmac.new(key=secret.encode(), digestmod=hashlib.sha1)
    mac.update(nonce.encode()); mac.update(b"\x00")
    mac.update(user.encode()); mac.update(b"\x00")
    mac.update(password.encode()); mac.update(b"\x00")
    mac.update(b"admin" if admin else b"notadmin")
    return mac.hexdigest()


async def test_synapse_cree_le_compte_technique_avec_le_bon_mac(tmp_path):
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"nonce": "abc123"})
        body = json.loads(request.content)
        seen.update(body)
        return httpx.Response(200, json={"access_token": "tok", "user_id": "@portail-x:s.local"})

    sy = SynapseAdmin("http://s", "s.local", "secret-partage", str(tmp_path / "tok"),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await sy.ensure_admin_token()
    assert seen["admin"] is True
    assert seen["mac"] == reference_mac("secret-partage", "abc123", seen["username"], seen["password"], True)
    assert sy.token == "tok"
    assert (tmp_path / "tok").read_text() == "tok"


async def test_synapse_reutilise_le_jeton_valide(tmp_path):
    (tmp_path / "tok").write_text("deja-la")
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json={"user_id": "@portail-old:s.local"})

    sy = SynapseAdmin("http://s", "s.local", "x", str(tmp_path / "tok"),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await sy.ensure_admin_token()
    assert calls == ["/_matrix/client/v3/account/whoami"] and sy.token == "deja-la"


async def test_synapse_provisionne_sans_mot_de_passe_et_lie_l_identite_oidc(tmp_path):
    seen = {}

    def handler(request):
        seen["path"], seen["body"] = request.url.raw_path.decode(), json.loads(request.content)
        return httpx.Response(201, json={})

    sy = SynapseAdmin("http://s", "s.local", "x", str(tmp_path / "t"),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    sy.token = "t"
    await sy.provision_user("@awa:s.local", "Awa", "kc-uuid")
    assert seen["path"] == "/_synapse/admin/v2/users/%40awa%3As.local"
    assert "password" not in seen["body"] and seen["body"]["admin"] is False
    assert seen["body"]["external_ids"] == [{"auth_provider": "oidc-keycloak", "external_id": "kc-uuid"}]


async def test_salle_chiffree_expirante_sur_invitation_puis_le_compte_technique_quitte(tmp_path):
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(200, json={"room_id": "!r:s.local"})

    sy = SynapseAdmin("http://s", "s.local", "x", str(tmp_path / "t"),
                      http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    sy.token, sy.bot_mxid = "t", "@bot:s.local"
    await sy.create_encrypted_room("[CONFIDENTIEL] X", "t", ["@a:s.local", "@b:s.local"], "@a:s.local", 86_400_000)
    create = calls[0][2]
    state = {e["type"]: e["content"] for e in create["initial_state"]}
    assert state["m.room.encryption"]["algorithm"] == "m.megolm.v1.aes-sha2"
    assert state["m.room.retention"]["max_lifetime"] == 86_400_000
    assert state["m.room.join_rules"]["join_rule"] == "invite"
    assert create["power_level_content_override"]["users"]["@a:s.local"] == 100
    assert calls[1][1].startswith("/_synapse/admin/v1/join/") and calls[1][2] == {"user_id": "@a:s.local"}
    assert calls[2][1].endswith("/leave")  # le compte technique ne reste pas dans la salle
    assert "@a:s.local" not in create["invite"]  # le responsable est inscrit directement


async def test_keycloak_exige_otp_a_la_creation_et_utilise_le_compte_de_service():
    seen = {}

    def handler(request):
        path = request.url.path
        if path.endswith("/token"):
            return httpx.Response(200, json={"access_token": "svc", "expires_in": 60})
        if request.method == "POST" and path.endswith("/users"):
            seen["user"] = json.loads(request.content)
            assert request.headers["authorization"] == "Bearer svc"
            return httpx.Response(201, headers={"Location": "http://kc/admin/realms/r/users/uuid-1"})
        if request.method == "GET" and "/roles/" in path:
            return httpx.Response(200, json={"id": "r1", "name": "agent"})
        return httpx.Response(204)

    kc = KeycloakAdmin("http://kc", "r", "portal-admin", "s", http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    uid = await kc.create_user("awa", "Awa Ouedraogo", "pw", True, "agent")
    assert uid == "uuid-1"
    assert "CONFIGURE_TOTP" in seen["user"]["requiredActions"]
    assert "UPDATE_PASSWORD" in seen["user"]["requiredActions"]
    assert seen["user"]["credentials"][0]["temporary"] is True
