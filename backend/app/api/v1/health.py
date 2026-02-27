from fastapi import APIRouter

from app.core.responses import ok

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    return ok({"status": "ok"})
