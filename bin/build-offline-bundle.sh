#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

fail() {
    echo "Offline bundle build failed: $1" >&2
    exit 1
}

command -v docker >/dev/null 2>&1 || fail "Docker Desktop is required."
docker info >/dev/null 2>&1 || fail "Docker Desktop is not running."
docker compose version >/dev/null 2>&1 || fail "Docker Compose v2 is required."

BUNDLE_VERSION="${BUNDLE_VERSION:-$(date +%Y%m%d%H%M%S)}"
OUTPUT_PATH="${1:-$ROOT_DIR/tbdr-offline-bundle-${BUNDLE_VERSION}.tar.gz}"
WORK_DIR="$(mktemp -d -t tbdr-offline-bundle.XXXXXX)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "Building tbdr-web:offline for linux/amd64..."
docker build --platform linux/amd64 --tag tbdr-web:offline .

echo "Pulling PostgreSQL and Redis for linux/amd64..."
docker pull --platform linux/amd64 postgres:16-alpine
docker pull --platform linux/amd64 redis:7-alpine
docker tag postgres:16-alpine tbdr-postgres:offline
docker tag redis:7-alpine tbdr-redis:offline

STAGING_DIR="$WORK_DIR/tbdr-offline-bundle"
mkdir -p "$STAGING_DIR"
docker save --output "$STAGING_DIR/images.tar" \
    tbdr-web:offline tbdr-postgres:offline tbdr-redis:offline

cp docker-compose.yml docker-compose.offline.yml .env.example README.md \
    "$STAGING_DIR/"
cp "launch-tbdr-macOS.command" "$STAGING_DIR/"
chmod +x "$STAGING_DIR/launch-tbdr-macOS.command"
mkdir -p "$STAGING_DIR/tests"
cp tests/test_launcher.sh "$STAGING_DIR/tests/"

mkdir -p "$(dirname "$OUTPUT_PATH")"
tar -czf "$OUTPUT_PATH" -C "$WORK_DIR" "tbdr-offline-bundle"
echo "Created $OUTPUT_PATH"
echo "Transfer and extract this archive on the target Mac, then run launch-tbdr-macOS.command."
