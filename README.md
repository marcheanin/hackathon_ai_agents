# Генератор Агентов — мульти-модульная система генерации AI-агентов

Система **Генератор Агентов (V3)** — полный пайплайн от пользовательского запроса до сгенерированной архитектуры AI-агента. Состоит из 5 модулей, координируемых оркестратором.

## Место в системе V3

```
Клиент → Оркестратор → Аналитик → МВАЛ (REQUEST) → Архитектор → МВАЛ (ARCHITECTURE) → Реализация
                          │            │                │              │
                          ▼            ▼                ▼              ▼
                     PostgreSQL    PostgreSQL        Qdrant         Redis
                     Yandex LLM   Redis           Yandex LLM     Yandex LLM
                                  Yandex LLM      Yandex Emb
```

## Общий стек и зависимости

### Инфраструктура (docker-compose)

| Сервис | Образ | Назначение |
|--------|-------|------------|
| PostgreSQL | `postgres:16-alpine` | БД для Аналитика (`interview`) и МВАЛ (`mval`) |
| Redis | `redis:7-alpine` | Policy Cache для МВАЛ |
| Qdrant | `qdrant/qdrant:latest` | Векторная БД для RAG-паттернов Архитектора |

### Используемые модели

| Модель | Провайдер | Назначение |
|--------|-----------|------------|
| `deepseek-v32/latest` | Yandex Cloud LLM API | LLM для всех модулей (Аналитик, МВАЛ, Архитектор) |
| `text-search-doc/latest` (256 dim) | Yandex Cloud Embeddings API | Эмбеддинги для RAG (Архитектор) |

---

## Модули

### 1. Orchestrator — Оркестратор (порт 8000)

Координирует полный пайплайн: Аналитик → МВАЛ → Архитектор → МВАЛ → Реализация. Поддерживает REST и WebSocket (многошаговый диалог с уточнениями).

| Компонент | Технология |
|-----------|------------|
| Runtime | Python 3.11 |
| API | FastAPI |
| HTTP-клиент | httpx |
| WebSocket | websockets |
| Валидация | Pydantic |

**Внешние зависимости:** нет собственных — вызывает 4 модуля по HTTP.
**Используемые модели:** нет (чистый оркестратор).

---

### 2. Analyst — ИИ Аналитик (порт 8010)

Декомпозиция и конкретизация пользовательского запроса. Многошаговое интервью с уточняющими вопросами.

| Компонент | Технология |
|-----------|------------|
| Runtime | Python 3.11 |
| API | FastAPI |
| Agent framework | LangGraph + LangChain |
| DB-драйвер | asyncpg |
| Логирование | structlog |
| Валидация | Pydantic |
| HTTP-клиент | httpx |

**Внешние зависимости:** PostgreSQL (БД `interview`), Yandex Cloud LLM API, МВАЛ (по HTTP).
**Используемые модели:** `deepseek-v32/latest` через Yandex Cloud OpenAI-compatible API.

---

### 3. МВАЛ — Модуль Валидации (порт 8020 + RedTeam sidecar 8021)

Валидация артефактов между модулями. Включает RedTeam-агент для анализа угроз.

| Компонент | Технология |
|-----------|------------|
| Runtime | Python 3.11 |
| API | FastAPI |
| Agent framework | LangChain |
| DB-драйвер | asyncpg |
| Кэш | redis (hiredis) |
| Логирование | structlog |
| Валидация | Pydantic |
| HTTP-клиент | httpx |

**Внешние зависимости:** PostgreSQL (БД `mval`), Redis, Yandex Cloud LLM API, RedTeam sidecar.
**Используемые модели:** `deepseek-v32/latest` (основной + RedTeam агент).

---

### 4. Architect — ИИ Архитектор (порт 8030)

Проектирует архитектуру AI-агента через декомпозированный мульти-агентный пайплайн (LangGraph) с RAG и retry-loop. Возвращает Mermaid C4 + YAML + JSON.

