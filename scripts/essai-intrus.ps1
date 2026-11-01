# Essai "Intrus" : prouve qu'une personne non enrolee ne peut pas entrer.
# Usage (PowerShell, pile demarree) : .\scripts\essai-intrus.ps1
$base = "http://matrix.localhost:8080"
$ok = $true

function Verifier($nom, $attendu, $obtenu) {
    if ($obtenu) { Write-Host "[OK]    $nom : $attendu" -ForegroundColor Green }
    else { Write-Host "[ECHEC] $nom : $attendu non constate" -ForegroundColor Red; $script:ok = $false }
}

# 1. Inscription directe refusee
$r = curl.exe -s -X POST "$base/_matrix/client/v3/register" -H "Content-Type: application/json" -d "{}"
Verifier "1. Inscription directe" "refusee (inscription desactivee)" ($r -match "Registration has been disabled")

# 2. Seule la connexion SSO est proposee, aucun mot de passe Matrix
$flows = curl.exe -s "$base/_matrix/client/v3/login"
Verifier "2a. Methodes de connexion" "SSO propose, mot de passe absent" (($flows -match "m.login.sso") -and ($flows -notmatch "m.login.password"))

$tmp = New-TemporaryFile
'{"type":"m.login.password","identifier":{"type":"m.id.user","user":"awa.ouedraogo"},"password":"Sentinelle#Demo2026"}' | Out-File -Encoding ascii $tmp
$r = curl.exe -s -X POST "$base/_matrix/client/v3/login" -H "Content-Type: application/json" --data-binary "@$tmp"
Remove-Item $tmp
Verifier "2b. Connexion par mot de passe" "refusee, aucun jeton" (($r -match "Password login has been disabled") -and ($r -notmatch "access_token"))

# 3. API d'administration non exposee
$code = curl.exe -s -o NUL -w "%{http_code}" "$base/_synapse/admin/v2/users"
Verifier "3. API d'administration" "inaccessible (code $code)" ($code -eq "403" -or $code -eq "404")

Write-Host ""
Write-Host "4. A faire a la main : fenetre privee, http://admin.localhost:8080, connexion en agent simple : 'Acces refuse' attendu."
if ($ok) { Write-Host "RESULTAT : REUSSI" -ForegroundColor Green } else { Write-Host "RESULTAT : ECHEC" -ForegroundColor Red; exit 1 }
