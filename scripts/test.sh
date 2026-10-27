#!/usr/bin/env bash
set -euo pipefail

COMPOSE="docker compose -f docker-compose.test.yml"

# Убираем мусор, если остался
$COMPOSE down -v --remove-orphans >/dev/null 2>&1 || true

# 1. Поднимаем только БД
echo "=== 1. Start DB ==="
$COMPOSE up -d test_db

# 2. Прогоняем миграции
echo "=== 2. Run migrations ==="
$COMPOSE run --rm test_migrations

# 3. Запускаем тесты (run --rm покажет все логи pytest в терминале!)
echo "=== 3. Run tests ==="
$COMPOSE run --rm tests
EXIT_CODE=$?

# 4. Убираем за собой
$COMPOSE down -v --remove-orphans >/dev/null 2>&1 || true

exit $EXIT_CODE