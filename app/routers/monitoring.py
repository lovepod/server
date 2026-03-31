from fastapi import APIRouter

router = APIRouter(prefix="/v1/monitoring", tags=["monitoring"])


@router.get("/heartbeat")
def heartbeat() -> str:
    return "Hearts Still Beating"
