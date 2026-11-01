"""Doubles de test : aucun Keycloak ni Synapse réel n'est nécessaire pour ces tests."""
import base64
import json
import os
import sys

import itsdangerous
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.config import Settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.service import AgentService  # noqa: E402


class FakeKeycloak:
    def __init__(self):
        self.users: dict[str, dict] = {}
        self.calls: list[str] = []
        self.fail_disable = False
        self.fail_reenable = False
        self.otp: set[str] = set()

    async def create_user(self, username, full_name, password, temporary, role):
        self.calls.append(f"create:{username}")
        uid = f"kc-{username}"
        self.users[uid] = {"username": username, "enabled": True, "role": role,
                           "temporary": temporary, "password": password}
        return uid

    async def disable_and_logout(self, uid):
        self.calls.append(f"disable:{uid}")
        if self.fail_disable:
            raise RuntimeError("Keycloak indisponible")
        self.users[uid]["enabled"] = False

    async def reenable(self, uid, password):
        self.calls.append(f"reenable:{uid}")
        if self.fail_reenable:
            raise RuntimeError("Keycloak indisponible")
        self.users[uid].update(enabled=True, password=password, temporary=True)
        self.otp.discard(uid)

    async def is_enabled(self, uid):
        return self.users[uid]["enabled"]

    async def delete_user(self, uid):
        self.calls.append(f"delete:{uid}")
        self.users.pop(uid, None)

    async def has_otp(self, uid):
        return uid in self.otp


class FakeSynapse:
    server_name = "sentinelle.local"

    def __init__(self):
        self.accounts: dict[str, dict] = {}
        self.calls: list[str] = []
        self.fail_provision = False
        self.rooms_created: list[dict] = []
        self.rooms_left_after: int = 0  # nb d'appels avant que l'utilisateur ait quitté ses salles

    def mxid(self, username):
        return f"@{username}:{self.server_name}"

    async def provision_user(self, mxid, display_name, kc_subject):
        self.calls.append(f"provision:{mxid}")
        if self.fail_provision:
            raise RuntimeError("Synapse indisponible")
        self.accounts[mxid] = {"deactivated": False, "devices": ["D1", "D2"],
                               "rooms": ["!r:s"], "kc": kc_subject}

    async def deactivate(self, mxid):
        self.calls.append(f"deactivate:{mxid}")
        self.accounts[mxid].update(deactivated=True, rooms=[])

    async def reactivate(self, mxid, display_name, kc_subject):
        self.calls.append(f"reactivate:{mxid}")
        self.accounts[mxid].update(deactivated=False, kc=kc_subject)

    async def list_devices(self, mxid):
        return list(self.accounts[mxid]["devices"])

    async def delete_devices(self, mxid, ids):
        self.calls.append(f"delete_devices:{len(ids)}")
        self.accounts[mxid]["devices"] = []

    async def is_deactivated(self, mxid):
        return self.accounts[mxid]["deactivated"]

    async def joined_rooms(self, mxid):
        return list(self.accounts[mxid]["rooms"])

    async def create_encrypted_room(self, name, topic, invitees, owner, max_lifetime_ms):
        self.rooms_created.append({"name": name, "invitees": invitees, "owner": owner,
                                   "max_lifetime_ms": max_lifetime_ms})
        return "!room:sentinelle.local"


@pytest.fixture
def kc():
    return FakeKeycloak()


@pytest.fixture
def sy():
    return FakeSynapse()


@pytest.fixture
def db(tmp_path):
    return Database(str(tmp_path / "t.db"))


@pytest.fixture
def service(kc, sy, db):
    return AgentService(kc, sy, db)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        keycloak_url="http://auth.test", realm="sentinelle", portal_client_id="portal",
        portal_client_secret="x", kc_admin_client_id="portal-admin", kc_admin_client_secret="y",
        synapse_url="http://synapse.test", server_name="sentinelle.local", shared_secret="z",
        base_url="http://admin.test", session_secret="secret-de-test", data_dir=str(tmp_path),
        seed_demo=False)


def session_cookie(secret: str, data: dict) -> str:
    """Fabrique un cookie de session Starlette signé pour les tests."""
    raw = base64.b64encode(json.dumps(data).encode("utf-8"))
    return itsdangerous.TimestampSigner(secret).sign(raw).decode("utf-8")
