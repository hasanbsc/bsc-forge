"""BSC Forge — Ana FastAPI Uygulaması"""
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from routers.auth import router as auth_router
from routers.chat import router as chat_router
from routers.models import router as models_router
from routers.products import router as products_router
from services.auth import user_store
from services.chat_history import chat_history
from services.orchestrator import orchestrator
from services.product_store import product_store

logger = logging.getLogger("bsc_forge")

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


async def _warm_orchestrator() -> None:
    """Mistral 7B'yi background'da sıcak tut; keep_alive=30m ile çalışır kalır.

    İlk gerçek kullanıcı isteğinde cold start 30-40s sürmesin diye startup'ta
    arka planda küçük bir analyze çağrısı yapılır.
    """
    try:
        if await orchestrator.available():
            logger.info("Orchestrator warm-up başlatıldı (Mistral 7B)")
            await orchestrator.analyze("merhaba")
            logger.info("Orchestrator hazır")
    except Exception as e:
        logger.warning("Orchestrator warm-up başarısız: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlarken veritabanı tablolarını oluştur."""
    await chat_history.init_db()
    await user_store.init_table()
    await product_store.init_table()
    # Mistral'ı background'da ısıt — startup'ı bloklamaz
    asyncio.create_task(_warm_orchestrator())
    yield


app = FastAPI(
    title="BSC Forge",
    description="Yapay Zeka Ürün Fabrikası — Backend API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — yalnızca yerel geliştirme origin'leri (kimlik bilgili istekler için "*" yasaktır)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Router'ları bağla
app.include_router(auth_router, prefix="/api/auth", tags=["Üyelik"])
app.include_router(chat_router, prefix="/api/chat", tags=["Sohbet"])
app.include_router(models_router, prefix="/api", tags=["Modeller"])
app.include_router(products_router, prefix="/api", tags=["Ürünler"])


@app.get("/health")
async def root():
    """Sağlık kontrolü endpoint'i."""
    return {
        "app": "BSC Forge",
        "version": "0.1.0",
        "status": "çalışıyor",
        "providers": {
            "gemini": settings.is_gemini_configured(),
            "groq": settings.is_groq_configured(),
            "deepseek": settings.is_deepseek_configured(),
        },
    }


# Statik frontend dosyaları — build varsa servis et
if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/")
    async def serve_index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file = STATIC_DIR / full_path
        if file.exists() and file.is_file():
            return FileResponse(file)
        return FileResponse(STATIC_DIR / "index.html")
else:
    @app.get("/")
    async def root():
        return {"app": "BSC Forge", "version": "0.1.0", "status": "çalışıyor"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
    )
