"""Prospecção dashboard API, montada pelo Hermes em /api/plugins/prospeccao/."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health():
    return {"ok": True}
