$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

$objectRoot = 'data/object_store'
$backupRoot = 'data/object_store_backup'
$database = 'data/platform/annapurna.duckdb'
$landSql = 'data/platform/land.sql'
$checkSql = 'data/platform/idempotence_check.sql'
$record = 'data/platform/idempotence_runs.csv'

Remove-Item $backupRoot -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $backupRoot | Out-Null

if (Test-Path "$objectRoot/sales") {
    Move-Item "$objectRoot/sales" "$backupRoot/sales"
}
if (Test-Path "$objectRoot/manifest") {
    Move-Item "$objectRoot/manifest" "$backupRoot/manifest"
}
New-Item -ItemType Directory -Force -Path "$objectRoot/sales", "$objectRoot/manifest" | Out-Null

try {
    & duckdb $database -c ".read $landSql"
    if ($LASTEXITCODE -ne 0) {
        throw "DuckDB landing failed with exit code $LASTEXITCODE"
    }

    & powershell -NoProfile -ExecutionPolicy Bypass -File 'data/platform/upload_minio.ps1'
    if ($LASTEXITCODE -ne 0) {
        throw "MinIO upload failed with exit code $LASTEXITCODE"
    }

    Remove-Item $backupRoot -Recurse -Force
}
catch {
    Remove-Item "$objectRoot/sales" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "$objectRoot/manifest" -Recurse -Force -ErrorAction SilentlyContinue
    if (Test-Path "$backupRoot/sales") {
        Move-Item "$backupRoot/sales" "$objectRoot/sales"
    }
    if (Test-Path "$backupRoot/manifest") {
        Move-Item "$backupRoot/manifest" "$objectRoot/manifest"
    }
    Remove-Item $backupRoot -Recurse -Force -ErrorAction SilentlyContinue
    throw
}

if (-not (Test-Path $record)) {
    Set-Content $record 'run,row_count,checksum'
}
$runNumber = ((Get-Content $record | Select-Object -Skip 1).Count) + 1
$check = & duckdb $database -csv -c ".read $checkSql" | Select-Object -Last 1
Add-Content $record "$runNumber,$check"
Write-Output "run=$runNumber,$check"