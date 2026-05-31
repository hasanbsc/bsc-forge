"""BSC Forge — Model kataloğu (yetenek etiketleri + sağlayıcı)."""
from __future__ import annotations

from dataclasses import dataclass, field

# Görev tipleri (router çıktısı)
TASK_FILE_OPS = "file_ops"
TASK_CODING = "coding"
TASK_TURKISH = "turkish"
TASK_ENGLISH = "english"
TASK_REASONING = "reasoning"
TASK_WEATHER = "weather"
TASK_FAST = "fast"

ALL_TASKS = (
    TASK_FILE_OPS,
    TASK_CODING,
    TASK_TURKISH,
    TASK_ENGLISH,
    TASK_REASONING,
    TASK_WEATHER,
    TASK_FAST,
)


@dataclass(frozen=True)
class ModelEntry:
    id: str
    provider: str
    model: str
    label: str
    type: str  # cloud | local
    tasks: frozenset[str]
    priority: int = 50  # Aynı görevde düşük = önce dene
    ollama_name: str | None = None  # Ollama'daki gerçek tag


# ─── Bulut modelleri (API key) ─────────────────────────────
# priority: düşük sayı = önce tercih edilir (aynı görev içinde sıralama)
CLOUD_MODELS: list[ModelEntry] = [
    ModelEntry(
        id="gemini-flash",
        provider="gemini",
        model="gemini-2.5-flash",
        label="Gemini 2.5 Flash",
        type="cloud",
        tasks=frozenset({
            TASK_TURKISH, TASK_ENGLISH, TASK_FAST, TASK_REASONING, TASK_WEATHER,
            TASK_CODING, TASK_FILE_OPS,
        }),
        # Tool calling'de en güvenilir + free tier 1500 RPD — kodlamada da öne al
        priority=4,
    ),
    ModelEntry(
        id="deepseek-coder",
        provider="deepseek",
        model="deepseek-coder",
        label="DeepSeek Coder",
        type="cloud",
        tasks=frozenset({TASK_CODING, TASK_FILE_OPS}),
        # DeepSeek ücretli (free tier yok). Otomatik routing'in tercih
        # etmemesi için priority yüksek; manuel seçim için katalogda kalır.
        priority=90,
    ),
    ModelEntry(
        id="gemini-pro",
        provider="gemini",
        model="gemini-2.5-pro",
        label="Gemini 2.5 Pro",
        type="cloud",
        tasks=frozenset({
            TASK_CODING, TASK_REASONING, TASK_FILE_OPS,
        }),
        # Free tier'de çok kısıtlı (5 RPM, ~50 RPD) — yalnızca manuel seçimle gelsin
        priority=80,
    ),
    ModelEntry(
        id="deepseek-chat",
        provider="deepseek",
        model="deepseek-chat",
        label="DeepSeek Chat",
        type="cloud",
        tasks=frozenset({TASK_TURKISH, TASK_ENGLISH, TASK_FAST, TASK_REASONING}),
        priority=90,  # Ücretli — yalnızca manuel seçim için
    ),
    ModelEntry(
        id="groq-70b",
        provider="groq",
        model="llama-3.3-70b-versatile",
        label="Llama 3.3 70B (Groq)",
        type="cloud",
        tasks=frozenset({TASK_CODING, TASK_ENGLISH, TASK_REASONING, TASK_TURKISH}),
        # Tool calling güvenilirliği Gemini'den düşük (function tag'leri metne
        # yazabiliyor) — Gemini Flash kotaya takılırsa fallback olarak kalsın
        priority=20,
    ),
    ModelEntry(
        id="groq-8b",
        provider="groq",
        model="llama-3.1-8b-instant",
        label="Llama 3.1 8B (Groq)",
        type="cloud",
        tasks=frozenset({TASK_FAST, TASK_ENGLISH}),
        priority=5,
    ),
]

# ─── Yerel Ollama şablonları (yüklü modellere göre eşleşir) ───
# Donanım 7B sınıfı modellerde zorlandığı için katalog 3B ve altı modellere
# odaklı tutulur. Yeni model eklemek için Ollama'da pull edip buraya entry
# ekleyin (id + ollama_name tag'i eşleşmeli).
OLLAMA_TEMPLATES: list[ModelEntry] = [
    ModelEntry(
        id="ollama-qwen-coder-3b",
        provider="ollama",
        model="qwen2.5-coder:3b",
        label="Qwen 2.5 Coder 3B (Yerel)",
        type="local",
        tasks=frozenset({TASK_CODING, TASK_FILE_OPS}),
        priority=8,
        ollama_name="qwen2.5-coder:3b",
    ),
    ModelEntry(
        id="ollama-qwen-coder-1_5b",
        provider="ollama",
        model="qwen2.5-coder:1.5b",
        label="Qwen 2.5 Coder 1.5B (Yerel)",
        type="local",
        tasks=frozenset({TASK_CODING, TASK_FILE_OPS}),
        priority=12,
        ollama_name="qwen2.5-coder:1.5b",
    ),
    ModelEntry(
        id="ollama-llama3.2-3b",
        provider="ollama",
        model="llama3.2:3b",
        label="Llama 3.2 3B (Yerel)",
        type="local",
        tasks=frozenset({TASK_FAST, TASK_TURKISH, TASK_ENGLISH, TASK_REASONING}),
        priority=15,
        ollama_name="llama3.2:3b",
    ),
]


def match_ollama_installed(installed_names: list[str]) -> list[ModelEntry]:
    """Yüklü Ollama modellerini şablonlarla eşleştir."""
    matched: list[ModelEntry] = []
    used: set[str] = set()
    lower_installed = [n.lower() for n in installed_names]

    for tpl in OLLAMA_TEMPLATES:
        key = (tpl.ollama_name or tpl.model).lower()
        for name in lower_installed:
            if key in name and name not in used:
                matched.append(
                    ModelEntry(
                        id=tpl.id,
                        provider=tpl.provider,
                        model=name if ":" in name else tpl.model,
                        label=f"{tpl.label.split('(')[0].strip()} ({name})",
                        type="local",
                        tasks=tpl.tasks,
                        priority=tpl.priority,
                        ollama_name=tpl.ollama_name,
                    )
                )
                used.add(name)
                break

    # Hiç eşleşme yoksa ilk yüklü modeli genel yerel olarak ekle
    if not matched and installed_names:
        n = installed_names[0]
        matched.append(
            ModelEntry(
                id="ollama-generic",
                provider="ollama",
                model=n,
                label=f"Yerel: {n}",
                type="local",
                tasks=frozenset({TASK_FAST, TASK_CODING, TASK_TURKISH}),
                priority=99,
            )
        )
    return matched


def entry_to_api_dict(entry: ModelEntry, status: str = "aktif") -> dict:
    return {
        "id": entry.id,
        "provider": entry.provider,
        "model": entry.model,
        "label": entry.label,
        "type": entry.type,
        "tasks": sorted(entry.tasks),
        "status": status,
    }
