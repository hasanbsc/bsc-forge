"""Ollama provider — yerel modeller.

Ollama API tool-calling desteklemez; basit listeleme isteklerinde
sezgisel (keyword tabanlı) bir araç çağrısı üretiriz. Bu, kota dolduğunda
"backend klasörünü listele" gibi yaygın isteklerin yine de çalışmasını sağlar.
"""
from services.providers.base import StepResult, ToolCall


_LISTING_PHRASES = (
    "klasörü listele", "klasörü göster", "klasörü aç",
    "dosyaları listele", "dosyaları göster",
    "içindekileri listele", "içindekileri göster", "içindeki dosyalar",
    "dizini göster", "dizini listele",
    "list directory", "list files", "show files", "show directory",
    "ls ",
)


def heuristic_tool_calls(user_message: str) -> list[ToolCall]:
    """Bulut kotası bitince yalnızca AÇIK niyetli dosya listeleme isteklerinde yerel araç.

    Açık listeleme niyeti şart — "dosya AÇMA" / "yeni dosya" / "index.html'i güncelle" gibi
    cümleler tetiklememeli. İki kelimelik fiil+nesne kombinasyonu zorunlu.
    """
    msg = (user_message or "").lower()
    if not any(p in msg for p in _LISTING_PHRASES):
        return []
    path = "."
    if "backend" in msg:
        path = "backend"
    elif "frontend" in msg:
        path = "frontend"
    return [ToolCall("list_directory", {"path": path})]


async def step_ollama(messages: list[dict]) -> StepResult:
    """Ollama tool API desteklemez; basit isteklerde sezgisel araç."""
    user_msg = next(
        (m["content"] for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    heuristic = heuristic_tool_calls(user_msg)
    if heuristic:
        return StepResult(tool_calls=heuristic)
    return StepResult(tool_calls=[], direct_text=None)
