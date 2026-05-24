"""BSC Forge — Akıllı model yönlendirici (görev → en uygun model)."""
from __future__ import annotations

import re
from dataclasses import dataclass

from config import settings
from services.model_registry import (
    ALL_TASKS,
    CLOUD_MODELS,
    ModelEntry,
    TASK_CODING,
    TASK_ENGLISH,
    TASK_FAST,
    TASK_FILE_OPS,
    TASK_REASONING,
    TASK_TURKISH,
    TASK_WEATHER,
    match_ollama_installed,
)
from services.provider_utils import is_ollama_available

# ─── Sınıflandırma sinyalleri ─────────────────────────────

_FILE_SIGNALS = (
    # Türkçe — mutlaka listeleme/görüntüleme niyeti olmalı
    "klasör", "listele", "listeler", "dizin", "içindeki",
    "read_file", "dosyaları göster", "dosyaları listele",
    "proje dosyaları", "proje dizini", "proje klasörü",
    # İngilizce
    "folder", "directory", "list files", "list directory", "show files",
    "read file", "open file", "project files",
)
_CODE_SIGNALS = (
    # Türkçe
    "kod", "fonksiyon", "hata ayıkla", "refactor", "yaz", "oluştur",
    "proje oluştur", "uygulama yaz", "script yaz",
    # İngilizce + evrensel
    "python", "javascript", "typescript", "react", "fastapi", "html", "css",
    "api", "class", "debug", "implement", "sql", "git", "npm", "pip",
    "function", "write code", "fix bug", "unit test", "dockerfile",
    "bash", "shell script", "create project", "build", "website",
)
_WEATHER_SIGNALS = (
    # Türkçe
    "hava durumu", "hava nasıl", "yağmur", "kar yağ", "derece", "sıcaklık",
    # İngilizce
    "weather", "forecast", "meteoroloji", "temperature", "rain", "snow",
)
_REASONING_SIGNALS = (
    # Türkçe
    "karşılaştır", "analiz", "mimari", "tasarla", "neden", "avantaj",
    "dezavantaj", "trade-off", "planla", "strateji", "adım adım açıkla",
    # İngilizce
    "compare", "analyze", "analysis", "architecture", "design", "why",
    "pros and cons", "plan", "strategy", "explain step by step",
)
_TURKISH_CHARS = set("ğıüşöçİĞÜŞÖÇ")

TASK_LABELS_TR = {
    TASK_FILE_OPS: "Dosya / proje",
    TASK_CODING: "Kodlama",
    TASK_TURKISH: "Türkçe sohbet",
    TASK_ENGLISH: "İngilizce sohbet",
    TASK_REASONING: "Derin analiz",
    TASK_WEATHER: "Hava / canlı veri",
    TASK_FAST: "Hızlı sohbet",
}


@dataclass
class RouteDecision:
    task: str
    provider: str
    model: str
    label: str
    reason: str
    entry_id: str

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "task_label": TASK_LABELS_TR.get(self.task, self.task),
            "provider": self.provider,
            "model": self.model,
            "label": self.label,
            "reason": self.reason,
            "entry_id": self.entry_id,
        }


_TR_STOPWORDS = {
    "ve", "veya", "ile", "bir", "bu", "şu", "için", "ben", "sen", "biz", "siz",
    "bana", "sana", "bize", "size", "ona", "onlara", "ne", "nasıl", "neden",
    "kim", "nerede", "nereye", "ama", "fakat", "çünkü", "gibi", "kadar", "ise",
    "değil", "yok", "var", "olarak", "hakkında", "üzerine", "sonra", "önce",
    "bilgi", "yap", "yaz", "ver", "söyle", "açıkla", "anlat", "göster",
}


def _detect_language(text: str) -> str:
    lower = text.lower()
    # Türkçe karakter veya Türkçe stopword varsa Türkçe say
    if any(c in _TURKISH_CHARS for c in text):
        return "tr"
    tokens = re.findall(r"[a-zA-ZğıüşöçİĞÜŞÖÇ']+", lower)
    if any(tok in _TR_STOPWORDS for tok in tokens):
        return "tr"
    en_markers = (
        r"\b(hello|hi|the|and|what|how|why|please|explain|write|code|weather)\b"
    )
    if re.search(en_markers, lower):
        return "en"
    # Çoğunlukla ASCII kelime → İngilizce ihtimali
    if len(tokens) >= 3 and sum(1 for w in tokens if w.isascii()) / len(tokens) > 0.85:
        return "en"
    return "tr"


