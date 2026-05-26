"""Sağlayıcı hata sınıflandırma ve fallback zinciri (Gemini → Groq → Ollama)."""
import httpx

from config import settings

GROQ_FALLBACK_MODEL = "llama-3.3-70b-versatile"
OLLAMA_FALLBACK_MODEL = "qwen2.5-coder:1.5b"
DEEPSEEK_FALLBACK_MODEL = "deepseek-chat"

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
    """Bulut API kota / rate limit / bakiye hatası mı?"""
    text = str(exc).lower()
    markers = (
        "429",
        "402",  # DeepSeek "Insufficient Balance"
        "resource_exhausted",
        "quota",
        "rate limit",
        "rate_limit",
        "too many requests",
        "exceeded your current quota",
        "insufficient balance",
        "insufficient_balance",
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
    # Tool/function call sorunları (Groq Llama, Gemini MALFORMED_FUNCTION_CALL)
    tool_markers = (
        "tool_use_failed",
        "failed to call a function",
        "malformed_function_call",
        "malformed function call",
        "max_tokens",
        "fallback gerek",
    )
    return any(m in text for m in tool_markers)


def is_auth_error(exc: BaseException | str) -> bool:
    text = str(exc).lower()
    return "api key expired" in text or "invalid api key" in text or "401" in text


def is_error_token(token: str) -> bool:
    return token.strip().startswith("[HATA]")


def fallback_notice(from_provider: str, to_provider: str) -> str:
    """UI'da gösterilecek geçiş mesajı (kota/limit veya tool format sorunu)."""
    return (
        f"⚠️ **{PROVIDER_LABELS.get(from_provider, from_provider)}** yanıt veremedi; "
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
        elif p == "deepseek" and settings.is_deepseek_configured():
            chain.append("deepseek")
        elif p == "ollama":
            chain.append("ollama")
    return chain or ["ollama"]


def model_for_provider(provider: str, preferred: str | None = None) -> str:
    """Provider'a uygun model adını döndür.

    `preferred` farklı bir provider'a aitse (ör. cascade'de Gemini'den Ollama'ya
    geçince `gemini-2.5-flash` korunmuşsa) yok say ve provider'ın varsayılan
    fallback modelini kullan.
    """
    pref = (preferred or "").lower()
    if provider == "gemini":
        if pref.startswith("gemini"):
            return preferred
        return "gemini-2.5-flash"
    if provider == "groq":
        # Groq'ta Llama ailesi + diğer Groq isimleri (mixtral, gemma, qwen ...)
        if pref and (
            "llama" in pref
            or pref.startswith(("mixtral", "gemma", "qwen", "deepseek-r1"))
        ):
            return preferred
        return GROQ_FALLBACK_MODEL
    if provider == "deepseek":
        if pref.startswith("deepseek"):
            return preferred
        return DEEPSEEK_FALLBACK_MODEL
    # ollama — yerel modeller "name:tag" formatında (örn. qwen2.5-coder:1.5b);
    # bulut model adları (gemini-..., deepseek-...) tag içermez ve geçersizdir.
    if preferred and ":" in preferred and not pref.startswith(("gemini", "deepseek-chat", "deepseek-coder")):
        return preferred
    return OLLAMA_FALLBACK_MODEL


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
