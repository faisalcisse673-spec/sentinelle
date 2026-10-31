# STATUS (fichier de reprise : à lire EN PREMIER à chaque reprise de session)

Dernière mise à jour : sam. 31 oct. 2026, 18h55 (UTC+0). Échéance de dépôt : **dim. 1er nov. 2026, 23h59**.

## Contexte
- Sprint pré-hackathon 2026 (Hackathon 226, MTDPCE-DGTD), challenge « La messagerie souveraine de l'administration ».
- Équipe de 3 élèves ingénieurs EPO (5e année) : l'utilisateur (IA et Data), Alfred (Génie logiciel), Cramer (Réseaux et Télécoms).
- Aucun travail antérieur n'existe : tout est reconstruit dans ce dépôt (décision du 31 oct. 18h53).
- Nom proposé (à confirmer par l'équipe) : équipe **Harmattan**, produit **Sentinelle**.
- Machine de démo : HP EliteBook 1040 G8, 32 Go de RAM, probablement Windows + Docker Desktop (donc fins de ligne LF forcées via .gitattributes).

## Décisions d'architecture (validées)
- Niveau open source : **Étendre et adapter** (Element Web + Synapse), AUCUNE crypto maison (Olm/Megolm).
- Identité : Keycloak (OIDC, TOTP obligatoire, rôles). Synapse en SSO uniquement, inscription fermée, fédération coupée.
- Portail d'administration (FastAPI + Jinja2) : enrôlement, annuaire par ministère et fonction, révocation unique (Keycloak + Synapse), journal d'audit, canaux institutionnels classifiés (rétention Synapse).
- Astuce réseau : Caddy avec alias Docker `auth.localhost`, `matrix.localhost`, `chat.localhost`, `admin.localhost` sur le port 8080, pour que navigateur et conteneurs utilisent les mêmes URL.
- Test « rien en clair » : script qui cherche une chaîne témoin dans pg_dump et le stockage média.

## Limites de l'environnement de Claude (importantes)
- Docker Hub et GitHub Releases sont bloqués : la pile complète n'a PAS pu être démarrée par Claude.
- Testable par Claude : validation de la config Synapse (pip), tests unitaires du portail, JSON/YAML.
- Tout le reste doit être lancé par l'équipe (`docker compose up -d`) ; les erreurs sont à renvoyer à Claude.

## Avancement
- [x] PDF relu, pile validée
- [x] Dépôt initialisé, LICENSE (AGPL-3.0) en place
- [ ] docker-compose.yml, .env, .gitattributes
- [ ] deploy/ : caddy, element, synapse, keycloak (realm), postgres init
- [ ] portal/ : app FastAPI + tests
- [ ] scripts/ : verify_no_plaintext, comptes de démo
- [ ] README.md (FR, 2 pages max), THIRD_PARTY.md
- [ ] Pièces du dossier : fiche équipe, note de pré-projet (2 p.), note de sécurité (2 p.)
- [ ] Script de la vidéo (3 min)
- [ ] Bonus : tests automatisés (+2) ; langue nationale (+3, traduction à faire valider par un locuteur natif)

## Reste à demander à l'équipe
- Confirmer le nom d'équipe, noms/filières/contacts, attestations d'inscription 2026-2027.
- Créer le dépôt public (GitHub/GitLab/Codeberg) et pousser avec des commits RÉELS et progressifs.
