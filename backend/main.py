"""BSC Forge — Ana FastAPI Uygulaması"""
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers.chat import router as chat_router

app = FastAPI(
    title="BSC Forge",
    description="Yapay Zeka Ürün Fabrikası — Backend API",
    version="0.1.0",
)

# CORS — Frontend'in backend'e erişebilmesi için
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Router'ları bağla
app.include_router(chat_router, prefix="/api/chat", tags=["Sohbet"])


@app.get("/")
async def root():
    """Sağlık kontrolü endpoint'i."""
    return {
        "app": "BSC Forge",
        "version": "0.1.0",
        "status": "çalışıyor",
        "providers": {
            "gemini": settings.is_gemini_configured(),
            "groq": settings.is_groq_configured(),
        },
    }


@app.get("/api/models")
async def list_models():
    """Kullanılabilir model sağlayıcılarını listele."""
    models = []

    if settings.is_gemini_configured():
        models.append({
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "label": "Gemini 2.5 Flash",
            "type": "cloud",
            "status": "aktif",
        })

    if settings.is_groq_configured():
        models.extend([
            {
                "provider": "groq",
                "model": "llama-3.3-70b-versatile",
                "label": "Llama 3.3 70B (Groq)",
                "type": "cloud",
                "status": "aktif",
            },
            {
                "provider": "groq",
                "model": "llama-3.1-8b-instant",
                "label": "Llama 3.1 8B (Groq)",
                "type": "cloud",
                "status": "aktif",
            },
        ])

    # Ollama (yerel) — her zaman listede, bağlantı durumunu kontrol eder
    models.append({
        "provider": "ollama",
        "model": "qwen2.5-coder:1.5b",
        "label": "Qwen 2.5 Coder 1.5B (Yerel)",
        "type": "local",
        "status": "yapılandırılmadı",
    })

    return {"models": models, "default": settings.DEFAULT_MODEL}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )
