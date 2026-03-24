"""
E2E тесты с бенчмарками через локальный Ollama + Qdrant.

Требования:
  - Ollama запущен на localhost:11434 с моделями qwen3.5:9b и nomic-embed-text
  - Qdrant запущен на localhost:6333 с загруженными паттернами
  - .venv/bin/pytest tests/test_e2e.py -v -s

Бенчмарки: замеряем время каждого узла и полного пайплайна.
"""
import time
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.agents.graph import compiled_graph
from app.agents.state import AgentState
from app.main import app


# ─── Helpers ─────────────────────────────────────────────────

def _initial_state(user_request: str, context: dict | None = None) -> AgentState:
    return {
        "user_request": user_request,
        "context": context,
        "retrieved_patterns": [],
        "selected_patterns": [],
        "primary_pattern": "",
        "pattern_reasoning": "",
        "components": None,
        "data_flows": None,
        "mermaid_diagram": None,
        "yaml_spec": None,
        "validation_result": None,
        "feedback_history": [],
        "messages": [],
        "iteration_count": 0,
        "is_approved": False,
        "error": None,
    }


def _print_benchmark(label: str, duration: float) -> None:
    print(f"  ⏱  {label}: {duration:.2f}s")


# ─── E2E: Full Graph Pipeline ───────────────────────────────

TEST_REQUESTS = [
    "Нужен агент для мониторинга цен на маркетплейсах и отправки алертов в Telegram при снижении цены",
    "Build an AI agent that automatically triages GitHub issues, labels them, and assigns to team members",
    "Создать систему из нескольких агентов для автоматической генерации и проверки юнит-тестов на Python",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("user_request", TEST_REQUESTS, ids=["price-monitor-ru", "github-triage-en", "test-gen-multi-agent"])
async def test_full_pipeline(user_request: str) -> None:
    """E2E: полный пайплайн через LangGraph — от запроса до валидированной архитектуры."""
    state = _initial_state(user_request)

    t0 = time.perf_counter()
    final_state: dict[str, Any] = await compiled_graph.ainvoke(state)
    total_time = time.perf_counter() - t0

    print(f"\n{'='*70}")
    print(f"  Request: {user_request[:60]}...")
    _print_benchmark("Total pipeline", total_time)
    print(f"  Iterations: {final_state.get('iteration_count', 0)}")
    print(f"  Approved: {final_state.get('is_approved', False)}")

    # Валидация результата
    assert final_state.get("retrieved_patterns"), "RAG должен вернуть паттерны"
    assert len(final_state["retrieved_patterns"]) > 0

    assert final_state.get("selected_patterns"), "Pattern selector должен выбрать паттерны"
    assert final_state.get("primary_pattern"), "Должен быть primary pattern"

    assert final_state.get("components"), "Component architect должен спроектировать компоненты"
    assert len(final_state["components"]) >= 2, "Минимум 2 компонента"

    assert final_state.get("data_flows") is not None, "Integration designer должен определить потоки данных"

    assert final_state.get("mermaid_diagram"), "Diagram synthesizer должен создать Mermaid диаграмму"
    assert "C4Component" in final_state["mermaid_diagram"]

    assert final_state.get("yaml_spec"), "Должен быть YAML спек"
    assert "components:" in final_state["yaml_spec"]

    assert final_state.get("validation_result"), "Валидатор должен оценить архитектуру"
    vr = final_state["validation_result"]
    print(f"  Score: {vr.score:.3f}")
    print(f"  Scores: {vr.scores}")
    if vr.issues:
        print(f"  Issues: {vr.issues}")

    # Вывод архитектуры
    print(f"  Pattern: {final_state['primary_pattern']}")
    print(f"  Components ({len(final_state['components'])}):")
    for c in final_state["components"]:
        print(f"    - {c.id} ({c.type.value}): {c.name}")
    print(f"  Data flows ({len(final_state.get('data_flows', []))}):")
    for f in (final_state.get("data_flows") or []):
        print(f"    - {f.from_id} → {f.to_id}: {f.label}")
    print(f"{'='*70}\n")


# ─── E2E: HTTP API ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_api_generate_e2e() -> None:
    """E2E: полный цикл через HTTP POST /api/v1/generate."""
    t0 = time.perf_counter()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=300) as client:
        response = await client.post(
            "/api/v1/generate",
            json={
                "user_request": "Создать AI-агента для автоматического code review с интеграцией в GitHub PR workflow",
            },
        )
    total_time = time.perf_counter() - t0

    print(f"\n{'='*70}")
    print("  API E2E: POST /api/v1/generate")
    _print_benchmark("Total API response", total_time)

    if response.status_code != 200:
        print(f"  Response body: {response.text[:500]}")
    assert response.status_code == 200
    data = response.json()
    print(f"  Status: {data['status']}")
    print(f"  Iterations: {data['iterations']}")
    print(f"  Request ID: {data['request_id']}")

    assert data["status"] in ("success", "max_retries_exceeded")
    assert data["architecture"] is not None
    assert data["architecture"]["mermaid_diagram"]
    assert data["architecture"]["components"]
    assert data["validation"] is not None
    print(f"  Validation score: {data['validation']['score']}")
    print(f"  Components: {len(data['architecture']['components'])}")
    print(f"{'='*70}\n")


