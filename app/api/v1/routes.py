import uuid

from fastapi import APIRouter, HTTPException

from app.agents.graph import compiled_graph
from app.agents.state import AgentState
from app.rag.client import check_qdrant_health
from app.schemas.requests import GenerateRequest
from app.schemas.responses import ArchitectureDraft, GenerateResponse

router = APIRouter(prefix="/api/v1")


@router.post("/generate", response_model=GenerateResponse)
async def generate_architecture(request: GenerateRequest) -> GenerateResponse:
    request_id = str(uuid.uuid4())

    initial_state: AgentState = {
        "user_request": request.user_request,
        "context": request.context,
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

    try:
        final_state: AgentState = await compiled_graph.ainvoke(initial_state)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent pipeline failed: {e}") from e

    status = "success" if final_state.get("is_approved") else "max_retries_exceeded"

    architecture: ArchitectureDraft | None = None
    if final_state.get("components") and final_state.get("mermaid_diagram"):
        architecture = ArchitectureDraft(
            title=f"Architecture for: {request.user_request[:80]}",
            description=request.user_request,
            primary_pattern=final_state.get("primary_pattern", ""),
            patterns_used=final_state.get("selected_patterns", []),
            components=final_state.get("components") or [],
            data_flows=final_state.get("data_flows") or [],
            mermaid_diagram=final_state.get("mermaid_diagram", ""),
            yaml_spec=final_state.get("yaml_spec", ""),
        )

    return GenerateResponse(
        status=status,
        architecture=architecture,
        validation=final_state.get("validation_result"),
        iterations=final_state.get("iteration_count", 0),
        request_id=request_id,
    )


@router.get("/health")
async def health() -> dict:
    qdrant_ok = await check_qdrant_health()
    return {
        "status": "ok",
        "qdrant": "ok" if qdrant_ok else "unavailable",
    }
