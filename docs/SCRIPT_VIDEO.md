# Script de la vidéo de démonstration (3 minutes maximum)

La vidéo doit montrer : un **échange chiffré entre deux agents**, la **révocation d'un agent** et la **fonctionnalité innovante**. Viser 2 min 50 pour garder une marge sous les 3 minutes.

## Préparation (à faire avant d'enregistrer)

- `docker compose down -v` puis `docker compose up -d --build`, attendre que tout soit `healthy`.
- Deux profils de navigateur côte à côte (Chrome et une fenêtre privée), fenêtres à moitié d'écran : à gauche l'agent **Awa**, à droite l'agent **Ibrahim**. Un troisième onglet pour le portail (`admin.si`). Un terminal avec police agrandie.
- Pré-connecter `awa.ouedraogo`, `ibrahim.sawadogo` et `moussa.traore` (TOTP déjà créé) pour ne pas perdre de temps ; enrôler en direct seulement un nouvel agent.
- Enregistrer en 1080p avec OBS, voix posée, une seule prise par séquence. Montage simple (coupes). Sous-titres français conseillés.

## Déroulé

| Temps | Image | Voix (à adapter avec vos mots) |
|---|---|---|
| 0:00 à 0:15 | Schéma d'architecture du README, puis nom Sentinelle | « Les agents publics échangent des informations sensibles sur des messageries qui échappent à l'État. Voici Sentinelle : une messagerie souveraine, chiffrée de bout en bout, que l'on installe en une commande. » |
| 0:15 à 0:40 | Portail, **Agents**, **Enrôler** un agent (nom, ministère, fonction), mot de passe provisoire affiché | « L'administrateur enrôle un agent par ministère et par fonction. Seuls les agents enrôlés existent : pas d'inscription libre. » |
| 0:40 à 1:00 | Première connexion de ce nouvel agent : SSO, changement de mot de passe, QR code TOTP | « À la première connexion, le second facteur est obligatoire. Pas de code, pas d'accès. » |
| 1:00 à 1:40 | Awa écrit à Ibrahim dans un groupe, envoie un message `TEMOIN-7421` et un PDF ; l'icône **Chiffré de bout en bout** visible ; Ibrahim répond | « Awa et Ibrahim échangent un message et un fichier. Tout est chiffré dans le navigateur, avec le protocole Matrix : nous n'avons écrit aucune cryptographie. » |
| 1:40 à 2:00 | Terminal : `docker compose --profile outils run --rm verifier TEMOIN-7421`, résultat **REUSSI** | « Preuve : on inspecte la base et les fichiers du serveur comme un administrateur le ferait. Aucun message, aucun fichier lisible. Le serveur ne lit rien. » |
| 2:00 à 2:30 | Moussa dans le groupe ; dans le portail **Révoquer** Moussa ; étapes vérifiées et durée ; l'écran de Moussa se déconnecte ; Awa écrit, Moussa ne reçoit plus | « Un agent quitte l'administration, ou perd son téléphone. Un clic : compte désactivé, appareils supprimés, retiré des groupes, puis vérification. Il perd l'accès à l'instant, sur tous ses appareils. » |
| 2:30 à 2:55 | Portail **Canaux** : créer un canal *Confidentiel* du ministère ; invitation reçue dans Element ; mention de l'expiration automatique ; page **Conformité** | « Notre innovation : des canaux institutionnels classifiés. Chiffrés dès leur création, sur invitation, avec expiration automatique des messages côté serveur, et un tableau de conformité du second facteur. » |
| 2:55 à 3:00 | Dépôt GitHub (licence AGPL-3.0) | « Open source, auto-hébergé, sans service tiers. Sentinelle, par l'équipe Harmattan. » |

## À éviter

- Montrer des mots de passe réels, des comptes personnels ou des données réelles : seuls des comptes fictifs.
- Dépasser 3 minutes : le jury peut arrêter la lecture.
- Promettre ce que le prototype ne fait pas (captures d'écran bloquées, effacement à distance).
