"""BSC Forge — Orkestra Şefi (yerel LLM ön analiz katmanı).

Heuristik (model_router.detect_layer) belirsiz kalan durumlarda devreye girer.
Yerel orchestrator modeli (Ollama, varsayılan llama3.2:3b) ile prompt analizi
yapar; karmaşıklık + katman (production/analysis) önerir. Sıcak (keep_alive)
tutulur ki ikinci çağrı hızlı olsun.

Maliyet/UX dengesi:
- İlk çağrı cold start (3B sınıfı CPU'da ~3-8 sn)
- Sonraki çağrılar 1-3 sn (keep_alive sayesinde sıcak)
- Heuristik kesin karar verebiliyorsa orchestrator HİÇ çağrılmaz (sıfır gecikme)
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass

import httpx

from config import settings
from services.provider_utils import is_ollama_available

logger = logging.getLogger("bsc_forge.orchestrator")

KEEP_ALIVE = "30m"
REQUEST_TIMEOUT = 30.0  # saniye — 3B sınıfı için yeterli (timeout politikası ayrıca)

# Few-shot örnekli, sıkı JSON dönüş için optimize edilmiş sistem promptu
_SYSTEM_PROMPT = """Görev sınıflandırıcısın. Kullanıcı isteğini analiz et ve SADECE geçerli JSON döndür.

Şema:
{"task": "site|code|chat|file|math|analysis", "complexity": "simple|medium|complex", "layer": "production|analysis"}

Kurallar:
- HTML/CSS/JS, web sitesi, sayfa üretimi → site, layer=production
- Tek dosya kısa kod snippet → code, layer=analysis
- Sohbet, selamlama → chat, layer=analysis
- Dosya/klasör listele/oku/yaz → file, layer=production
- Matematik (sayısal) → math, layer=production
- Karşılaştırma, açıklama, soru-cevap → analysis, layer=analysis

Örnekler:
İstek: "Kahve dükkanı için site yap" → {"task":"site","complexity":"medium","layer":"production"}
İstek: "Daha iyi hale getir" → {"task":"site","complexity":"medium","layer":"production"}
İstek: "merhaba" → {"task":"chat","complexity":"simple","layer":"analysis"}
İstek: "2+2" → {"task":"math","complexity":"simple","layer":"production"}
İstek: "backend klasörünü listele" → {"task":"file","complexity":"simple","layer":"production"}
İstek: "FastAPI Flask karşılaştır" → {"task":"analysis","complexity":"medium","layer":"analysis"}
"""


@dataclass
class OrchestratorDecision:
    task: str  # site|code|chat|file|math|analysis
    complexity: str  # simple|medium|complex
    layer: str  # production|analysis
    raw: dict


class Orchestrator:
    """Belirsiz isteklerde devreye giren yerel ön-analiz LLM'i.

    `available()` ile Ollama + orchestrator modelinin hazır olup olmadığını kontrol et.
    `analyze(message)` ile karar al — hata/timeout durumunda None döner.
    """

    def __init__(self):
        self._available_cache: bool | None = None

    async def available(self) -> bool:
        """Ollama ayakta ve `settings.ORCHESTRATOR_MODEL` yüklü mü?"""
        if self._available_cache is not None:
            return self._available_cache
        if not await is_ollama_available():
            self._available_cache = False
            return False
        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(url)
                if r.status_code != 200:
                    self._available_cache = False
                    return False
                names = [m.get("name", "") for m in r.json().get("models", [])]
                self._available_cache = settings.ORCHESTRATOR_MODEL in names
        except Exception:
            self._available_cache = False
        return self._available_cache

    def invalidate_cache(self) -> None:
        self._available_cache = None

    async def analyze(self, message: str) -> OrchestratorDecision | None:
        """Mesajı analiz et. Hata/timeout → None.

        Çağıran taraf None alırsa kendi heuristik kararıyla devam eder.
        """
        if not await self.available():
            return None
        if not message or not message.strip():
            return None

        payload = {
            "model": settings.ORCHESTRATOR_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": f"İstek: {message!r}"},
            ],
            "format": "json",
            "stream": False,
            "keep_alive": KEEP_ALIVE,
            "options": {"temperature": 0.0, "num_predict": 80},
        }

        url = f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/chat"
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
                r = await client.post(url, json=payload)
                if r.status_code != 200:
                    logger.warning(
                        "Orchestrator HTTP %d: %s", r.status_code, r.text[:200]
                    )
                    return None
                content = r.json().get("message", {}).get("content", "")
        except (httpx.TimeoutException, asyncio.TimeoutError):
            logger.info("Orchestrator timeout (%.1fs) — heuristik fallback", REQUEST_TIMEOUT)
            return None
        except Exception as e:
            logger.warning("Orchestrator hatası: %s", e)
            return None

        try:
            raw = json.loads(content)
        except json.JSONDecodeError:
            logger.info("Orchestrator JSON parse hatası: %s", content[:200])
            return None

        task = (raw.get("task") or "").lower().strip()
        complexity = (raw.get("complexity") or "medium").lower().strip()
        layer = (raw.get("layer") or "analysis").lower().strip()

        valid_tasks = {"site", "code", "chat", "file", "math", "analysis"}
        if task not in valid_tasks:
            return None
        if complexity not in {"simple", "medium", "complex"}:
            complexity = "medium"
        if layer not in {"production", "analysis"}:
            layer = "analysis"

        return OrchestratorDecision(
            task=task, complexity=complexity, layer=layer, raw=raw
        )


orchestrator = Orchestrator()
