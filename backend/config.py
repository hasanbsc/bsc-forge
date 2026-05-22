"""BSC Forge — Konfigürasyon Yönetimi"""
import os
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını yükle
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)


class Settings:
    """Uygulama ayarları (.env dosyasından okunur)."""

    # API Anahtarları
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Sunucu
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    # Veritabanı
    DB_PATH: str = str(BASE_DIR / "data" / "chat_history.db")

    # Varsayılan Model
    DEFAULT_PROVIDER: str = "gemini"
    DEFAULT_MODEL: str = "gemini-2.5-flash"

    def is_gemini_configured(self) -> bool:
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY != "buraya-gemini-anahtarini-yaz")

    def is_groq_configured(self) -> bool:
        return bool(self.GROQ_API_KEY and self.GROQ_API_KEY != "buraya-groq-anahtarini-yaz")


settings = Settings()
