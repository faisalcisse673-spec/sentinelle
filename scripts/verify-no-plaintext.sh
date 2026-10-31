#!/bin/sh
# Preuve « le serveur ne lit rien » (epreuve en direct du jury).
#
# Usage (depuis la racine du depot) :
#   1. Dans Element, envoyez un message contenant un mot temoin unique, par ex. TEMOIN-7421
#      (et/ou joignez un fichier : PDF, image...).
#   2. docker compose --profile outils run --rm verifier TEMOIN-7421
#
# Le script lit la base PostgreSQL de Synapse et le stockage des medias, exactement comme le ferait
# un administrateur du serveur, et echoue si un message ou un fichier apparait en clair.
CANARY="$1"
if [ -z "$CANARY" ]; then
  echo "Usage : docker compose --profile outils run --rm verifier MOT-TEMOIN"
  exit 2
fi

FAIL=0
ok() { echo "  [OK]     $1"; }
ko() { echo "  [ECHEC]  $1"; FAIL=1; }
q() { psql -At -c "$1"; }

echo
echo "=== Verification : le serveur ne lit rien ==="
echo "Mot temoin recherche : $CANARY"

echo
echo "1) Ce que le serveur stocke comme evenements (type : nombre)"
psql -At -F ' : ' -c "SELECT type, count(*) FROM events GROUP BY type ORDER BY 2 DESC LIMIT 12;" | sed 's/^/     /'

PLAIN=$(q "SELECT count(*) FROM events WHERE type='m.room.message';")
CIPHER=$(q "SELECT count(*) FROM events WHERE type='m.room.encrypted';")
echo
echo "2) Messages"
if [ "$PLAIN" = "0" ]; then ok "aucun message en clair (m.room.message : 0)"; else ko "$PLAIN message(s) en clair dans la base"; fi
echo "     messages chiffres stockes (m.room.encrypted) : $CIPHER"
if [ "$CIPHER" = "0" ]; then echo "     (aucun message encore envoye : envoyez-en un dans Element puis relancez)"; fi

echo
echo "3) Salles sans chiffrement"
UNENC=$(q "SELECT count(*) FROM rooms r WHERE NOT EXISTS (SELECT 1 FROM current_state_events c WHERE c.room_id = r.room_id AND c.type = 'm.room.encryption');")
if [ "$UNENC" = "0" ]; then ok "toutes les salles sont chiffrees de bout en bout"; else ko "$UNENC salle(s) sans chiffrement"; fi

echo
echo "4) Recherche du mot temoin dans TOUTE la base (export complet)"
HITS=$(pg_dump --no-owner --no-privileges 2>/dev/null | grep -c -F -- "$CANARY")
if [ "$HITS" = "0" ]; then ok "mot temoin absent de la base"; else ko "mot temoin trouve $HITS fois dans la base"; fi

echo
echo "5) Fichiers du stockage des medias"
MEDIA=/synapse-data/media_store
if [ -d "$MEDIA" ]; then
  TOTAL=$(find "$MEDIA" -type f | wc -l)
  FOUND=$(grep -rlF -- "$CANARY" "$MEDIA" 2>/dev/null | wc -l)
  CLEAR=0
  for f in $(find "$MEDIA" -type f); do
    magic=$(head -c 4 "$f" | od -An -tx1 | tr -d ' \n')
    case "$magic" in
      25504446|89504e47|ffd8ffe0|ffd8ffe1|ffd8ffdb|47494638|504b0304)
        CLEAR=$((CLEAR + 1)); echo "     fichier lisible en clair : $f" ;;
    esac
  done
  echo "     fichiers stockes : $TOTAL"
  if [ "$FOUND" = "0" ]; then ok "mot temoin absent des fichiers"; else ko "mot temoin trouve dans $FOUND fichier(s)"; fi
  if [ "$CLEAR" = "0" ]; then ok "aucun PDF, image ou archive lisible en clair"; else ko "$CLEAR fichier(s) lisible(s) en clair (PDF, image, archive)"; fi
else
  echo "     (aucun fichier envoye pour l'instant)"
fi

echo
if [ "$FAIL" = "0" ]; then
  echo "RESULTAT : REUSSI. Le serveur ne contient aucun message ni fichier en clair."
else
  echo "RESULTAT : ECHEC. Voir les lignes [ECHEC] ci-dessus."
fi
echo "Rappel : les noms et sujets de salles ne sont pas chiffres dans Matrix (voir docs/NOTE_SECURITE.md)."
exit $FAIL
