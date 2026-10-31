"""Client de l'API d'administration de Synapse.

Le portail ne manipule JAMAIS de message : il ne fait que gerer les comptes, les
appareils et la creation de salles chiffrees. Le chiffrement reste celui d'Element/Synapse
(Olm/Megolm) ; aucune cryptographie n'est developpee ici. Le seul calcul cryptographique
du depot est le HMAC-SHA1 exige par l'API d'enregistrement administrateur de Synapse
(procedure documentee par Synapse), utilise une fois pour creer le compte technique.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from urllib.parse import quote

import httpx


class SynapseError(RuntimeError):
    pass


class SynapseAdmin:
    def __init__(self, base_url: str, server_name: str, shared_secret: str, token_file: str,
                 http: httpx.AsyncClient | None = None) -> None:
        self.base = base_url.rstrip("/")
        self.server_name = server_name
        self.shared_secret = shared_secret
        self.token_file = token_file
        self.http = http or httpx.AsyncClient(timeout=20)
        self.token: str | None = None
        self.bot_mxid: str | None = None

    def mxid(self, username: str) -> str:
        return f"@{username}:{self.server_name}"

    # ---- authentification technique -------------------------------------------------
    async def ensure_admin_token(self) -> None:
        """Reutilise le jeton enregistre s'il est valide, sinon cree un compte technique."""
        if os.path.exists(self.token_file):
            token = open(self.token_file, encoding="utf-8").read().strip()
            r = await self.http.get(f"{self.base}/_matrix/client/v3/account/whoami",
                                    headers={"Authorization": f"Bearer {token}"})
            if r.status_code == 200:
                self.token, self.bot_mxid = token, r.json()["user_id"]
                return
        username = f"portail-{secrets.token_hex(3)}"
        password = secrets.token_urlsafe(32)
        nonce = (await self.http.get(f"{self.base}/_synapse/admin/v1/register")).json()["nonce"]
        mac = hmac.new(self.shared_secret.encode(), digestmod=hashlib.sha1)
        for part in (nonce, username, password, "admin"):
            mac.update(part.encode())
            if part != "admin":
                mac.update(b"\x00")
        r = await self.http.post(f"{self.base}/_synapse/admin/v1/register", json={
            "nonce": nonce, "username": username, "password": password,
            "admin": True, "mac": mac.hexdigest()})
        if r.status_code != 200:
            raise SynapseError(f"Creation du compte technique impossible ({r.status_code})")
        data = r.json()
        self.token, self.bot_mxid = data["access_token"], data["user_id"]
        os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
        fd = os.open(self.token_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(self.token)

    async def _call(self, method: str, path: str, ok: tuple[int, ...] = (200,), **kw) -> httpx.Response:
        if not self.token:
            raise SynapseError("Jeton technique absent")
        r = await self.http.request(method, f"{self.base}{path}",
                                    headers={"Authorization": f"Bearer {self.token}"}, **kw)
        if r.status_code not in ok:
            raise SynapseError(f"{method} {path.split('?')[0]} -> {r.status_code}")
        return r

    # ---- comptes -----------------------------------------------------------------------
    async def provision_user(self, mxid: str, display_name: str, kc_subject: str) -> None:
        """Pre-cree le compte Matrix et le lie a l'identite Keycloak (sub OIDC).
        Aucun mot de passe : la connexion n'est possible que via Keycloak (2FA)."""
        await self._call("PUT", f"/_synapse/admin/v2/users/{quote(mxid)}", ok=(200, 201), json={
            "displayname": display_name,
            "admin": False,
            "external_ids": [{"auth_provider": "oidc-keycloak", "external_id": kc_subject}],
        })

    async def deactivate(self, mxid: str) -> None:
        """Invalide jetons et appareils, retire le compte de toutes les salles."""
        await self._call("POST", f"/_synapse/admin/v1/deactivate/{quote(mxid)}", json={"erase": False})

    async def list_devices(self, mxid: str) -> list[str]:
        r = await self._call("GET", f"/_synapse/admin/v2/users/{quote(mxid)}/devices")
        return [d["device_id"] for d in r.json().get("devices", [])]

    async def delete_devices(self, mxid: str, device_ids: list[str]) -> None:
        if device_ids:
            await self._call("POST", f"/_synapse/admin/v2/users/{quote(mxid)}/delete_devices",
                             json={"devices": device_ids})

    async def is_deactivated(self, mxid: str) -> bool:
        r = await self._call("GET", f"/_synapse/admin/v2/users/{quote(mxid)}")
        return bool(r.json().get("deactivated"))

    async def joined_rooms(self, mxid: str) -> list[str]:
        r = await self._call("GET", f"/_synapse/admin/v1/users/{quote(mxid)}/joined_rooms")
        return r.json().get("joined_rooms", [])

    # ---- canaux institutionnels classifies --------------------------------------------
    async def create_encrypted_room(self, name: str, topic: str, invitees: list[str], owner: str,
                                    max_lifetime_ms: int) -> str:
        """Cree une salle sur invitation, chiffree de bout en bout, avec expiration
        automatique des messages (purge cote serveur sur horodatage, sans lecture).
        Le compte technique quitte la salle : il n'y reste ni membre ni administrateur."""
        bot = self.bot_mxid or ""
        levels = {bot: 100, owner: 100}
        body = {
            "name": name, "topic": topic, "preset": "private_chat", "visibility": "private",
            "invite": [m for m in invitees if m != owner],
            "initial_state": [
                {"type": "m.room.encryption", "state_key": "",
                 "content": {"algorithm": "m.megolm.v1.aes-sha2"}},
                {"type": "m.room.retention", "state_key": "",
                 "content": {"max_lifetime": max_lifetime_ms}},
                {"type": "m.room.history_visibility", "state_key": "",
                 "content": {"history_visibility": "joined"}},
                {"type": "m.room.join_rules", "state_key": "", "content": {"join_rule": "invite"}},
            ],
            "power_level_content_override": {
                "users": levels,
                "events": {"m.room.encryption": 100, "m.room.retention": 100,
                           "m.room.join_rules": 100, "m.room.history_visibility": 100},
            },
        }
        r = await self._call("POST", "/_matrix/client/v3/createRoom", json=body)
        room_id = r.json()["room_id"]
        # Le responsable doit etre membre AVANT le depart du compte technique : sans membre
        # local dans la salle, les invites ne pourraient plus la rejoindre (constate sur Synapse reel).
        await self._call("POST", f"/_synapse/admin/v1/join/{quote(room_id)}", json={"user_id": owner})
        await self._call("POST", f"/_matrix/client/v3/rooms/{quote(room_id)}/leave", json={})
        return room_id
