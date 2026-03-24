from __future__ import annotations

from fastapi import APIRouter, Depends

from mval.dependencies import get_gateway
from mval.domain.models import ValidationContext, ValidationRequest, ValidationVerdict

router = APIRouter(tags=["validation"])


@router.post("/validate", response_model=ValidationVerdict)
async def validate(
    body: ValidationRequest,
    gateway=Depends(get_gateway),
):
    context = ValidationContext(
        phase=body.phase,
        source_module=body.source_module,
        target_module=body.target_module,
        artifact=body.artifact,
        metadata=body.metadata,
    )
    return await gateway.validate(context)


@router.get("/health")
async def health(gateway=Depends(get_gateway)):
    return await gateway.health()
