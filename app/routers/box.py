from __future__ import annotations

from fastapi import APIRouter, Depends

from app.deps import get_box_service
from app.schemas import RegisterBoxRequest, RegisterBoxResponse, ValidateBoxRequest, ValidateBoxResponse
from app.services.box_service import BoxService

router = APIRouter(prefix="/v1/box", tags=["box"])


@router.post("/register", response_model=RegisterBoxResponse)
def register_box(
    body: RegisterBoxRequest,
    service: BoxService = Depends(get_box_service),
) -> RegisterBoxResponse:
    return service.register(body)


@router.post("/validate", response_model=ValidateBoxResponse)
def validate_box(
    body: ValidateBoxRequest,
    service: BoxService = Depends(get_box_service),
) -> ValidateBoxResponse:
    return service.validate(body)
