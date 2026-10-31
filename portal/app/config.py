"""Configuration du portail, lue depuis l'environnement."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Variable d'environnement manquante : {name}")
    return value


@dataclass(frozen=True)
class Settings:
    keycloak_url: str
    realm: str
    portal_client_id: str
    portal_client_secret: str
    kc_admin_client_id: str
    kc_admin_client_secret: str
    synapse_url: str
    server_name: str
    shared_secret: str
    base_url: str
    session_secret: str
    data_dir: str
    seed_demo: bool
    admin_role: str = "admin-si"
    agent_role: str = "agent"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            keycloak_url=_env("KEYCLOAK_URL").rstrip("/"),
            realm=_env("KEYCLOAK_REALM", "sentinelle"),
            portal_client_id=_env("PORTAL_CLIENT_ID", "portal"),
            portal_client_secret=_env("PORTAL_CLIENT_SECRET"),
            kc_admin_client_id=_env("KC_ADMIN_CLIENT_ID", "portal-admin"),
            kc_admin_client_secret=_env("KC_ADMIN_CLIENT_SECRET"),
            synapse_url=_env("SYNAPSE_URL").rstrip("/"),
            server_name=_env("MATRIX_SERVER_NAME"),
            shared_secret=_env("SYNAPSE_SHARED_SECRET"),
            base_url=_env("PORTAL_BASE_URL").rstrip("/"),
            session_secret=_env("PORTAL_SESSION_SECRET"),
            data_dir=_env("PORTAL_DATA_DIR", "/data"),
            seed_demo=_env("SEED_DEMO", "0") == "1",
        )
