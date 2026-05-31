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
from services.orchestrator import orchestrator

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
    # Yeni: orkestrasyon katmanı kararı
    layer: str = "analysis"  # "production" (uzun üretim, yerel tercih) | "analysis" (bulut tercih)
    complexity: str = "medium"  # "simple" | "medium" | "complex"
    source: str = "heuristic"  # "heuristic" | "orchestrator" (yerel LLM fallback)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "task_label": TASK_LABELS_TR.get(self.task, self.task),
            "provider": self.provider,
            "model": self.model,
            "label": self.label,
            "reason": self.reason,
            "entry_id": self.entry_id,
            "layer": self.layer,
            "complexity": self.complexity,
            "source": self.source,
        }


# ─── Katman (layer) heuristiği — sıfır gecikme ön karar ─────

# Uzun çıktı isteyen üretim niyetleri → yerel tercih edilir (kota tasarrufu + kalite)
_PRODUCTION_SIGNALS_STRICT = (
    # Site / web üretimi
    "site yap", "site oluştur", "website", "web sitesi", "landing page",
    "homepage", "ana sayfa", "tek sayfa",
    # HTML/CSS/JS açık ifade
    "html dosya", "html sayfa", "html üret", "html oluştur",
    "css dosya", "stylesheet",
    "üç ayrı dosya", "birden fazla dosya", "modüler dosya",
    "ayrı dosya", "ayrı bir dosya",
    # Codex tarzı tetikleyiciler
    "index.html", "style.css", "script.js",
)
_PRODUCTION_KEYWORDS = (
    "site", "sayfa", "html", "css", "javascript", "landing", "anasayfa",
    "menü", "navbar", "hero", "footer", "frontend", "template",
)
_PRODUCTION_VERBS = (
    "oluştur", "yap", "üret", "yaz", "tasarla", "kodla", "geliştir",
    "build", "create", "generate", "make", "design",
)

_ANALYSIS_SIGNALS = (
    # Türkçe
    "karşılaştır", "nedir", "ne demek", "ne anlama",
    "neden", "niçin", "açıkla", "anlat", "öner",
    "fark nedir", "fark var", "ne fark",
    # İngilizce
    "compare", "explain", "what is", "what does", "why", "difference between",
)


def detect_layer(message: str, history: list[dict] | None = None) -> tuple[str, str]:
    """
    Mesajı 'production' (üretim) veya 'analysis' (analiz) katmanına yerleştirir.

    Karmaşıklık: simple (< 8 kelime, soru), medium (varsayılan), complex (> 30 kelime).
    Belirsiz mesajlar için history bağlamına bakılır — son asistan mesajında
    bir dosya yazılmışsa devam mesajı muhtemelen üretim devamıdır.
    """
    text = message.lower().strip()
    word_count = len(message.split())

    # Karmaşıklık tahmini
    if word_count < 8:
        complexity = "simple"
    elif word_count > 30:
        complexity = "complex"
    else:
        complexity = "medium"

    # 1) Strict üretim ifadeleri (kesin işaret)
    if any(s in text for s in _PRODUCTION_SIGNALS_STRICT):
        return "production", complexity

    # 2) Üretim fiili + üretim anahtar kelimesi birlikte
    has_verb = any(v in text for v in _PRODUCTION_VERBS)
    has_keyword = any(k in text for k in _PRODUCTION_KEYWORDS)
    if has_verb and has_keyword:
        return "production", complexity

    # 3) Açık analiz sinyali
    if any(s in text for s in _ANALYSIS_SIGNALS):
        return "analysis", complexity

    # 4) Belirsiz kısa devam mesajı + history'de son asistan mesajı dosya
    #    yazımı içeriyor → devam = üretim
    if word_count < 8 and history:
        for msg in reversed(history):
            if msg.get("role") != "assistant":
                continue
            content = (msg.get("content") or "").lower()
            if (
                "kaydedildi" in content
                or "oluşturuldu" in content
                or "güncellendi" in content
                or ".html" in content
                or ".css" in content
                or ".js" in content
            ):
                return "production", complexity
            break

    return "analysis", complexity


_TR_STOPWORDS = {
    # Bağlaç / edat
    "ve", "veya", "ile", "ama", "fakat", "çünkü", "gibi", "kadar", "ise",
    "olarak", "hakkında", "üzerine", "sonra", "önce", "ki", "de", "da",
    # Zamir / işaret
    "bir", "bu", "şu", "o", "ben", "sen", "biz", "siz", "onlar",
    "bana", "sana", "bize", "size", "ona", "onlara", "bunu", "şunu", "onu",
    "buna", "şuna", "bunlar", "şunlar", "kendi", "kendin", "kendisi",
    # Soru / belirteç
    "ne", "nasıl", "neden", "kim", "nerede", "nereye", "hangi", "kaç", "niye",
    # Yaygın fiiller / fiil çekimleri (düzenleme bağlamı için kritik)
    "yap", "yaz", "ver", "söyle", "açıkla", "anlat", "göster", "et", "ol",
    "yapma", "yapar", "yaparsın", "yaparım", "yapalım", "yaptın", "yaptım",
    "değiştir", "düzelt", "güncelle", "yenile", "ekle", "çıkar", "kaldır",
    "iyileştir", "geliştir", "getir", "getirir", "getirin", "ediyor", "edilen",
    "olan", "olacak", "oldu", "olur", "olmuş",
    # Sıfat / zarf
    "daha", "iyi", "kötü", "büyük", "küçük", "az", "çok", "her", "tüm",
    "bütün", "biraz", "şimdi", "yine", "tekrar", "yeni", "eski", "hızlı",
    "yavaş", "hep", "bazı", "böyle", "şöyle", "öyle", "lütfen", "tamam",
    # Olumsuzlama
    "değil", "yok", "var", "evet", "hayır",
    # Sık kullanılan isimler (sohbet)
    "bilgi", "dosya", "kod", "site", "sayfa", "şey",
}


