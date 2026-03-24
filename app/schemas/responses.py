from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    LLM_AGENT = "llm_agent"
    TOOL = "tool"
    MEMORY = "memory"
    ORCHESTRATOR = "orchestrator"
    API_GATEWAY = "api_gateway"
    DATABASE = "database"
    QUEUE = "queue"
    EXTERNAL = "external"


class Component(BaseModel):
    id: str = Field(..., description="Уникальный идентификатор компонента (snake_case)")
    name: str = Field(..., description="Человекочитаемое название")
    type: ComponentType
    description: str = Field(..., description="Что делает этот компонент")
    technology: str | None = Field(None, description="Конкретная технология, например FastAPI, Qdrant")
    dependencies: list[str] = Field(default_factory=list, description="Список id компонентов, от которых зависит")


class DataFlow(BaseModel):
    from_id: str = Field(..., description="id компонента-источника")
    to_id: str = Field(..., description="id компонента-получателя")
    label: str = Field(..., description="Краткое описание передаваемых данных")
    protocol: str | None = Field(None, description="Протокол: HTTP, gRPC, AMQP и т.д.")


class ArchitectureDraft(BaseModel):
    title: str
    description: str
    primary_pattern: str = Field(..., description="Основной архитектурный паттерн")
    patterns_used: list[str] = Field(default_factory=list, description="Все применённые паттерны")
    components: list[Component]
    data_flows: list[DataFlow]
    mermaid_diagram: str = Field(..., description="Готовая Mermaid C4-диаграмма")
    yaml_spec: str = Field(..., description="YAML-представление архитектуры")
    deployment_notes: str | None = None


class ValidationResult(BaseModel):
    approved: bool
    score: float = Field(..., ge=0.0, le=1.0)
    scores: dict[str, float] = Field(
        default_factory=dict,
        description="Оценки по критериям: completeness, correctness, applicability, feasibility",
    )
    feedback: str
    issues: list[str] = Field(default_factory=list)


class GenerateResponse(BaseModel):
    status: Literal["success", "max_retries_exceeded", "error"]
    architecture: ArchitectureDraft | None = None
    validation: ValidationResult | None = None
    iterations: int = Field(..., description="Количество выполненных итераций")
    request_id: str