| Компонент | Технология |
|-----------|------------|
| Runtime | Python 3.11 |
| API | FastAPI |
| Agent framework | LangGraph + LangChain |
| Vector DB клиент | qdrant-client |
| Валидация | Pydantic + pydantic-settings |
| HTTP-клиент | httpx |
| Парсинг паттернов | python-frontmatter, PyYAML |

**Внешние зависимости:** Qdrant (векторная БД), Yandex Cloud LLM API, Yandex Cloud Embeddings API.
**Используемые модели:** `deepseek-v32/latest` (LLM), `text-search-doc/latest` 256 dim (эмбеддинги).

---

### 5. Implementor — Модуль Реализации (порт 8040)

Заглушка. В будущем — генерация кода по архитектуре из БД Шаблонов Кода.

| Компонент | Технология |
|-----------|------------|
| Runtime | Python 3.11 |
| API | FastAPI |
| Валидация | Pydantic |

**Внешние зависимости:** нет.
**Используемые модели:** нет (stub).

## Архитектура пайплайна

Декомпозированный мульти-агентный пайплайн из 6 узлов с retry-loop:

```
START
  │
  ▼
[retrieve_patterns]          ← Qdrant RAG поиск top-K паттернов (1 раз)
  │
  ▼
[select_patterns]            ← LLM: выбор 2-3 паттернов (1 раз)
  │
  ┌──────────────────────────────────────┐
  │         RETRY ZONE (max 3)           │
  ▼                                      │
[design_components]          ← LLM: проектирование компонентов
  │                                      │
  ▼                                      │
[design_integrations]        ← LLM: потоки данных между компонентами
  │                                      │
  ▼                                      │
[synthesize_diagram]         ← Python: Mermaid C4 + YAML (без LLM)
  │                                      │
  ▼                                      │
[validate_architecture]      ← LLM: оценка по 4 критериям
  │                                      │
  ├── approved (score ≥ 0.7) ─────────────────► END (success)
  ├── retry (iter < max) ───────────────┘
  └── max_retries ────────────────────────────► END (max_retries_exceeded)
```

### Узлы

| Узел | Тип | Описание |
|------|-----|----------|
| `retrieve_patterns` | Qdrant | Embed запроса → cosine search top-K паттернов |
| `select_patterns` | LLM | Выбирает 2-3 релевантных паттерна из RAG-результатов |
| `design_components` | LLM (retryable) | Проектирует список компонентов на основе паттернов + feedback |
| `design_integrations` | LLM (retryable) | Определяет потоки данных между компонентами |
| `synthesize_diagram` | Python | Детерминированная генерация Mermaid C4 + YAML |
| `validate_architecture` | LLM | Оценка по 4 критериям (completeness, correctness, applicability, feasibility) |

## HTTP API

### `POST /api/v1/generate`

Генерация архитектуры AI-агента.

**Request:**
```json
{
  "user_request": "Нужен агент для мониторинга цен на маркетплейсах и отправки алертов в Telegram",
  "context": {                     // опционально
    "team_size": 3,
    "tech_stack": ["Python", "Redis"]
  }
}
```

| Поле | Тип | Обязательно | Описание |
|------|-----|:-----------:|----------|
| `user_request` | `string` | да | Описание агента (10–4000 символов) |
| `context` | `object \| null` | нет | Дополнительный контекст (ограничения, стек, команда) |

