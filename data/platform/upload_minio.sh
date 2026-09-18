#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
MC_CONFIG_VOLUME="setubid-mc-config"

# Use the existing MinIO service and mirror the current landing prefix.
docker volume create "$MC_CONFIG_VOLUME" >/dev/null
docker run --rm --network host \
  -v "$MC_CONFIG_VOLUME:/root/.mc" \
  quay.io/minio/mc alias set local http://127.0.0.1:9000 setubid setubid-secret

docker run --rm --network host \
  -v "$MC_CONFIG_VOLUME:/root/.mc" \
  quay.io/minio/mc mb --ignore-existing local/annapurna

docker run --rm --network host \
  -v "$MC_CONFIG_VOLUME:/root/.mc" \
  quay.io/minio/mc rm --recursive --force local/annapurna/sales/

docker run --rm --network host \
  -v "$MC_CONFIG_VOLUME:/root/.mc" \
  -v "$REPO_ROOT/data/object_store/sales:/src:ro" \
  quay.io/minio/mc cp --recursive --quiet /src/ local/annapurna/sales/

echo "Uploaded data/object_store/sales to s3://annapurna/sales/"
