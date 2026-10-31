# Guide de démonstration pour le jury et pour l'entretien

Pré-requis : `docker compose up -d --build`, tous les services `healthy`. Deux navigateurs (ou une fenêtre privée) pour jouer deux agents. Comptes fictifs, mot de passe `Sentinelle#Demo2026`. Première connexion de chaque compte : créer le TOTP avec l'application d'authentification.

## Épreuve 1 : « Le serveur ne lit rien »

1. Dans Element (`http://chat.localhost:8080`), `awa.ouedraogo` crée une discussion de groupe avec `ibrahim.sawadogo`, envoie `TEMOIN-7421` et joint un PDF.
2. Dans un terminal : `docker compose --profile outils run --rm verifier TEMOIN-7421`.
3. Résultat attendu : `RESULTAT : REUSSI`. Aucun `m.room.message`, toutes les salles chiffrées, mot témoin absent de la base et des médias, aucun PDF lisible.
4. Trafic réseau (option) : `docker run --rm --net container:$(docker compose ps -q proxy) nicolaka/netshoot tcpdump -i any -A -s0 port 8080 | grep -a TEMOIN` ne doit rien afficher : seul du chiffré circule.

## Épreuve 2 : Révocation pendant une conversation de groupe

1. `awa`, `ibrahim` et `moussa.traore` discutent dans un même groupe.
2. Dans le portail (`http://admin.localhost:8080`, compte `admin.si`) : Agents, puis **Révoquer** `moussa.traore`.
3. Le portail affiche les étapes (Keycloak, compte Matrix, appareils, vérification finale) et la durée.
4. Côté `moussa` : la session se ferme à la prochaine synchronisation et il ne reçoit plus les nouveaux messages. Une reconnexion est refusée (compte Keycloak désactivé). Côté `awa` : le groupe continue, `moussa` n'y figure plus.

## Épreuve 3 : Intrus

- Un compte non enrôlé ne peut pas se connecter : l'inscription est fermée dans Keycloak (`registrationAllowed: false`).
- Tentative d'inscription directe : `curl -X POST http://matrix.localhost:8080/_matrix/client/v3/register -H "Content-Type: application/json" -d "{}"` est refusée.
- Tentative de connexion par mot de passe Matrix : impossible (mots de passe Matrix désactivés).
- Rejoindre un groupe sans invitation : refusé (salles sur invitation).
- Portail : un agent simple ou un visiteur reçoit un refus (`admin-si` requis).

## Épreuve 4 : Innovation

1. Portail, **Canaux** : créer un canal *Confidentiel* pour un ministère. Les agents actifs du ministère sont invités, chiffrés dès la création.
2. Créer un canal *Éphémère (démonstration)* (5 minutes) : envoyer un message, attendre la purge (le serveur purge chaque minute), recharger Element : le message a expiré, sans que le serveur l'ait jamais lu.
3. **Conformité** : liste des agents sans second facteur. **Audit** : toutes les actions d'administration.

## Épreuve 5 : Explication du code (qui répond est désigné par le jury)

| Fonction | Fichier | À savoir expliquer |
|---|---|---|
| `AgentService.revoke` | `portal/app/service.py` | Les 4 étapes, pourquoi Keycloak d'abord, pourquoi on continue si une étape échoue, la vérification finale |
| `AgentService.enrol` | `portal/app/service.py` | Création Keycloak avec TOTP obligatoire, compte Matrix lié par l'identifiant OIDC, annulation en cas d'échec |
| `SynapseAdmin.create_encrypted_room` | `portal/app/synapse.py` | Chiffrement imposé à la création, rétention, pourquoi le compte technique quitte la salle |
| `KeycloakAdmin.create_user` | `portal/app/keycloak.py` | Actions requises `CONFIGURE_TOTP` et `UPDATE_PASSWORD`, mot de passe temporaire |
| `is_admin` et la route `/auth/callback` | `portal/app/main.py` | Connexion OIDC, contrôle du rôle côté serveur, session signée, CSRF |
| `oidc_providers` | `deploy/synapse/homeserver.yaml` | SSO uniquement, `attribute_requirements`, déconnexion par canal arrière |

## Questions probables sur les choix de sécurité (4 minutes)

- **Pourquoi Matrix ?** Protocole éprouvé et ouvert, groupes et fichiers chiffrés, client web complet, auto-hébergeable. Aucune crypto maison.
- **Que voit le serveur ?** Qui parle dans quelle salle, quand, la taille ; pas le contenu (note de sécurité, section 3).
- **Que se passe-t-il si un téléphone est volé ?** L'administrateur révoque : accès serveur coupé en quelques secondes. Les messages déjà stockés sur l'appareil restent une limite assumée (chiffrement du disque, expiration des messages).
- **Un administrateur du serveur peut-il lire les messages ?** Non. Il peut gérer les comptes et voir les métadonnées. Le risque d'ajout d'un appareil malveillant est réduit par la vérification croisée des appareils.
- **Pourquoi des origines séparées pour le portail et Element ?** Une faille du portail ne doit pas donner accès au stockage de clés du navigateur.
- **Qu'est-ce qui n'est pas fait ?** TLS en démonstration, secrets de démo, captures d'écran, effacement à distance (voir limites).