**Response (200):**
```json
{
  "status": "success",
  "architecture": {
    "title": "Architecture for: Нужен агент для мониторинга цен...",
    "description": "Нужен агент для мониторинга цен...",
    "primary_pattern": "event-driven-architecture",
    "patterns_used": ["event-driven-architecture", "microservices"],
    "components": [
      {
        "id": "price_monitor_agent",
        "name": "Price Monitor Agent",
        "type": "llm_agent",
        "description": "Отслеживает цены на маркетплейсах и обнаруживает снижения",
        "technology": "LangChain",
        "dependencies": ["marketplace_api"]
      }
    ],
    "data_flows": [
      {
        "from_id": "price_monitor_agent",
        "to_id": "event_queue",
        "label": "Publish price drop event",
        "protocol": "AMQP"
      }
    ],
    "mermaid_diagram": "C4Component\n    title ...",
    "yaml_spec": "components:\n  - id: price_monitor_agent\n    ...",
    "deployment_notes": null
  },
  "validation": {
    "approved": true,
    "score": 0.875,
    "scores": {
      "completeness": 0.9,
      "correctness": 0.85,
      "applicability": 0.95,
      "feasibility": 0.8
    },
    "feedback": "Архитектура покрывает все ключевые требования...",
    "issues": ["Missing error handling for Telegram API rate limits"]
  },
  "iterations": 1,
  "request_id": "d368a306-86ce-4f0e-afe3-d142de41da91"
}
```

**Response (500):**
```json
{
  "detail": "Agent pipeline failed: <error message>"
}
```

### `GET /api/v1/health`

Проверка состояния сервиса.

**Response:**
```json
{
  "status": "ok",
  "qdrant": "ok"
}
```

## Контракты данных

### GenerateRequest

```
user_request: string          — описание агента (10–4000 символов)
context: object | null        — дополнительный контекст
```

### GenerateResponse

```
status: "success" | "max_retries_exceeded" | "error"
architecture: ArchitectureDraft | null
validation: ValidationResult | null
iterations: integer           — количество итераций пайплайна
request_id: string            — UUID запроса
```

### ArchitectureDraft

```
title: string                 — заголовок архитектуры
description: string           — исходный запрос
primary_pattern: string       — основной паттерн (например "event-driven-architecture")
patterns_used: string[]       — все применённые паттерны
components: Component[]       — список компонентов
data_flows: DataFlow[]        — потоки данных между компонентами
mermaid_diagram: string       — Mermaid C4Component диаграмма (готова для рендеринга)
yaml_spec: string             — YAML-представление архитектуры
deployment_notes: string | null
```

### Component

```
id: string                    — уникальный ID (snake_case)
name: string                  — человекочитаемое название
type: ComponentType           — тип компонента (enum, см. ниже)
description: string           — что делает компонент
technology: string | null     — конкретная технология (FastAPI, Qdrant, LangGraph)
dependencies: string[]        — id компонентов, от которых зависит
```

**ComponentType** (enum):
```
llm_agent     — LLM-агент
tool          — инструмент/адаптер
memory        — хранилище состояния
orchestrator  — оркестратор
api_gateway   — API-шлюз
database      — база данных
queue         — очередь/брокер сообщений
external      — внешний сервис
```

### DataFlow

```
from_id: string               — id компонента-источника
to_id: string                 — id компонента-получателя
label: string                 — описание данных ("HTTP POST /generate", "query vector + top-K results")
protocol: string | null       — протокол (HTTP, gRPC, AMQP, WebSocket, direct call)
```

### ValidationResult

```
approved: boolean             — одобрена ли архитектура (score >= 0.7)
score: float                  — средний балл (0.0–1.0)
scores: object                — оценки по критериям:
  completeness: float         —   все необходимые компоненты присутствуют
  correctness: float          —   паттерны применены корректно
  applicability: float        —   архитектура решает запрос пользователя
  feasibility: float          —   техническая реализуемость
feedback: string              — текстовая обратная связь
issues: string[]              — конкретные проблемы (пустой список если одобрено)
```

## RAG: база паттернов

Qdrant коллекция `arch_patterns` содержит 8 архитектурных паттернов:

| Паттерн | Описание |
|---------|----------|
| `microservices` | Микросервисная архитектура |
| `event-driven-architecture` | Событийно-ориентированная архитектура |
| `layered-architecture` | Layered (N-Tier) / MVC |
| `cqrs-event-sourcing` | CQRS + Event Sourcing |
| `saga-pattern` | Saga (распределённые транзакции) |
| `hexagonal-architecture` | Гексагональная (Ports & Adapters) |
| `rag-agent` | RAG-based AI Agent |
| `multi-agent-orchestration` | Multi-Agent Orchestration |

