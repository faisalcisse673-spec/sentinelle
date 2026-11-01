"""Logique metier : enrolement, revocation unique, canaux classifies."""
from __future__ import annotations

import asyncio
import re
import secrets
import time
from dataclasses import dataclass, field

from .db import Database

USERNAME_RE = re.compile(r"^[a-z][a-z0-9._-]{2,31}$")
ROLES = ("agent", "admin-si")


@dataclass(frozen=True)
class Level:
    key: str
    label: str
    max_lifetime_ms: int
    description: str


LEVELS: dict[str, Level] = {
    "restreinte": Level("restreinte", "Diffusion restreinte", 30 * 24 * 3600 * 1000,
                        "Chiffré de bout en bout, sur invitation, messages purgés après 30 jours."),
    "confidentiel": Level("confidentiel", "Confidentiel", 24 * 3600 * 1000,
                          "Chiffré de bout en bout, sur invitation, messages purgés après 24 heures."),
    "demo": Level("demo", "Éphémère (démonstration)", 5 * 60 * 1000,
                  "Messages purgés après 5 minutes, pour démontrer l'expiration automatique."),
}


class ValidationError(ValueError):
    pass


@dataclass
class Step:
    name: str
    ok: bool
    detail: str = ""
    ms: int = 0


@dataclass
class RevocationReport:
    agent: str
    steps: list[Step] = field(default_factory=list)

    @property
    def total_ms(self) -> int:
        return sum(s.ms for s in self.steps)

    @property
    def complete(self) -> bool:
        return bool(self.steps) and all(s.ok for s in self.steps)


