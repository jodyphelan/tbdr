#!/bin/bash

set -u

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR" || exit 1

fail() {
    echo
    echo "tbdr could not be started: $1"
    echo
    read -r -p "Press Return to close this window..." _
    exit 1
}

if ! command -v docker >/dev/null 2>&1; then
    fail "Docker Desktop is not installed or the docker command is not on PATH."
fi

if ! docker compose version >/dev/null 2>&1; then
    fail "Docker Compose v2 is unavailable. Update Docker Desktop and try again."
fi

if ! docker info >/dev/null 2>&1; then
    if [ -d "/Applications/Docker.app" ]; then
        echo "Starting Docker Desktop..."
        open -a Docker
    else
        fail "Docker Desktop is not running, and /Applications/Docker.app was not found."
    fi

    ready=0
    for _ in $(seq 1 120); do
        if docker info >/dev/null 2>&1; then
            ready=1
            break
        fi
        sleep 1
    done
    [ "$ready" -eq 1 ] || fail "Docker Desktop did not become ready within two minutes."
fi

if [ ! -f .env ]; then
    [ -f .env.example ] || fail "The .env.example file is missing."
    cp .env.example .env || fail "Could not create .env from .env.example."

    command -v openssl >/dev/null 2>&1 || fail "openssl is required to generate local secrets."
    db_password="$(openssl rand -hex 32)" || fail "Could not generate a PostgreSQL password."
    secret_key="$(openssl rand -hex 32)" || fail "Could not generate an application secret key."
    sed -i '' "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$db_password|" .env
    sed -i '' "s|^TBDR_SECRET_KEY=.*|TBDR_SECRET_KEY=$secret_key|" .env

    echo "Created .env with generated local secrets."
    echo "Review .env now if you want to change the port, resources, or sample visibility."
    read -r -p "Press Return to continue starting tbdr..." _
fi

rebuild=0
offline=0
for argument in "$@"; do
    case "$argument" in
        --rebuild) rebuild=1 ;;
        --offline) offline=1 ;;
        *) fail "Unknown option: $argument (use --offline or --rebuild)." ;;
    esac
done

if [ -f images.tar ]; then
    offline=1
fi

compose_args=(-f docker-compose.yml)
if [ "$offline" -eq 1 ]; then
    [ -f docker-compose.offline.yml ] || fail "Offline Compose configuration is missing."
    [ -f images.tar ] || fail "Offline image archive images.tar is missing."
    compose_args+=(-f docker-compose.offline.yml)
    echo "Loading offline Docker images..."
    docker load --input images.tar || fail "Could not load the offline Docker images."
    docker image inspect tbdr-web:offline tbdr-postgres:offline tbdr-redis:offline \
        >/dev/null 2>&1 || fail "The offline image archive is incomplete."
fi

if [ "$offline" -eq 1 ]; then
    echo "Starting tbdr in offline mode..."
    docker compose "${compose_args[@]}" up -d || fail "Docker Compose could not start the offline services."
elif [ "$rebuild" -eq 1 ] || [ -z "$(docker compose "${compose_args[@]}" images -q web 2>/dev/null)" ]; then
    echo "Building and starting tbdr..."
    docker compose "${compose_args[@]}" up --build -d || fail "Docker Compose could not build or start the services."
else
    echo "Starting tbdr..."
    docker compose "${compose_args[@]}" up -d || fail "Docker Compose could not start the services."
fi

web_port="$(awk -F= '$1 == "TBDR_WEB_PORT" {print $2}' .env | tail -n 1)"
web_port="${web_port:-8000}"
url="http://localhost:${web_port}"

echo "Waiting for tbdr at $url ..."
healthy=0
for _ in $(seq 1 180); do
    if curl --silent --fail --output /dev/null "$url/healthz"; then
        healthy=1
        break
    fi
    sleep 1
done

if [ "$healthy" -ne 1 ]; then
    docker compose "${compose_args[@]}" ps
    echo
    echo "Recent web/worker/init-db logs:"
    docker compose "${compose_args[@]}" logs --tail=50 web worker init-db
    fail "The tbdr health check did not succeed within three minutes."
fi

echo "tbdr is ready. Opening $url"
open "$url"