def _detect_language(text: str, history: list[dict] | None = None) -> str:
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
    # Çoğunlukla ASCII kelime → İngilizce ihtimali. AMA önce sohbet bağlamına bak:
    # "iyileştir", "değiştir", "düzelt" gibi kısa devam mesajları stopword'lerce
    # yakalanmazsa son kullanıcı mesajındaki dile uy.
    if history:
        for msg in reversed(history):
            if msg.get("role") != "user":
                continue
            prev = msg.get("content") or ""
            if any(c in _TURKISH_CHARS for c in prev):
                return "tr"
            prev_tokens = re.findall(r"[a-zA-ZğıüşöçİĞÜŞÖÇ']+", prev.lower())
            if any(tok in _TR_STOPWORDS for tok in prev_tokens):
                return "tr"
            break  # yalnızca en son user mesajına bak
    if len(tokens) >= 3 and sum(1 for w in tokens if w.isascii()) / len(tokens) > 0.85:
        return "en"
    return "tr"


def classify_task(message: str, history: list[dict] | None = None) -> str:
    """Kural tabanlı görev sınıflandırıcı (API maliyeti: 0)."""
    text = message.lower().strip()
    lang = _detect_language(message, history)

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
        use_orchestrator: bool = False,
    ) -> RouteDecision:
        """Manuel veya otomatik model seçimi.

        `use_orchestrator=True` ise heuristik karar verildikten sonra yerel
        orchestrator modeline danışılır; çelişki varsa orchestrator kararı
        override eder. Maliyet: 1-8 sn (cold start). Default kapalı — UI'dan opt-in.
        """
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
                        layer="analysis",
                        complexity="medium",
                        source="manual",
                    )
            return RouteDecision(
                task="manual",
                provider=provider,
                model=model or "",
                label=f"{provider}/{model}",
                reason="Kullanıcı seçimi (katalog dışı)",
                entry_id="manual",
                layer="analysis",
                complexity="medium",
                source="manual",
            )

        task = classify_task(message, history)
        layer, complexity = detect_layer(message, history)

        # Layer "production" tespit edildi ama task sohbet/genel kaldıysa
        # (örn. "site yap" → CODE_SIGNALS'a düşmedi) → kod görevine yükselt.
        # Böylece üretim isteği kod modeline (Qwen Coder vb.) yönelir.
        if layer == "production" and task in (TASK_TURKISH, TASK_ENGLISH, TASK_FAST):
            task = TASK_CODING

        # Üretim katmanı → yerel modelleri tercih (kota dostu, kalite)
        # Analiz katmanı → bulut modelleri tercih (hızlı, ucuz)
        # Dosya işlemleri her zaman yerel; weather/turkish/english analiz.
        prefer_local = (
            task == TASK_FILE_OPS
            or layer == "production"
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
                layer=layer,
                complexity=complexity,
                source="heuristic",
            )

        # Opsiyonel: yerel orchestrator modeli ile ikincil görüş
        # Yalnızca user opt-in ettiyse — 1-8 sn gecikme maliyeti var.
        source = "heuristic"
        if use_orchestrator:
            decision = await orchestrator.analyze(message)
            if decision is not None:
                # Orchestrator çelişkisi varsa override et
                if decision.layer != layer:
                    layer = decision.layer
                    prefer_local = (
                        task == TASK_FILE_OPS
                        or layer == "production"
                    )
                    entry = self.pick_for_task(task, prefer_local=prefer_local) or entry
                complexity = decision.complexity
                source = "orchestrator"

        layer_tr = "Üretim (yerel tercih)" if layer == "production" else "Analiz (bulut)"
        prefix = "🎼 " if source == "orchestrator" else ""
        reason = (
            f"{prefix}Görev: {TASK_LABELS_TR.get(task, task)} · "
            f"Katman: {layer_tr} → {entry.label}"
        )
        if task == TASK_WEATHER:
            reason += " (canlı hava verisi için ileride weather aracı gerekir)"

        return RouteDecision(
            task=task,
            provider=entry.provider,
            model=entry.model,
            label=entry.label,
            reason=reason,
            entry_id=entry.id,
            layer=layer,
            complexity=complexity,
            source=source,
        )


model_router = ModelRouter()
