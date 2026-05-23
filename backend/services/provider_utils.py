"""Sağlayıcı hata sınıflandırma ve fallback zinciri (Gemini → Groq → Ollama)."""
import httpx

from config import settings

GROQ_FALLBACK_MODEL = "llama-3.3-70b-versatile"
OLLAMA_FALLBACK_MODEL = "qwen2.5-coder:1.5b"
DEEPSEEK_FALLBACK_MODEL = "deepseek-1.0"

# Kota/limit dolunca denenecek sıra
FALLBACK_CHAIN = ("gemini", "groq", "deepseek", "ollama")

PROVIDER_LABELS = {
    "gemini": "Gemini",
    "groq": "Groq",
    "deepseek": "Deepseek",
    "ollama": "Ollama (yerel)",
}


def model_active_event(
    provider: str,
    model: str,
    label: str | None = None,
) -> dict:
    """WebSocket: şu an hangi modelin yanıtladığını bildir."""
    display = label or f"{PROVIDER_LABELS.get(provider, provider)} · {model}"
    return {
        "type": "model_active",
        "provider": provider,
        "model": model,
        "label": display,
        "model_type": "local" if provider == "ollama" else "cloud",
    }


def is_quota_or_rate_limit(exc: BaseException | str) -> bool:
    """Bulut API kota veya rate limit hatası mı?"""
    text = str(exc).lower()
    markers = (
        "429",
        "resource_exhausted",
        "quota",
        "rate limit",
        "rate_limit",
        "too many requests",
        "exceeded your current quota",
        "capacity",  # Groq bazen capacity döner
    )
    return any(m in text for m in markers)


def is_fallbackable_error(exc: BaseException | str) -> bool:
    """Bir sonraki sağlayıcıya geçilebilir mi?"""
    text = str(exc).lower()
    if is_quota_or_rate_limit(text):
        return True
    # Geçici sunucu hataları
    if any(x in text for x in ("503", "502", "504", "unavailable", "overloaded")):
        return True
    # Groq/Llama bazen tool çağrısı formatını bozar (400 tool_use_failed) — fallback'le
    return "tool_use_failed" in text or "failed to call a function" in text


def is_auth_error(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    return "api key expired" in text or "invalid api key" in text or "401" in text


def is_error_token(token: str) -> bool:
    return token.strip().startswith("[HATA]")


def fallback_notice(from_provider: str, to_provider: str) -> str:
    """UI'da gösterilecek geçiş mesajı."""
    return (
        f"⚠️ **{PROVIDER_LABELS.get(from_provider, from_provider)}** kotası/limiti doldu; "
        f"**{PROVIDER_LABELS.get(to_provider, to_provider)}** ile devam ediliyor."
    )


def cascade_from(start: str) -> list[str]:
    """Seçilen sağlayıcıdan başlayarak fallback zinciri."""
    if start in FALLBACK_CHAIN:
        candidates = list(FALLBACK_CHAIN[FALLBACK_CHAIN.index(start) :])
    else:
        candidates = [start]

    chain: list[str] = []
    for p in candidates:
        if p == "gemini" and settings.is_gemini_configured():
            chain.append("gemini")
        elif p == "groq" and settings.is_groq_configured():
            chain.append("groq")
        elif p == "ollama":
            chain.append("ollama")
    return chain or ["ollama"]


def model_for_provider(provider: str, preferred: str | None = None) -> str:
    if provider == "gemini":
        return preferred or "gemini-2.5-flash"
    if provider == "groq":
        return preferred if preferred and "llama" in preferred else GROQ_FALLBACK_MODEL
    if provider == "deepseek":
        return preferred or DEEPSEEK_FALLBACK_MODEL
    return preferred or OLLAMA_FALLBACK_MODEL


async def is_ollama_available() -> bool:
    """Ollama sunucusu ayakta mı?"""
    url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(url)
            return r.status_code == 200
    except Exception:
        return False


def friendly_provider_error(exc: BaseException, provider: str) -> str:
    """Kullanıcıya gösterilecek kısa Türkçe hata."""
    raw = str(exc)
    if is_quota_or_rate_limit(raw):
        if provider == "gemini":
            return (
                "**Gemini ücretsiz kota doldu** (günde ~20 istek). "
                "Sistem otomatik olarak Groq veya yerel modele geçmeyi dener."
            )
        if provider == "groq":
            return (
                "**Groq kotası/limiti doldu.** "
                "Ollama yerel model çalışıyorsa ona geçilir (`ollama serve`)."
            )
        return f"**{provider} kota/rate limit:** Lütfen biraz bekleyip tekrar dene."
    if is_auth_error(raw):
        return (
            "**API anahtarı geçersiz veya süresi dolmuş.** "
            "`.env` dosyasını güncelle ve backend'i yeniden başlat (`python3 main.py`)."
        )
    return f"**{provider} hatası:** {raw[:400]}"
