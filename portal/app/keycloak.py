"""Client minimal de l'API d'administration Keycloak (compte de service du portail)."""
from __future__ import annotations

import time

import httpx


class KeycloakError(RuntimeError):
    pass


class KeycloakAdmin:
    def __init__(self, base_url: str, realm: str, client_id: str, client_secret: str,
                 http: httpx.AsyncClient | None = None) -> None:
        self.base = base_url.rstrip("/")
        self.realm = realm
        self.client_id = client_id
        self.client_secret = client_secret
        self.http = http or httpx.AsyncClient(timeout=15)
        self._token: str | None = None
        self._expires = 0.0

    async def _bearer(self) -> str:
        if self._token and time.time() < self._expires - 10:
            return self._token
        r = await self.http.post(
            f"{self.base}/realms/{self.realm}/protocol/openid-connect/token",
            data={"grant_type": "client_credentials", "client_id": self.client_id,
                  "client_secret": self.client_secret},
        )
        if r.status_code != 200:
            raise KeycloakError(f"Jeton de service refuse ({r.status_code})")
        data = r.json()
        self._token = data["access_token"]
        self._expires = time.time() + int(data.get("expires_in", 60))
        return self._token

    async def _call(self, method: str, path: str, ok: tuple[int, ...] = (200, 201, 204), **kw) -> httpx.Response:
        headers = {"Authorization": f"Bearer {await self._bearer()}"}
        r = await self.http.request(method, f"{self.base}/admin/realms/{self.realm}{path}",
                                    headers=headers, **kw)
        if r.status_code not in ok:
            raise KeycloakError(f"{method} {path} -> {r.status_code}")
        return r

    async def find_user(self, username: str) -> dict | None:
        r = await self._call("GET", "/users", params={"username": username, "exact": "true"})
        users = r.json()
        return users[0] if users else None

    async def create_user(self, username: str, full_name: str, password: str,
                          temporary: bool, role: str) -> str:
        """Cree l'agent avec second facteur obligatoire a la premiere connexion."""
        first, _, last = full_name.partition(" ")
        actions = ["CONFIGURE_TOTP"] + (["UPDATE_PASSWORD"] if temporary else [])
        body = {
            "username": username,
            "enabled": True,
            "firstName": first,
            "lastName": last or first,
            # Adresse interne fictive : evite l'ecran "completer le profil" a la connexion.
            "email": f"{username}@sentinelle.local",
            "emailVerified": True,
            "requiredActions": actions,
            "credentials": [{"type": "password", "value": password, "temporary": temporary}],
        }
        r = await self._call("POST", "/users", ok=(201,), json=body)
        user_id = r.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        await self.assign_role(user_id, role)
        return user_id

    async def assign_role(self, user_id: str, role: str) -> None:
        rep = (await self._call("GET", f"/roles/{role}")).json()
        await self._call("POST", f"/users/{user_id}/role-mappings/realm", json=[rep])

    async def disable_and_logout(self, user_id: str) -> None:
        """Desactive le compte puis ferme toutes ses sessions."""
        rep = (await self._call("GET", f"/users/{user_id}")).json()
        rep["enabled"] = False
        await self._call("PUT", f"/users/{user_id}", json=rep)
        await self._call("POST", f"/users/{user_id}/logout")

    async def reenable(self, user_id: str, password: str) -> None:
        """Reactivation apres une revocation : le compte est rouvert mais l'agent doit
        refaire une authentification complete (nouveau mot de passe, nouveau second facteur).
        L'ancien code a usage unique est supprime : l'appareil qui le portait est inconnu."""
        rep = (await self._call("GET", f"/users/{user_id}")).json()
        rep["enabled"] = True
        rep["requiredActions"] = ["UPDATE_PASSWORD", "CONFIGURE_TOTP"]
        await self._call("PUT", f"/users/{user_id}", json=rep)
        creds = (await self._call("GET", f"/users/{user_id}/credentials")).json()
        for cred in creds:
            if cred.get("type") == "otp":
                await self._call("DELETE", f"/users/{user_id}/credentials/{cred['id']}")
        await self._call("PUT", f"/users/{user_id}/reset-password",
                         json={"type": "password", "value": password, "temporary": True})

    async def delete_user(self, user_id: str) -> None:
        await self._call("DELETE", f"/users/{user_id}", ok=(204, 404))

    async def is_enabled(self, user_id: str) -> bool:
        return bool((await self._call("GET", f"/users/{user_id}")).json().get("enabled"))

    async def has_otp(self, user_id: str) -> bool:
        creds = (await self._call("GET", f"/users/{user_id}/credentials")).json()
        return any(c.get("type") == "otp" for c in creds)