# ─── E2E: Individual Node Benchmarks ────────────────────────

@pytest.mark.asyncio
async def test_node_benchmarks() -> None:
    """Бенчмарк каждого узла по отдельности."""
    from app.agents.nodes.arch_validator import validate_architecture_node
    from app.agents.nodes.component_architect import design_components_node
    from app.agents.nodes.diagram_synthesizer import synthesize_diagram_node
    from app.agents.nodes.integration_designer import design_integrations_node
    from app.agents.nodes.pattern_selector import select_patterns_node
    from app.agents.nodes.rag_retriever import retrieve_patterns_node

    state = _initial_state("Нужен чат-бот агент с RAG для ответов на вопросы по документации компании")
    benchmarks: dict[str, float] = {}

    print(f"\n{'='*70}")
    print("  Node-level benchmarks")
    print(f"{'='*70}")

    # Node 1: RAG Retriever
    t0 = time.perf_counter()
    result = await retrieve_patterns_node(state)
    benchmarks["retrieve_patterns"] = time.perf_counter() - t0
    state.update(result)
    _print_benchmark("retrieve_patterns (RAG)", benchmarks["retrieve_patterns"])
    assert len(state["retrieved_patterns"]) > 0

    # Node 2: Pattern Selector
    t0 = time.perf_counter()
    result = await select_patterns_node(state)
    benchmarks["select_patterns"] = time.perf_counter() - t0
    state.update(result)
    _print_benchmark("select_patterns (LLM)", benchmarks["select_patterns"])
    assert len(state["selected_patterns"]) >= 1

    # Node 3: Component Architect
    t0 = time.perf_counter()
    result = await design_components_node(state)
    benchmarks["design_components"] = time.perf_counter() - t0
    state.update(result)
    _print_benchmark("design_components (LLM)", benchmarks["design_components"])
    assert state["components"] and len(state["components"]) >= 2

    # Node 4: Integration Designer
    t0 = time.perf_counter()
    result = await design_integrations_node(state)
    benchmarks["design_integrations"] = time.perf_counter() - t0
    state.update(result)
    _print_benchmark("design_integrations (LLM)", benchmarks["design_integrations"])
    assert state["data_flows"] is not None

    # Node 5: Diagram Synthesizer (deterministic)
    t0 = time.perf_counter()
    result = await synthesize_diagram_node(state)
    benchmarks["synthesize_diagram"] = time.perf_counter() - t0
    state.update(result)
    _print_benchmark("synthesize_diagram (Python)", benchmarks["synthesize_diagram"])
    assert state["mermaid_diagram"]

    # Node 6: Architecture Validator
    t0 = time.perf_counter()
    result = await validate_architecture_node(state)
    benchmarks["validate_architecture"] = time.perf_counter() - t0
    state.update(result)
    _print_benchmark("validate_architecture (LLM)", benchmarks["validate_architecture"])
    assert state["validation_result"]

    # Summary
    total = sum(benchmarks.values())
    llm_total = sum(v for k, v in benchmarks.items() if k != "retrieve_patterns" and k != "synthesize_diagram")

    print(f"\n  {'─'*40}")
    print(f"  Total:        {total:.2f}s")
    print(f"  LLM nodes:    {llm_total:.2f}s ({llm_total/total*100:.0f}%)")
    print(f"  RAG:          {benchmarks['retrieve_patterns']:.2f}s ({benchmarks['retrieve_patterns']/total*100:.0f}%)")
    print(f"  Deterministic: {benchmarks['synthesize_diagram']:.4f}s")
    print(f"{'='*70}\n")
