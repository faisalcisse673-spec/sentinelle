# STATUS (fichier de reprise : à lire EN PREMIER à chaque reprise de session)

Dernière mise à jour : sam. 31 oct. 2026, ~19h40 (UTC+0). Échéance de dépôt : **dim. 1er nov. 2026, 23h59**.

## RÈGLE ABSOLUE
Le travail précédent EXISTE. Ne JAMAIS repartir de zéro ni réécrire un fichier existant sans l'avoir lu.
Avant toute écriture : `git status`, `git log`, lire le fichier. Les anciennes itérations sont dans /home/claude :
- `sentinelle/` : **dépôt actuel, à continuer** (réécriture du 31 oct. 12h49-13h00 : portail + 42 tests + Docker Compose)
- `kibare/`, `tenga-msg/` : itérations antérieures (mêmes idées, anciens noms). Ne pas les utiliser comme base.
- `sandbox/` : essais réels (hors Docker) contre un vrai Keycloak 26.5.7 et un vrai Synapse (scénarios 1 et 2 : enrôlement,
  2e facteur, révocation, whoami 401, reconnexion refusée) : VALIDÉS sur l'itération `kibare`.

## Contexte
- Sprint pré-hackathon 2026 (Hackathon 226, MTDPCE-DGTD), challenge « La messagerie souveraine de l'administration ».
- Équipe de 3 élèves ingénieurs EPO (5e année) : l'utilisateur (IA et Data), Alfred (Génie logiciel), Cramer (Réseaux et Télécoms).
- Produit : **Sentinelle**. Nom d'équipe : à confirmer (proposition : Harmattan).
- Machine de démo : HP EliteBook 1040 G8, 32 Go, Docker Desktop probable (fins de ligne LF forcées via .gitattributes).

## Architecture (en place dans le dépôt)
- Niveau open source : **Étendre et adapter** (Element Web + Synapse). AUCUNE crypto maison (Olm/Megolm côté clients).
- Keycloak (OIDC, rôles `agent` / `admin-si`, TOTP exigé par action requise CONFIGURE_TOTP à la 1re connexion).
- Synapse : SSO uniquement, mots de passe Matrix désactivés, inscription fermée, fédération coupée, présence coupée,
  E2EE par défaut sur toutes les salles, `attribute_requirements` (rôle requis), rétention serveur.
- Caddy : domaines distincts `chat.` `matrix.` `auth.` `admin.localhost:8080` (alias Docker, mêmes URL navigateur/conteneurs).
  Origines séparées : le portail ne partage pas l'origine d'Element.
- Portail FastAPI : enrôlement, révocation unique en 4 étapes + vérification finale, canaux classifiés
  (restreinte 30 j / confidentiel 24 h / démo 5 min), conformité 2FA, journal d'audit. Comptes de démo via SEED_DEMO=1.
- Tests : `cd portal && pytest` → 42 tests verts (vérifié le 31 oct. 19h).

## Limites de l'environnement de Claude
- Docker Hub bloqué : le `docker-compose.yml` n'a JAMAIS été démarré par Claude. Seule l'équipe peut le valider.
- Claude peut tester : config Synapse (pip, version 1.139), tests unitaires du portail, processus réels hors Docker
  (Keycloak dans /home/claude/sandbox/keycloak-26.5.7).

## Avancement
- [x] PDF relu, pile validée
- [x] Dépôt : compose, deploy/ (caddy, element, synapse, keycloak, postgres), portail + 42 tests, LICENSE AGPL-3.0
- [ ] **Validation `docker compose up -d --build` sur la machine de l'équipe** (bloquant, à faire ce soir)
- [x] scripts/verify-no-plaintext.sh + service `verifier` (profil `outils`) : syntaxe et compose validés, NON exécuté contre un vrai Postgres
- [x] README.md (2 p.), THIRD_PARTY.md (licences Element Web / vodozemac à revérifier à la source)
- [x] docs/ : NOTE_PRE_PROJET.pdf + NOTE_SECURITE.pdf (2 p. chacun, vérifié), SCRIPT_VIDEO, DEMO_JURY
- [ ] docs/FICHE_EQUIPE.md : champs [entre crochets] à compléter par l'équipe + 3 attestations d'inscription 2026-2027
- [ ] Après validation du compose par l'équipe : corriger ce qui casse, mettre à jour les docs si le comportement diffère
- [ ] Commits Git réels et progressifs poussés sur un dépôt public par l'équipe (auteurs = les 3 étudiants)
- [ ] Bonus : tests automatisés (+2, déjà 42 tests) ; langue nationale (+3, à faire valider par un locuteur natif)

## À demander / faire par l'équipe
- Confirmer le nom d'équipe ; noms, filières, contacts ; attestations d'inscription 2026-2027.
- Créer le dépôt public (GitHub/GitLab/Codeberg) et pousser avec des commits RÉELS (auteurs : les étudiants).
