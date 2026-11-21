$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:LC_ALL = 'English_United States.utf8'
$env:PYTHONIOENCODING = 'utf-8'
try {
    & .\.venv\Scripts\python.exe scripts/service_manager.py
    if ($LASTEXITCODE -ne 0) {
        Read-Host 'Startup failed. Read the error above. Press Enter to close'
    }
} catch {
    Write-Host $_ -ForegroundColor Red
    Read-Host 'Press Enter to close'
}