Векторы: nomic-embed-text (768 dim), Distance.COSINE.

## Полная инструкция по запуску

### Требования

- Docker + Docker Compose v2
- Ключ API Yandex Cloud (для LLM и эмбеддингов)
- Python 3.11+ (только для ручного seed-скриптов, не обязательно при запуске через Docker)

### Быстрый запуск (одна команда)

```bash
# Клонировать и настроить .env
git clone <repo-url> && cd hackathon_ai_agents
cp .env.example .env   # или отредактировать существующий .env

# Запустить всё через скрипт
chmod +x scripts/init.sh
./scripts/init.sh
```

Скрипт `init.sh` автоматически:
1. Поднимает инфраструктуру (PostgreSQL, Redis, Qdrant)
2. Ждёт healthcheck-ов
3. Собирает и запускает все 6 сервисов
4. Проверяет health endpoints

### Пошаговый запуск

#### Шаг 1. Настроить переменные окружения

Создать файл `.env` в корне проекта:

```env
# Yandex Cloud LLM (обязательно)
YANDEX_API_KEY=<ваш API-ключ Yandex Cloud>
YANDEX_FOLDER_ID=<ваш Folder ID>
YANDEX_BASE_URL=https://llm.api.cloud.yandex.net/v1

# LLM модель
LLM_MODEL_NAME=deepseek-v32/latest

# Embeddings
EMBEDDING_MODEL=text-search-doc/latest
EMBEDDING_DIMENSIONS=256

# PostgreSQL
POSTGRES_PASSWORD=secret

# Qdrant
QDRANT_COLLECTION=arch_patterns
```

#### Шаг 2. Поднять инфраструктуру

```bash
docker compose up -d postgres redis qdrant
```

Дождаться готовности (healthcheck-и настроены автоматически):
```bash
docker compose ps  # все три сервиса должны быть healthy
```

При первом запуске PostgreSQL автоматически выполнит:
- `scripts/init-db.sql` — создание БД `mval` (пользователь `mval`) и `interview`
- `modules/mval/migrations/` — таблица `policy_rules`
- `modules/analyst/migrations/` — таблица `knowledge_documents` + seed-данные

#### Шаг 3. Собрать и запустить сервисы

```bash
docker compose up -d --build
```

Это поднимет 6 контейнеров:

| Сервис | Контейнер | Порт |
|--------|-----------|------|
| Оркестратор | `agents-orchestrator` | 8000 |
| Аналитик | `agents-analyst` | 8010 |
| МВАЛ | `agents-mval` | 8020 |
| МВАЛ RedTeam | `agents-mval-redteam` | 8021 |
| Архитектор | `agents-architect` | 8030 |
| Реализация | `agents-implementor` | 8040 |

#### Шаг 4. Загрузить паттерны в Qdrant (RAG)

Архитектор использует RAG по векторной базе паттернов. Загрузка выполняется из контейнера архитектора:

```bash
docker compose exec architect python scripts/inject_patterns.py
```

Флаг `--recreate` пересоздаст коллекцию, если она уже существует:
```bash
docker compose exec architect python scripts/inject_patterns.py --recreate
```

Загружаются 8 архитектурных паттернов из `modules/architect/scripts/patterns/*.md`.

#### Шаг 5. Загрузить политики валидации в МВАЛ (опционально)

Seed-политики для модуля валидации:

```bash
docker compose exec mval python scripts/seed_policies.py \
  --db-url postgresql://mval:mval_secret@postgres:5432/mval
```

Загружаются 18 правил валидации (FORMAT, SECURITY, COMPLIANCE, THREAT) для фаз REQUEST и ARCHITECTURE.

#### Шаг 6. Проверить работоспособность

