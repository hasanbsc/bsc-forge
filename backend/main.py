"""BSC Forge — Ana FastAPI Uygulaması"""
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from config import settings
from routers.chat import router as chat_router
from routers.models import router as models_router
from routers.products import router as products_router
from services.chat_history import chat_history
from services.product_store import product_store

STATIC_DIR = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama başlarken veritabanı tablolarını oluştur."""
    await chat_history.init_db()
    await product_store.init_table()
    yield


app = FastAPI(
    title="BSC Forge",
    description="Yapay Zeka Ürün Fabrikası — Backend API",
    version="0.1.0",
    lifespan=lifespan,
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
