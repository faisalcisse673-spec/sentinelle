# Technologies utilisées et licences

Aucune de ces technologies n'impose de service tiers. **Vérifier chaque licence sur le dépôt officiel avant le dépôt du dossier** (les projets changent parfois de licence).

| Technologie | Rôle | Licence | Projet |
|---|---|---|---|
| Synapse | Serveur Matrix (messages, salles, fichiers chiffrés) | AGPL-3.0 | https://github.com/element-hq/synapse |
| Element Web | Client de messagerie (chiffrement Olm/Megolm côté navigateur) | AGPL-3.0 ou GPL-3.0 | https://github.com/element-hq/element-web |
| vodozemac | Implémentation d'Olm/Megolm utilisée par Element | Apache-2.0 | https://github.com/matrix-org/vodozemac |
| Keycloak | Identité, SSO OpenID Connect, second facteur TOTP, rôles | Apache-2.0 | https://github.com/keycloak/keycloak |
| PostgreSQL | Base de données (Synapse, Keycloak) | Licence PostgreSQL | https://www.postgresql.org |
| Caddy | Proxy inverse | Apache-2.0 | https://github.com/caddyserver/caddy |
| FastAPI | Portail d'administration (serveur web) | MIT | https://github.com/fastapi/fastapi |
| Starlette / Uvicorn | Briques de FastAPI | BSD-3-Clause | https://github.com/encode/starlette |
| HTTPX | Client HTTP du portail | BSD-3-Clause | https://github.com/encode/httpx |
| Authlib | Connexion OpenID Connect du portail | BSD-3-Clause | https://github.com/authlib/authlib |
| Jinja2 | Gabarits HTML du portail | BSD-3-Clause | https://github.com/pallets/jinja |
| itsdangerous | Signature des cookies de session | BSD-3-Clause | https://github.com/pallets/itsdangerous |
| python-multipart | Lecture des formulaires | Apache-2.0 | https://github.com/Kludex/python-multipart |
| pytest, pytest-asyncio | Tests automatisés | MIT / Apache-2.0 | https://github.com/pytest-dev/pytest |
| Docker Compose | Déploiement en une commande | Apache-2.0 | https://github.com/docker/compose |

Le code original de ce dépôt (`portal/`, `deploy/`, `scripts/`, `docs/`) est publié sous **AGPL-3.0** (voir `LICENSE`), compatible avec les licences ci-dessus.
