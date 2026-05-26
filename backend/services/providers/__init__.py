"""BSC Forge — Ajan sağlayıcı (provider) adaptörleri.

Her LLM sağlayıcısı (Gemini / Groq / DeepSeek / Ollama) için tool-calling adımı
ayrı bir modülde. Ortak veri tipleri `base.py`'de.
"""
from services.providers.base import ToolCall, StepResult
from services.providers.gemini import step_gemini
from services.providers.groq import step_groq, groq_tools_schema
from services.providers.deepseek import step_deepseek
from services.providers.ollama import step_ollama, heuristic_tool_calls

__all__ = [
    "ToolCall",
    "StepResult",
    "step_gemini",
    "step_groq",
    "step_deepseek",
    "step_ollama",
    "heuristic_tool_calls",
    "groq_tools_schema",
]
