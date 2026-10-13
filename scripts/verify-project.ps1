$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/5] Checking Docker Compose configuration..."
docker compose config --quiet

Write-Host "[2/5] Checking Python syntax..."
Push-Location (Join-Path $root 'services/api')
try {
  python -m compileall -q app tests manage.py celery_worker.py wsgi.py
  if ($LASTEXITCODE -ne 0) { throw "Python compile check failed." }
} finally { Pop-Location }

Write-Host "[3/5] Checking migration chain..."
$migrations = Get-ChildItem (Join-Path $root 'services/api/migrations/versions') -Filter '*.py' | Sort-Object Name
if ($migrations.Count -lt 2) { throw "Migration files not found." }
$latest = Get-Content $migrations[-1].FullName -Raw
if ($latest -notmatch 'revision\s*=\s*["'']0010["'']') { Write-Warning "Latest filename-sorted migration is not revision 0010; inspect migration graph manually." }

Write-Host "[4/5] Checking frontend dependencies/build..."
if (-not (Test-Path (Join-Path $root 'web/node_modules'))) {
  Write-Warning "web/node_modules is absent. Run 'cd web; npm install' before building."
} else {
  Push-Location (Join-Path $root 'web')
  try { npm run build; if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." } }
  finally { Pop-Location }
}

Write-Host "[5/5] Static checks finished. Runtime integration is separate."
Write-Host "Next: docker compose up --build -d; docker compose exec api pytest -v; follow PILOT_E2E_CHECKLIST.md."
