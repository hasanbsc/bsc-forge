"""BSC Forge — Konfigürasyon Yönetimi"""
import logging
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

# .env dosyasını yükle
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

logger = logging.getLogger("bsc_forge.config")


def _resolve_jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET", "").strip()
    if secret:
        return secret
    # .env'de JWT_SECRET yoksa rastgele üret — tek bir backend süreci için geçerli.
    # Restart sonrası tokenlar geçersiz olur; üretimde mutlaka .env'e sabit değer yaz.
    logger.warning(
        "JWT_SECRET tanımsız; geçici rastgele bir anahtar kullanılıyor. "
        "Backend yeniden başlatıldığında oturumlar geçersiz olur. "
        ".env dosyasına kalıcı bir JWT_SECRET ekle."
    )
    return secrets.token_urlsafe(64)


class Settings:
    """Uygulama ayarları (.env dosyasından okunur)."""

    # API Anahtarları
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")

    # Ollama
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    # Sunucu
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))

    # Veritabanı
    DB_PATH: str = str(BASE_DIR / "data" / "chat_history.db")

    # Ajan dosya araçları — yalnızca bu kök altına erişim
    WORKSPACE_ROOT: str = str(BASE_DIR)

    # Ajan ReAct döngüsünde en fazla kaç adım atılır.
    # Çoklu dosya akışında modele 4+ adım gerekir; üst sınır kontrolden çıkmayı engeller.
    MAX_AGENT_STEPS: int = int(os.getenv("MAX_AGENT_STEPS", "5"))

    # Varsayılan Model
    DEFAULT_PROVIDER: str = "gemini"
    DEFAULT_MODEL: str = "gemini-2.5-flash"

    # Üyelik / JWT
    JWT_SECRET: str = _resolve_jwt_secret()
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_DAYS: int = int(os.getenv("JWT_EXPIRES_DAYS", "7"))

    def is_gemini_configured(self) -> bool:
        return bool(self.GEMINI_API_KEY)

    def is_groq_configured(self) -> bool:
        return bool(self.GROQ_API_KEY)

    def is_deepseek_configured(self) -> bool:
        return bool(self.DEEPSEEK_API_KEY)


settings = Settings()
