$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $repoRoot

docker volume create setubid-mc-config | Out-Null
docker run --rm --network host -v setubid-mc-config:/root/.mc quay.io/minio/mc alias set local http://127.0.0.1:9000 setubid setubid-secret
docker run --rm --network host -v setubid-mc-config:/root/.mc quay.io/minio/mc mb --ignore-existing local/annapurna
docker run --rm --network host -v setubid-mc-config:/root/.mc quay.io/minio/mc rm --recursive --force local/annapurna/sales/
docker run --rm --network host -v setubid-mc-config:/root/.mc -v "${repoRoot}/data/object_store/sales:/src:ro" quay.io/minio/mc cp --recursive --quiet /src/ local/annapurna/sales/