class AgentService:
    def __init__(self, kc, synapse, db: Database) -> None:
        self.kc, self.sy, self.db = kc, synapse, db

    # ---- enrolement -----------------------------------------------------------------
    async def enrol(self, actor: str, username: str, full_name: str, ministere: str,
                    fonction: str, role: str = "agent", password: str | None = None,
                    temporary: bool = True) -> str:
        """Retourne le mot de passe provisoire (affiché une seule fois à l'administrateur)."""
        username = username.strip().lower()
        full_name, ministere, fonction = full_name.strip(), ministere.strip(), fonction.strip()
        if not USERNAME_RE.match(username):
            raise ValidationError("Identifiant invalide (3 à 32 caractères : a-z, 0-9, . _ -).")
        if role not in ROLES:
            raise ValidationError("Rôle inconnu.")
        if not (full_name and ministere and fonction):
            raise ValidationError("Nom, ministère et fonction sont obligatoires.")
        if self.db.one("SELECT 1 FROM agents WHERE username=?", (username,)):
            raise ValidationError("Cet identifiant existe déjà.")
        password = password or secrets.token_urlsafe(12)
        kc_id = await self.kc.create_user(username, full_name, password, temporary, role)
        mxid = self.sy.mxid(username)
        try:
            await self.sy.provision_user(mxid, full_name, kc_id)
        except Exception:
            await self.kc.delete_user(kc_id)  # pas de compte orphelin
            self.db.audit(actor, "enrolement_echec", username, "provisionnement Matrix impossible")
            raise
        self.db.execute(
            "INSERT INTO agents (username, full_name, ministere, fonction, role, kc_id, mxid, created_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (username, full_name, ministere, fonction, role, kc_id, mxid, int(time.time())))
        self.db.audit(actor, "enrolement", username, f"{ministere} / {fonction} / rôle={role}")
        return password

    # ---- revocation unique ----------------------------------------------------------
    async def revoke(self, actor: str, agent_id: int) -> RevocationReport:
        row = self.db.one("SELECT * FROM agents WHERE id=?", (agent_id,))
        if row is None:
            raise ValidationError("Agent introuvable.")
        if row["username"] == actor:
            raise ValidationError("Un administrateur ne peut pas se révoquer lui-même.")
        report = RevocationReport(agent=row["username"])
        mxid, kc_id = row["mxid"], row["kc_id"]

        async def run(name: str, coro_factory, detail_ok: str = "") -> bool:
            t0 = time.monotonic()
            try:
                result = await coro_factory()
                detail = detail_ok or (result if isinstance(result, str) else "")
                report.steps.append(Step(name, True, detail, int((time.monotonic() - t0) * 1000)))
                return True
            except Exception as exc:  # on continue : chaque etape est independante
                report.steps.append(Step(name, False, str(exc), int((time.monotonic() - t0) * 1000)))
                return False

        async def kc_step() -> str:
            await self.kc.disable_and_logout(kc_id)
            return "Compte Keycloak désactivé, sessions fermées"

        async def deactivate_step() -> str:
            await self.sy.deactivate(mxid)
            return "Compte Matrix désactivé : jetons invalidés, salles quittées"

        async def devices_step() -> str:
            ids = await self.sy.list_devices(mxid)
            await self.sy.delete_devices(mxid, ids)
            return f"{len(ids)} appareil(s) supprimé(s)"

        async def verify_step() -> str:
            if not await self.sy.is_deactivated(mxid):
                raise RuntimeError("le compte Matrix est encore actif")
            remaining = await self.sy.list_devices(mxid)
            if remaining:
                raise RuntimeError(f"{len(remaining)} appareil(s) encore enregistré(s)")
            rooms: list[str] = []
            for _ in range(10):  # Synapse retire parfois les salles en tâche de fond
                rooms = await self.sy.joined_rooms(mxid)
                if not rooms:
                    break
                await asyncio.sleep(0.5)
            if rooms:
                raise RuntimeError(f"encore membre de {len(rooms)} salle(s)")
            return "Vérifié : compte désactivé, 0 appareil, 0 salle"

        await run("Keycloak : désactivation et fermeture des sessions", kc_step)
        await run("Synapse : désactivation du compte", deactivate_step)
        await run("Synapse : suppression des appareils", devices_step)
        await run("Vérification finale", verify_step)

        status = "revoque" if report.complete else "revocation_partielle"
        self.db.execute("UPDATE agents SET status=?, revoked_at=? WHERE id=?",
                        (status, int(time.time()), agent_id))
        self.db.audit(actor, "revocation", row["username"],
                      f"{status} en {report.total_ms} ms")
        return report

    # ---- canaux institutionnels -----------------------------------------------------
    async def create_channel(self, actor: str, name: str, level_key: str, ministere: str,
                             owner_username: str) -> str:
        name = name.strip()
        if not name:
            raise ValidationError("Le nom du canal est obligatoire.")
        level = LEVELS.get(level_key)
        if level is None:
            raise ValidationError("Niveau de classification inconnu.")
        owner = self.db.one("SELECT * FROM agents WHERE username=? AND status='actif'",
                            (owner_username,))
        if owner is None:
            raise ValidationError("Le responsable doit être un agent actif.")
        if ministere and ministere != "*":
            members = self.db.query(
                "SELECT mxid FROM agents WHERE status='actif' AND role='agent' AND ministere=?",
                (ministere,))
        else:
            members = self.db.query(
                "SELECT mxid FROM agents WHERE status='actif' AND role='agent'")
        # Separation des taches : les administrateurs ne sont pas invites d'office (seul le
        # responsable choisi rejoint le canal directement).
        invitees = [m["mxid"] for m in members]
        title = f"[{level.label.upper()}] {name}"
        room_id = await self.sy.create_encrypted_room(
            title, level.description, invitees, owner["mxid"], level.max_lifetime_ms)
        self.db.execute(
            "INSERT INTO channels (room_id, name, niveau, ministere, owner, members, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (room_id, title, level.key, ministere or "*", owner_username, len(invitees),
             int(time.time())))
        self.db.audit(actor, "canal_cree", title, f"niveau={level.key} membres={len(invitees)}")
        return room_id

    # ---- conformite -----------------------------------------------------------------
    async def compliance(self) -> list[dict]:
        """Pour chaque agent actif : second facteur configure ?"""
        out = []
        for row in self.db.query("SELECT * FROM agents WHERE status='actif' ORDER BY username"):
            try:
                otp = await self.kc.has_otp(row["kc_id"])
                err = ""
            except Exception as exc:
                otp, err = False, str(exc)
            out.append({"username": row["username"], "full_name": row["full_name"],
                        "otp": otp, "error": err})
        return out

    # ---- donnees de demonstration ---------------------------------------------------
    async def seed_demo(self) -> None:
        if self.db.one("SELECT 1 FROM agents LIMIT 1"):
            return
        demo = [
            ("admin.si", "Administrateur Sécurité", "MTDPCE", "Administrateur sécurité", "admin-si"),
            ("awa.ouedraogo", "Awa Ouédraogo", "MTDPCE", "Directrice de cabinet", "agent"),
            ("ibrahim.sawadogo", "Ibrahim Sawadogo", "MTDPCE", "Chef de service informatique", "agent"),
            ("fatimata.kabore", "Fatimata Kaboré", "Santé", "Directrice des études", "agent"),
            ("moussa.traore", "Moussa Traoré", "Finances", "Inspecteur des services", "agent"),
        ]
        for username, name, ministere, fonction, role in demo:
            await self.enrol("seed", username, name, ministere, fonction, role,
                             password=DEMO_PASSWORD, temporary=False)


DEMO_PASSWORD = "Sentinelle#Demo2026"
