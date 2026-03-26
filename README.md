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

## Конфигурация

Через переменные окружения или `.env` файл:

| Переменная | По умолчанию | Описание |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API endpoint |
| `LLM_MODEL` | `qwen3.5:9b` | Модель LLM |
| `LLM_TEMPERATURE` | `0.2` | Температура генерации |
| `EMBEDDING_MODEL` | `nomic-embed-text` | Модель эмбеддингов |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `QDRANT_COLLECTION` | `arch_patterns` | Имя коллекции |
| `QDRANT_TOP_K` | `8` | Количество паттернов из RAG |
| `MAX_RETRIES` | `3` | Максимум retry-итераций |
| `VALIDATION_SCORE_THRESHOLD` | `0.7` | Порог одобрения (0.0–1.0) |

## Структура проекта

```
app/
├── main.py                          # FastAPI app + lifespan
├── config.py                        # Pydantic Settings
├── api/v1/routes.py                 # POST /generate, GET /health
├── schemas/
│   ├── requests.py                  # GenerateRequest
│   └── responses.py                 # Component, DataFlow, ArchitectureDraft,
│                                    # ValidationResult, GenerateResponse
├── agents/
│   ├── state.py                     # AgentState TypedDict
│   ├── graph.py                     # LangGraph StateGraph + conditional edges
│   └── nodes/
│       ├── rag_retriever.py         # Node 1: Qdrant RAG
│       ├── pattern_selector.py      # Node 2: LLM выбор паттернов
│       ├── component_architect.py   # Node 3: LLM проектирование компонентов
│       ├── integration_designer.py  # Node 4: LLM потоки данных
│       ├── diagram_synthesizer.py   # Node 5: Python — Mermaid + YAML
│       └── arch_validator.py        # Node 6: LLM валидация
├── rag/client.py                    # Qdrant async client
└── llm/
    ├── client.py                    # ChatOllama factory
    └── json_utils.py               # Робастный парсинг JSON из LLM
scripts/
├── inject_patterns.py               # Инжекция паттернов в Qdrant
└── patterns/*.md                    # 8 архитектурных паттернов (frontmatter + markdown)
docs/diagrams/
├── c2-container.mmd                 # C4 Container: место модуля в системе V3
├── c3-component-architect.mmd       # C4 Component: внутренняя архитектура модуля
└── c4-code-graph.mmd               # State Diagram: LangGraph flow
tests/
├── test_nodes.py                    # Unit-тесты (diagram_synthesizer)
├── test_api.py                      # API-тесты (mocked graph)
└── test_e2e.py                      # E2E + бенчмарки (Ollama + Qdrant)
```

## Запуск

```bash
# 1. Зависимости
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Инфраструктура
docker compose up qdrant -d
# Ollama должен быть запущен с моделями:
ollama pull qwen3.5:9b
ollama pull nomic-embed-text

# 3. Инжекция паттернов
python scripts/inject_patterns.py

# 4. Запуск
uvicorn app.main:app --reload

# 5. Проверка
curl http://localhost:8000/api/v1/health
curl -X POST http://localhost:8000/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"user_request": "Нужен агент для мониторинга цен и отправки алертов в Telegram"}'
```

## Тестирование

```bash
# Unit + API тесты (не требуют Ollama)
pytest tests/test_nodes.py tests/test_api.py -v

# E2E тесты с бенчмарками (требуют запущенные Ollama + Qdrant)
pytest tests/test_e2e.py -v -s
```

## Интеграция с другими модулями

### Для Модуля Валидации (вызывающая сторона)

1. Отправить `POST /api/v1/generate` с проверенным запросом
2. Проверить `response.status`:
   - `"success"` — архитектура одобрена, забрать `response.architecture`
   - `"max_retries_exceeded"` — архитектура не прошла валидацию за N итераций, но `response.architecture` содержит последний черновик
   - `"error"` — HTTP 500, pipeline сломался
3. При отклонении архитектуры — можно повторно вызвать с уточнённым `user_request` или дополнительным `context`

### Для Модуля Реализации (потребитель результата)

Ключевые поля из `ArchitectureDraft`:
- `components[]` — список компонентов с типами, технологиями и зависимостями
- `data_flows[]` — граф связей между компонентами с протоколами
- `mermaid_diagram` — визуализация (можно рендерить через Mermaid)
- `yaml_spec` — машиночитаемая спецификация
- `primary_pattern` + `patterns_used` — контекст архитектурных решений

### Docker Compose (для интеграции)

Сервис `app` доступен на порту 8000. При добавлении в общий docker-compose:

```yaml
architecture_agent:
  build:
    context: ./hackathon_ai_agents
    dockerfile: Dockerfile
  ports:
    - "8000:8000"
  environment:
    QDRANT_URL: http://qdrant:6333
    OLLAMA_BASE_URL: http://ollama:11434
  depends_on:
    qdrant:
      condition: service_healthy
```

## Бенчмарки (qwen3.5:9b, GPU)

| Узел | Время |
|------|-------|
| RAG Retriever (Qdrant) | ~0.03s |
| Pattern Selector (LLM) | ~2.7s |
| Component Architect (LLM) | ~12.3s |
| Integration Designer (LLM) | ~10s |
| Diagram Synthesizer (Python) | ~0.002s |
| Architecture Validator (LLM) | ~7s |
| **Полный пайплайн** | **~32–45s** |
