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
        priority=10,
    ),
    ModelEntry(
        id="groq-70b",
        provider="groq",
        model="llama-3.3-70b-versatile",
        label="Llama 3.3 70B (Groq)",
        type="cloud",
        tasks=frozenset({TASK_CODING, TASK_ENGLISH, TASK_REASONING, TASK_TURKISH}),
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
    ModelEntry(
        id="deepseek-1",
        provider="deepseek",
        model="deepseek-1.0",
        label="Deepseek 1.0",
        type="cloud",
        tasks=frozenset({TASK_TURKISH, TASK_ENGLISH, TASK_FAST, TASK_REASONING}),
        priority=30,
    ),
]

# ─── Yerel Ollama şablonları (yüklü modellere göre eşleşir) ───
OLLAMA_TEMPLATES: list[ModelEntry] = [
    ModelEntry(
        id="ollama-qwen-coder",
        provider="ollama",
        model="qwen2.5-coder:1.5b",
        label="Qwen 2.5 Coder (Yerel)",
        type="local",
        tasks=frozenset({TASK_CODING, TASK_FILE_OPS}),
        priority=10,
        ollama_name="qwen2.5-coder",
    ),
    ModelEntry(
        id="ollama-llama",
        provider="ollama",
        model="llama3.2:1b",
        label="Llama 3.2 1B (Yerel)",
        type="local",
        tasks=frozenset({TASK_FAST, TASK_ENGLISH, TASK_TURKISH}),
        priority=20,
        ollama_name="llama3.2",
    ),
    ModelEntry(
        id="ollama-mistral",
        provider="ollama",
        model="mistral:7b",
        label="Mistral 7B (Yerel)",
        type="local",
        tasks=frozenset({TASK_TURKISH, TASK_ENGLISH, TASK_REASONING}),
        priority=15,
        ollama_name="mistral",
    ),
    ModelEntry(
        id="ollama-gemma",
        provider="ollama",
        model="gemma2:2b",
        label="Gemma 2 2B (Yerel)",
        type="local",
        tasks=frozenset({TASK_FAST, TASK_TURKISH}),
        priority=25,
        ollama_name="gemma2",
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
