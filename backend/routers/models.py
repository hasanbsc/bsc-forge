"""Model kataloğu ve akıllı yönlendirme API."""
from fastapi import APIRouter
from pydantic import BaseModel

from services.model_registry import entry_to_api_dict
from services.model_router import model_router
from services.provider_utils import is_ollama_available

router = APIRouter()


class RouteRequest(BaseModel):
    message: str
    routing: str = "auto"
    provider: str | None = None
    model: str | None = None


@router.get("/models")
async def list_models():
    """Tüm modeller + Otomatik seçenek."""
    catalog = await model_router.refresh_catalog()
    ollama_up = await is_ollama_available()

    models = [
        {
            "id": "auto",
            "provider": "auto",
            "model": "auto",
            "label": "Otomatik (Akıllı)",
            "type": "router",
            "tasks": [],
            "status": "aktif",
        }
    ]

    for entry in catalog:
        status = "aktif"
        if entry.type == "local" and not ollama_up:
            status = "kapalı — ollama serve"
        models.append(entry_to_api_dict(entry, status))

    return {
        "models": models,
        "default": "auto",
        "routing": {
            "mode": "rule_based",
            "description": "Görev tipine göre model seçimi (kodlama, TR, EN, dosya, …)",
            "doc": "/docs/MODEL-ROUTING.md",
        },
    }


@router.post("/route")
async def route_message(body: RouteRequest):
    """Bir mesaj için hangi modelin seçileceğini önizle."""
    decision = await model_router.route(
        message=body.message,
        provider=body.provider,
        model=body.model,
        routing=body.routing,
    )
    return decision.to_dict()
