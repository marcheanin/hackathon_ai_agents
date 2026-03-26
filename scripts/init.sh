#!/bin/bash
set -e

echo "=== Система Генерации ИИ Агентов — Инициализация ==="

cd "$(dirname "$0")/.."

# 1. Поднимаем инфраструктуру
echo ">> Запуск инфраструктуры (Postgres, Redis, Qdrant)..."
docker compose up -d postgres redis qdrant

# 2. Ждём healthcheck'и
echo ">> Ожидание готовности инфраструктуры..."
for svc in postgres redis qdrant; do
    echo -n "   $svc: "
    timeout=60
    while [ $timeout -gt 0 ]; do
        if docker compose ps "$svc" | grep -q "(healthy)"; then
            echo "OK"
            break
        fi
        sleep 2
        timeout=$((timeout - 2))
    done
    if [ $timeout -le 0 ]; then
        echo "TIMEOUT — $svc не стал healthy за 60 секунд"
        exit 1
    fi
done

# 3. Билдим и запускаем все сервисы
echo ">> Сборка и запуск всех сервисов..."
docker compose up -d --build

echo ">> Ожидание запуска сервисов (15 сек)..."
sleep 15

# 4. Health checks
echo ">> Проверка health endpoints..."
for url in \
    "http://localhost:8000/health" \
    "http://localhost:8010/health" \
    "http://localhost:8020/health" \
    "http://localhost:8030/api/v1/health" \
    "http://localhost:8040/health"; do
    echo -n "   $url: "
    if curl -sf "$url" > /dev/null 2>&1; then
        echo "OK"
    else
        echo "FAIL (сервис может ещё запускаться)"
    fi
done

echo ""
echo "=== Инициализация завершена ==="
echo "Оркестратор:  http://localhost:8000"
echo "Аналитик:     http://localhost:8010"
echo "МВАЛ:         http://localhost:8020"
echo "Архитектор:   http://localhost:8030"
echo "Реализация:   http://localhost:8040"
echo ""
echo "Тест пайплайна:"
echo '  curl -X POST http://localhost:8000/pipeline -H "Content-Type: application/json" -d '\''{"message": "Нужен агент для обработки email"}'\'''