```bash
# Health check каждого сервиса
curl http://localhost:8000/health          # Оркестратор
curl http://localhost:8010/health          # Аналитик
curl http://localhost:8020/health          # МВАЛ
curl http://localhost:8030/api/v1/health   # Архитектор
curl http://localhost:8040/health          # Реализация
```

#### Шаг 7. Тестовый запуск пайплайна

```bash
# REST API — одношаговый запрос
curl -X POST http://localhost:8000/pipeline \
  -H "Content-Type: application/json" \
  -d '{"message": "Нужен агент для мониторинга цен на маркетплейсах и отправки алертов в Telegram"}'
```

Для многошагового диалога с уточнениями используйте WebSocket:
```
ws://localhost:8000/ws/pipeline/{session_id}
```

### Конфигурация

Все переменные окружения задаются через `.env` в корне проекта и прокидываются через `docker-compose.yml`.

#### Основные переменные

| Переменная | По умолчанию | Описание |
|---|---|---|
| `YANDEX_API_KEY` | — | API-ключ Yandex Cloud (обязательно) |
| `YANDEX_FOLDER_ID` | — | Folder ID Yandex Cloud (обязательно) |
| `YANDEX_BASE_URL` | `https://llm.api.cloud.yandex.net/v1` | Endpoint Yandex Cloud LLM API |
| `LLM_MODEL_NAME` | `deepseek-v32/latest` | Модель LLM |
| `EMBEDDING_MODEL` | `text-search-doc/latest` | Модель эмбеддингов |
| `EMBEDDING_DIMENSIONS` | `256` | Размерность эмбеддингов |
| `POSTGRES_PASSWORD` | `secret` | Пароль PostgreSQL (пользователь `postgres`) |
| `QDRANT_COLLECTION` | `arch_patterns` | Имя коллекции Qdrant |

### Логирование

Все модули пишут LLM-логи (промпты и ответы) в shared volume `agent_logs` → `/tmp/agent_logs/`:

| Файл | Модуль |
|------|--------|
| `orchestrator.log` | Оркестратор (request/response каждого этапа) |
| `mval_redteam.log` | МВАЛ RedTeam (промпты и ответы LLM) |

### Остановка и очистка

```bash
# Остановить все контейнеры
docker compose down

# Остановить и удалить данные (PostgreSQL, Qdrant, логи)
docker compose down -v
```

### Структура проекта

```
hackathon_ai_agents/
├── docker-compose.yml                # Все сервисы + инфраструктура
├── .env                              # Переменные окружения
├── scripts/
│   ├── init-db.sql                   # Инициализация БД (mval + interview)
│   └── init.sh                       # Скрипт полного запуска
├── modules/
│   ├── orchestrator/                 # Оркестратор (порт 8000)
│   │   ├── Dockerfile
│   │   └── main.py
│   ├── analyst/                      # ИИ Аналитик (порт 8010)
│   │   ├── Dockerfile
│   │   ├── src/analyst/              # Исходный код
│   │   ├── migrations/               # SQL-миграции (auto-apply)
│   │   ├── scripts/                  # Seed-скрипты
│   │   └── tests/
│   ├── mval/                         # МВАЛ (порт 8020 + RedTeam 8021)
│   │   ├── Dockerfile
│   │   ├── Dockerfile.redteam
│   │   ├── src/mval/                 # Исходный код
│   │   ├── migrations/               # SQL-миграции (auto-apply)
│   │   ├── scripts/seed_policies.py  # Seed политик валидации
│   │   └── tests/
│   ├── architect/                    # ИИ Архитектор (порт 8030)
│   │   ├── Dockerfile
│   │   ├── app/                      # Исходный код
│   │   ├── scripts/
│   │   │   ├── inject_patterns.py    # Загрузка паттернов в Qdrant
│   │   │   └── patterns/*.md         # 8 архитектурных паттернов
│   │   └── tests/
│   └── implementor/                  # Реализация — заглушка (порт 8040)
│       ├── Dockerfile
│       └── main.py
└── docs/diagrams/                    # C4-диаграммы (Mermaid)
```
