#!/usr/bin/env bash
set -e

# Run Flyway migrations using official Flyway docker container
echo "Running Flyway migrations against PostgreSQL..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

docker compose -f "$PROJECT_ROOT/docker-compose.yml" run --rm flyway migrate

echo "Flyway migrations applied successfully!"
