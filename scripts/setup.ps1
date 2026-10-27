# Zien Crypto - Automated Setup & Health Check Script (PowerShell)
$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   ZIEN CRYPTO // QUANTITATIVE TERMINAL SETUP" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python
try {
    $pyVer = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
    Write-Host "[OK] Python detected: $pyVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python 3.12+ is required but not found in PATH." -ForegroundColor Red
    exit 1
}

# 2. Check Directories
$dirs = @("cryptoscope/static", "cryptoscope/tests", "work/runtime", "work/backups")
foreach ($d in $dirs) {
    if (-not (Test-Path $d)) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }
}
Write-Host "[OK] Runtime directories validated." -ForegroundColor Green

# 3. Check Ollama Model
try {
    $models = ollama list
    if ($models -match "laya-crypto") {
        Write-Host "[OK] Ollama model 'laya-crypto:latest' is registered and ready." -ForegroundColor Green
    } else {
        Write-Host "[INFO] Creating Ollama model 'laya-crypto:latest' from Modelfile..." -ForegroundColor Yellow
        ollama create laya-crypto:latest -f Modelfile
        Write-Host "[OK] Ollama model created successfully." -ForegroundColor Green
    }
} catch {
    Write-Host "[WARN] Ollama CLI not detected or unreachable. Rule-based fallback active." -ForegroundColor Yellow
}

# 4. Run Doctor
Write-Host "`nRunning system diagnostic doctor..." -ForegroundColor Cyan
python cryptoscope/manage.py doctor

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "   Setup complete! Launch with:" -ForegroundColor Cyan
Write-Host "   python server.py --port 8900" -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Cyan
