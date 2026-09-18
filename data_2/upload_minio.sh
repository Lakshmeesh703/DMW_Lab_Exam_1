#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MC_CONFIG_VOLUME="setubid-mc-config"

# Use the SetuBid MinIO service and mirror the notice shards.
docker volume create "$MC_CONFIG_VOLUME" >/dev/null
docker run --rm --network host \
  -v "$MC_CONFIG_VOLUME:/root/.mc" \
  quay.io/minio/mc alias set local http://127.0.0.1:9000 setubid setubid-secret

docker run --rm --network host \
  -v "$MC_CONFIG_VOLUME:/root/.mc" \
  quay.io/minio/mc mb --ignore-existing local/setubid

docker run --rm --network host \
  -v "$MC_CONFIG_VOLUME:/root/.mc" \
  quay.io/minio/mc rm --recursive --force local/setubid/notices/

docker run --rm --network host \
  -v "$MC_CONFIG_VOLUME:/root/.mc" \
  -v "$REPO_ROOT/data_2/notices:/src:ro" \
  quay.io/minio/mc cp --recursive --quiet /src/ local/setubid/notices/

echo "Uploaded data_2/notices to s3://setubid/notices/"
