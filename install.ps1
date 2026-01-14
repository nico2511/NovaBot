# NovaBot - Installation Simplifiée
Write-Host "========================================"
Write-Host "NovaBot - Installation Automatique"
Write-Host "========================================"
Write-Host ""

# Vérifier Python
Write-Host "Verification de Python..."
$pythonVersion = python --version 2>&1
Write-Host "Python trouve: $pythonVersion"
Write-Host ""

# Créer environnement virtuel
Write-Host "Creation de l'environnement virtuel..."
if (Test-Path "venv") {
    Write-Host "Environnement virtuel existe deja"
    $response = Read-Host "Voulez-vous le recreer? (o/N)"
    if ($response -eq "o") {
        Remove-Item -Recurse -Force venv
        python -m venv venv
        Write-Host "Environnement virtuel recree"
    }
} else {
    python -m venv venv
    Write-Host "Environnement virtuel cree"
}
Write-Host ""

# Activer environnement
Write-Host "Activation de l'environnement virtuel..."
& .\venv\Scripts\Activate.ps1
Write-Host "Environnement virtuel active"
Write-Host ""

# Mettre à jour pip
Write-Host "Mise a jour de pip..."
python -m pip install --upgrade pip
Write-Host "pip mis a jour"
Write-Host ""

# Installer dépendances
Write-Host "Installation des dependances..."
Write-Host "(Cela peut prendre quelques minutes)"
pip install -r requirements.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "Dependances installees avec succes"
} else {
    Write-Host "Erreur lors de l'installation"
    exit 1
}
Write-Host ""

# Vérifier .env
Write-Host "Verification de la configuration..."
if (Test-Path ".env") {
    Write-Host "Fichier .env trouve"
} else {
    Write-Host "Fichier .env non trouve"
    Write-Host "Creez un fichier .env avec vos configurations"
}
Write-Host ""

# Créer dossiers
Write-Host "Creation des dossiers..."
$folders = @("logs", "data")
foreach ($folder in $folders) {
    if (-not (Test-Path $folder)) {
        New-Item -ItemType Directory -Path $folder | Out-Null
        Write-Host "Dossier '$folder' cree"
    }
}
Write-Host ""

Write-Host "========================================"
Write-Host "Installation terminee avec succes!"
Write-Host "========================================"
Write-Host ""
Write-Host "Prochaines etapes:"
Write-Host "1. Configurez vos cles API dans le fichier .env"
Write-Host "2. Lancez le bot avec: python main_nextjs.py"
Write-Host "3. Accedez au dashboard: http://localhost:3000"
Write-Host ""
