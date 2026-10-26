# Lance la solution avec Docker, en version CPU ou GPU NVIDIA.
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_docker.ps1 -Device cpu
#   powershell -ExecutionPolicy Bypass -File scripts\run_docker.ps1 -Device gpu
#   powershell -ExecutionPolicy Bypass -File scripts\run_docker.ps1 -Stop          # arreter
#   powershell -ExecutionPolicy Bypass -File scripts\run_docker.ps1 -Logs          # journaux
#
# -Device choisit l'image construite (la version gpu embarque les bibliotheques CUDA), donne
# le GPU au worker, et fixe le modele par defaut (cpu : whisper-small.en ; gpu : whisper-medium.en).
# Les donnees (base, fichiers, modeles) sont conservees d'un lancement a l'autre.
# (Fichier sans accents : Windows PowerShell 5.1 le lit en ANSI.)
param(
    [ValidateSet("cpu", "gpu")]
    [string]$Device = "cpu",
    [switch]$Stop,
    [switch]$Logs
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Lance une commande externe en silence et dit si elle a reussi. (Avec
# ErrorActionPreference = Stop, sa sortie d'erreur interromprait le script.)
function Test-Command([scriptblock]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try { & $Command *> $null; return $LASTEXITCODE -eq 0 }
    catch { return $false }
    finally { $ErrorActionPreference = $previous }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker introuvable : installez Docker Desktop (https://docs.docker.com/desktop/) puis relancez."
}
if (-not (Test-Command { docker info })) {
    throw "Docker ne repond pas : demarrez Docker Desktop puis relancez."
}

if ($Stop) { docker compose stop; exit $LASTEXITCODE }
if ($Logs) { docker compose logs -f --tail 100; exit $LASTEXITCODE }

if (-not (Test-Path ".env")) {
    Write-Warning "Pas de fichier .env : valeurs par defaut (mot de passe de base 'subtitle', mot de passe administrateur genere et affiche une fois par 'docker compose logs admin'). Pour un serveur, copiez .env.example en .env et renseignez les secrets."
}

$files = @("-f", "docker-compose.yml")
if ($Device -eq "gpu") {
    $files += "-f", "docker-compose.gpu.yml"
    # Verifie que Docker voit le GPU avant de construire une image de plusieurs Go.
    if (-not (Test-Command { docker run --rm --gpus all hello-world })) {
        throw "-Device gpu : Docker n'a pas acces a un GPU NVIDIA (pilote NVIDIA + WSL 2 sous Windows, NVIDIA Container Toolkit sous Linux). Sinon : -Device cpu."
    }
}

$env:DEVICE = $Device
docker compose @files up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Materiel       : $($Device.ToUpper())"
Write-Host "Application    : http://localhost:8000"
Write-Host "Administration : http://localhost:8001 (compte ADMIN_USERNAME, 'admin' par defaut ; mot de passe ADMIN_PASSWORD, ou genere : docker compose logs admin)"
Write-Host "Etat           : docker compose ps        Journaux : scripts\run_docker.ps1 -Logs"
Write-Host "Le worker telecharge le modele au premier lancement : il est pret quand la console"
Write-Host "d'administration l'affiche 'en service'."
