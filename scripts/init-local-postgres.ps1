# Create govbid role/database and apply schema on local Windows PostgreSQL.
# Usage (PowerShell, from repo root):
#   .\scripts\init-local-postgres.ps1
#
# Requires: psql on PATH (installed with PostgreSQL). Run as a user that can
# connect as the postgres superuser (you will be prompted for that password).

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$EnvFile = Join-Path $RepoRoot ".env"
$MigrationsDir = Join-Path $RepoRoot "db\migrations"

if (-not (Test-Path $EnvFile)) {
    Write-Error "Missing .env — copy .env.example to .env and set POSTGRES_PASSWORD first."
}
if (-not (Test-Path $MigrationsDir)) {
    Write-Error "Missing migrations directory: $MigrationsDir"
}

$vars = @{}
Get-Content $EnvFile | ForEach-Object {
    if ($_ -match '^\s*#' -or $_ -notmatch '=') { return }
    $k, $v = $_ -split '=', 2
    $vars[$k.Trim()] = $v.Trim().Trim('"')
}

$pgUser = if ($vars["POSTGRES_USER"]) { $vars["POSTGRES_USER"] } else { "govbid" }
$pgPass = $vars["POSTGRES_PASSWORD"]
$pgDb   = if ($vars["POSTGRES_DB"]) { $vars["POSTGRES_DB"] } else { "govbid" }

if (-not $pgPass -or $pgPass -match 'change_me') {
    Write-Error "Set POSTGRES_PASSWORD in .env before running this script."
}

$psql = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psql) {
    Write-Error "psql not found on PATH. Add PostgreSQL bin to PATH or open 'SQL Shell (psql)' from Start."
}

Write-Host "This will create role '$pgUser', database '$pgDb', and apply all db/migrations/*.sql"
Write-Host ""

$postgresPassword = Read-Host "PostgreSQL superuser (postgres) password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($postgresPassword)
$postgresPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)

$env:PGPASSWORD = $postgresPlain
$createSql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$pgUser') THEN
    CREATE ROLE $pgUser LOGIN PASSWORD '$($pgPass -replace "'", "''")';
  ELSE
    ALTER ROLE $pgUser WITH PASSWORD '$($pgPass -replace "'", "''")';
  END IF;
END
`$`$;
SELECT 'CREATE DATABASE $pgDb OWNER $pgUser'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$pgDb')\gexec
GRANT ALL PRIVILEGES ON DATABASE $pgDb TO $pgUser;
"@

$createSql | & psql -U postgres -h localhost -v ON_ERROR_STOP=1
if ($LASTEXITCODE -ne 0) {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    exit $LASTEXITCODE
}
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

$env:PGPASSWORD = $pgPass
$code = 0
foreach ($migration in Get-ChildItem (Join-Path $MigrationsDir "*.sql") | Sort-Object Name) {
    Write-Host "Applying $($migration.Name)..."
    & psql -U $pgUser -h localhost -d $pgDb -v ON_ERROR_STOP=1 -f $migration.FullName
    if ($LASTEXITCODE -ne 0) {
        $code = $LASTEXITCODE
        break
    }
}
Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue

if ($code -eq 0) {
    Write-Host ""
    Write-Host "Done. Database '$pgDb' is ready."
    Write-Host "  psql -U $pgUser -h localhost -d $pgDb"
    Write-Host "  Or connect in pgAdmin with those credentials."
} else {
    exit $code
}
