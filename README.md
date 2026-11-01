# Sentinelle : la messagerie souveraine de l'administration

Équipe **Harmattan**, École Polytechnique de Ouagadougou. Réponse au challenge « La messagerie souveraine de l'administration » (Hackathon 226, sprint technique pré-hackathon 2026, MTDPCE-DGTD).

## Concept

Les agents publics échangent des informations de service sur des messageries dont les serveurs échappent à l'État. **Sentinelle** est une messagerie instantanée (messages, groupes, fichiers) hébergée sur l'infrastructure de l'État, **chiffrée de bout en bout**, réservée aux agents enrôlés avec **second facteur** et **rôles**. L'innovation tient dans un **portail d'administration souveraine** :

- **enrôlement** des agents par ministère et par fonction (annuaire officiel) ;
- **révocation unique** : un clic coupe Keycloak et Synapse, supprime les appareils, retire l'agent des salles, puis **vérifie** le résultat et l'inscrit au journal d'audit ;
- **canaux institutionnels classifiés** (Diffusion restreinte, Confidentiel) : chiffrés, sur invitation, avec **expiration automatique** des messages côté serveur ;
- **conformité** : liste des agents n'ayant pas encore configuré leur second facteur.

## Architecture

```
 Navigateur de l'agent                       Infrastructure de l'État (Docker Compose)
 ┌──────────────────┐   HTTP(S)   ┌───────┐   ┌──────────────┐   ┌────────────┐
 │ Element Web      │────────────▶│ Caddy │──▶│ Synapse      │──▶│ PostgreSQL │
 │ chiffre/déchiffre│             │ proxy │   │ (ne voit que │   └────────────┘
 │ (Olm/Megolm)     │             └───┬───┘   │  du chiffré) │
 └──────────────────┘                 │       └──────▲───────┘
                                      │ SSO (OIDC)   │ API admin (réseau interne)
                                  ┌───▼──────┐   ┌───┴────────────────────┐
                                  │ Keycloak │◀──│ Portail d'administration│
                                  │ 2FA TOTP │   │ FastAPI (enrôle, révoque)│
                                  └──────────┘   └────────────────────────┘
```

Les clés ne quittent jamais le navigateur : le serveur et le portail ne manipulent que du chiffré. **Aucune cryptographie n'est développée par l'équipe** : protocole **Matrix (Olm/Megolm)**, implémenté par Element Web. Aucun service tiers n'est nécessaire (pas de fédération, d'aperçu d'URL, de CDN ni d'analytique).

## Niveau d'engagement open source

**Étendre et adapter** : Element Web et Synapse, configurés et durcis, étendus par un composant original (portail d'administration, `portal/`). Le code produit est publié sous **AGPL-3.0** (fichier `LICENSE`). Chaque technologie est citée avec sa licence dans [`THIRD_PARTY.md`](THIRD_PARTY.md).

## Installation (une seule commande)

Prérequis : Docker (Desktop ou Engine) avec Compose v2, 4 Go de RAM libres, port 8080 libre.

```
docker compose up -d --build
docker compose ps        # attendre que tous les services soient "healthy" (2 à 4 minutes)
```

| Service | Adresse |
|---|---|
| Messagerie (Element) | http://chat.localhost:8080 |
| Portail d'administration | http://admin.localhost:8080 (rôle `admin-si` requis) |

Les noms `*.localhost` sont résolus automatiquement par Chrome, Firefox et Edge.

**Comptes de démonstration (fictifs)**, mot de passe `Sentinelle#Demo2026` : `admin.si` (administrateur), `awa.ouedraogo`, `ibrahim.sawadogo`, `fatimata.kabore`, `moussa.traore`. À la première connexion, un QR code permet de créer le second facteur avec n'importe quelle application TOTP (FreeOTP, Aegis, Google Authenticator...).

**Une identité par navigateur** : la connexion est unique (SSO). Pour jouer plusieurs agents, utilisez une fenêtre privée ou un profil de navigateur par agent (voir `docs/DEMO_JURY.md`).

Réinitialisation complète : `docker compose down -v`.

## Vérifications

- **Tests automatisés** (43, dont enrôlement, révocation, accès refusé, CSRF) : `cd portal && pip install -r requirements-dev.txt && pytest`.
- **Preuve « le serveur ne lit rien »** : envoyer un message contenant `TEMOIN-7421`, puis `docker compose --profile outils run --rm verifier TEMOIN-7421`. Le script inspecte la base et les fichiers comme le ferait un administrateur et échoue si un message ou un fichier est en clair.
- **Essai « Intrus »** (inscription, mot de passe Matrix et API d'administration refusés) : `powershell -ExecutionPolicy Bypass -File .\scripts\essai-intrus.ps1`, attendu `RESULTAT : REUSSI`. Sous Linux ou macOS, les mêmes appels `curl` sont décrits dans [`docs/DEMO_JURY.md`](docs/DEMO_JURY.md), épreuve 3.
- Déroulé complet des épreuves du jury : [`docs/DEMO_JURY.md`](docs/DEMO_JURY.md).

## Documentation

[`docs/NOTE_PRE_PROJET.md`](docs/NOTE_PRE_PROJET.md) · [`docs/NOTE_SECURITE.md`](docs/NOTE_SECURITE.md) (menaces, métadonnées, limites) · [`docs/SCRIPT_VIDEO.md`](docs/SCRIPT_VIDEO.md)

## Limites connues (détail dans la note de sécurité)

- La démonstration tourne en HTTP sur la boucle locale ; en production, TLS est obligatoire (Caddy avec un nom de domaine réel).
- Les secrets du dépôt sont des valeurs de démonstration à changer.
- La révocation coupe l'accès au serveur ; elle n'efface pas ce qu'un téléphone volé a déjà déchiffré et stocké localement.
- Noms de salles, membres et horodatages ne sont pas chiffrés (limite du protocole Matrix).
- Le blocage des captures d'écran et du transfert est impossible dans un client web.
