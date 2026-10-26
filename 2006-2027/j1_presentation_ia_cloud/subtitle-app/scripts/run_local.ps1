# Lance la solution en local, sans Docker : application, console d'administration et worker,
# base SQLite, fichiers et journaux dans .\data.
#
#   powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1                # auto
#   powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -Device cpu
#   powershell -ExecutionPolicy Bypass -File scripts\run_local.ps1 -Device gpu    # GPU NVIDIA
#
# -Device choisit ou tournent les modeles ; le modele par defaut et la taille des lots suivent
# (cpu : whisper-small.en ; gpu : whisper-medium.en). auto = gpu si nvidia-smi repond.
# Arret : Ctrl+C. Relance : meme commande (les traitements en attente sont repris).
# (Fichier sans accents : Windows PowerShell 5.1 le lit en ANSI.)
param(
    [ValidateSet("auto", "cpu", "gpu")]
    [string]$Device = "auto",
    [string]$Models = "",
    [string]$DefaultModel = "",
    [string]$AdminPassword = "admin-local",
    [int]$Port = 8000,
    [int]$AdminPort = 8001
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

# Prend en compte un ffmpeg installe depuis l'ouverture du terminal.
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [Environment]::GetEnvironmentVariable("Path", "User") + ";" + $env:Path

$python = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Environnement .venv absent : python -m venv .venv puis pip install -r requirements-dev.txt"
}
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)) {
    throw "ffmpeg introuvable : winget install Gyan.FFmpeg"
}
if (-not (Test-Path "models\opus-mt-en-fr\model.bin")) {
    Write-Warning "Pas de traduction : dossier models\opus-mt-en-fr absent (voir README, scripts\convert_translation_model.py)."
}

# Lance une commande externe en silence et dit si elle a reussi. (Avec
# ErrorActionPreference = Stop, sa sortie d'erreur interromprait le script.)
function Test-Command([scriptblock]$Command) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try { & $Command *> $null; return $LASTEXITCODE -eq 0 }
    catch { return $false }
    finally { $ErrorActionPreference = $previous }
}

function Test-NvidiaGpu {
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) { return $false }
    return Test-Command { nvidia-smi --query-gpu=name --format=csv,noheader }
}

if ($Device -eq "auto") {
    $Device = if (Test-NvidiaGpu) { "gpu" } else { "cpu" }
}
if ($Device -eq "gpu") {
    if (-not (Test-NvidiaGpu)) {
        throw "-Device gpu : aucun GPU NVIDIA detecte (nvidia-smi). Installez le pilote NVIDIA ou lancez avec -Device cpu."
    }
    if (-not (Test-Command { & $python -c "import importlib.util as u, sys; sys.exit(0 if u.find_spec('nvidia.cudnn') and u.find_spec('nvidia.cublas') else 1)" })) {
        throw "-Device gpu : bibliotheques CUDA absentes du .venv. Lancez : .venv\Scripts\python -m pip install -r requirements-gpu.txt"
    }
}
else {
    # CPU : l'inference utilise tous les coeurs physiques.
    if (-not $env:CPU_THREADS) {
        $env:CPU_THREADS = (Get-CimInstance Win32_Processor | Measure-Object NumberOfCores -Sum).Sum
    }
}

if (-not $Models) {
    $Models = if ($Device -eq "gpu") {
        "whisper-medium.en,whisper-medium,whisper-small.en,whisper-small"
    } else {
        "whisper-small.en,whisper-small,whisper-medium.en"
    }
}

$env:DEVICE = $Device
$env:ENABLED_MODELS = $Models
$env:DEFAULT_MODEL = $DefaultModel   # vide = choisi selon -Device
$env:ADMIN_PASSWORD = $AdminPassword
$env:API_URL = "http://127.0.0.1:$Port"
$env:PYTHONUNBUFFERED = "1"
$env:HF_HUB_DISABLE_SYMLINKS_WARNING = "1"

# Trois processus independants : la console d'administration reste disponible si
# l'application ou le worker s'arrete, et un processus qui s'arrete est relance.
$services = [ordered]@{
    admin  = "-m", "uvicorn", "app.admin:create_app", "--factory", "--port", $AdminPort, "--log-level", "warning"
    api    = "-m", "uvicorn", "app.api:create_app", "--factory", "--port", $Port, "--log-level", "warning"
    worker = "-m", "app.worker"
}
$processes = @{}
Write-Host "Materiel       : $($Device.ToUpper())"
Write-Host "Application    : http://localhost:$Port"
Write-Host "Administration : http://localhost:$AdminPort (mot de passe : $AdminPassword)"
try {
    while ($true) {
        foreach ($name in $services.Keys) {
            $process = $processes[$name]
            if ($process -and -not $process.HasExited) { continue }
            if ($process) { Write-Warning "Le service '$name' ne tourne plus : relance." }
            $processes[$name] = Start-Process -FilePath $python -ArgumentList $services[$name] -NoNewWindow -PassThru
        }
        Start-Sleep -Seconds 5
    }
}
finally {
    $processes.Values | Where-Object { -not $_.HasExited } | ForEach-Object { Stop-Process -Id $_.Id -Force }
}