def classify_task(message: str, history: list[dict] | None = None) -> str:
    """Kural tabanlı görev sınıflandırıcı (API maliyeti: 0)."""
    text = message.lower().strip()
    lang = _detect_language(message)

    if any(s in text for s in _FILE_SIGNALS):
        return TASK_FILE_OPS
    if any(s in text for s in _WEATHER_SIGNALS):
        return TASK_WEATHER
    if any(s in text for s in _CODE_SIGNALS):
        return TASK_CODING
    if any(s in text for s in _REASONING_SIGNALS) or len(message.split()) > 80:
        return TASK_REASONING
    if lang == "en":
        return TASK_ENGLISH
    if lang == "tr":
        return TASK_TURKISH
    return TASK_FAST


class ModelRouter:
    """Katalogdan göreve uygun model seçer."""

    def __init__(self):
        self._catalog: list[ModelEntry] = []
        self._ollama_names: list[str] = []

    async def refresh_catalog(self) -> list[ModelEntry]:
        catalog: list[ModelEntry] = []

        if settings.is_gemini_configured():
            catalog.extend(e for e in CLOUD_MODELS if e.provider == "gemini")
        if settings.is_groq_configured():
            catalog.extend(e for e in CLOUD_MODELS if e.provider == "groq")
        if settings.is_deepseek_configured():
            catalog.extend(e for e in CLOUD_MODELS if e.provider == "deepseek")

        self._ollama_names = []
        if await is_ollama_available():
            self._ollama_names = await self._fetch_ollama_tags()
            catalog.extend(match_ollama_installed(self._ollama_names))

        self._catalog = catalog
        return catalog

    async def _fetch_ollama_tags(self) -> list[str]:
        import httpx

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    return []
                data = r.json()
                return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    def get_catalog(self) -> list[ModelEntry]:
        return list(self._catalog)

    def pick_for_task(self, task: str, prefer_local: bool = False) -> ModelEntry | None:
        candidates = [e for e in self._catalog if task in e.tasks]
        if not candidates:
            candidates = list(self._catalog)
        if not candidates:
            return None

        def sort_key(e: ModelEntry) -> tuple:
            if prefer_local:
                tier = 0 if e.type == "local" else 1
            else:
                tier = 0 if e.type == "cloud" else 1
            return (tier, e.priority)

        candidates.sort(key=sort_key)
        return candidates[0]

    async def route(
        self,
        message: str,
        provider: str | None = None,
        model: str | None = None,
        routing: str = "manual",
        history: list[dict] | None = None,
    ) -> RouteDecision:
        """Manuel veya otomatik model seçimi."""
        if not self._catalog:
            await self.refresh_catalog()

        # Manuel seçim
        if routing != "auto" and provider and provider != "auto":
            for e in self._catalog:
                if e.provider == provider and (not model or e.model == model):
                    return RouteDecision(
                        task="manual",
                        provider=e.provider,
                        model=e.model,
                        label=e.label,
                        reason="Kullanıcı seçimi",
                        entry_id=e.id,
                    )
            return RouteDecision(
                task="manual",
                provider=provider,
                model=model or "",
                label=f"{provider}/{model}",
                reason="Kullanıcı seçimi (katalog dışı)",
                entry_id="manual",
            )

        task = classify_task(message, history)

        # Yaratma/üretme niyeti — bulut tercih edilir
        _creation_signals = (
            "oluştur", "yaz", "yap", "üret", "oluşturun", "kodla", "tasarla",
            "create", "build", "generate", "make", "implement", "write",
        )
        # Düzenleme niyeti — uzun düzenleme bulut, kısa+net düzenleme yerel olabilir
        _edit_signals = (
            "düzenle", "değiştir", "değişiklik", "düzelt", "güncelle", "yenile",
            "ekle", "çıkar", "kaldır", "geliştir", "iyileştir",
            "refactor", "rename", "fix", "edit", "modify", "update", "patch",
        )
        msg_lower = message.lower()
        is_creation = any(s in msg_lower for s in _creation_signals)
        is_edit = any(s in msg_lower for s in _edit_signals)
        word_count = len(message.split())

        # Dosya işlemleri her zaman yerel.
        # Kodlamada **varsayılan bulut**. Yerel yalnızca: belirgin küçük
        # düzenleme + yaratma niyeti yok + kısa istek (< 15 kelime).
        prefer_local = task == TASK_FILE_OPS or (
            task == TASK_CODING
            and is_edit
            and not is_creation
            and word_count < 15
        )

        entry = self.pick_for_task(task, prefer_local=prefer_local)
        if not entry:
            return RouteDecision(
                task=task,
                provider=settings.DEFAULT_PROVIDER,
                model=settings.DEFAULT_MODEL,
                label="Varsayılan",
                reason="Katalog boş; varsayılan model",
                entry_id="default",
            )

        reason = f"Görev: {TASK_LABELS_TR.get(task, task)} → {entry.label}"
        if task == TASK_WEATHER:
            reason += " (canlı hava verisi için ileride weather aracı gerekir)"

        return RouteDecision(
            task=task,
            provider=entry.provider,
            model=entry.model,
            label=entry.label,
            reason=reason,
            entry_id=entry.id,
        )


model_router = ModelRouter()
