$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$env:LC_ALL='English_United States.utf8'
if (-not (Test-Path .venv\Scripts\python.exe)) { python -m venv --without-pip .venv }
python -m pip --python .venv\Scripts\python.exe install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
New-Item -ItemType Directory -Force .r-library | Out-Null
$rscript = $env:RSCRIPT_PATH
if (-not $rscript) {
  $rscript = (Get-ChildItem 'C:\Program Files\R\*\bin\Rscript.exe' | Sort-Object FullName -Descending | Select-Object -First 1).FullName
}
& $rscript -e "install.packages(c('plumber','jsonlite','processx','digest','haven','flextable','officer'),lib='.r-library',repos='https://cloud.r-project.org')"
if ($LASTEXITCODE -ne 0) { throw 'R dependency installation failed.' }
