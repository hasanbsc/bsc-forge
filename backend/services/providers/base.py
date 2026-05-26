"""Ortak veri tipleri — tüm provider adaptörleri buradan import eder."""
from dataclasses import dataclass


@dataclass
class ToolCall:
    """LLM'in çağırmak istediği bir araç (ad + argümanlar)."""
    name: str
    args: dict


@dataclass
class StepResult:
    """Bir ajan adımının sonucu.

    - `tool_calls`: bu adımda çalıştırılacak araç çağrıları
    - `direct_text`: araç yok, doğrudan kullanıcıya verilecek metin
    - `quota_fallback` + `fallback_from/to`: bir önceki sağlayıcı düştü, ona geçildi
    """
    tool_calls: list[ToolCall]
    direct_text: str | None = None
    quota_fallback: bool = False
    fallback_from: str | None = None
    fallback_to: str | None = None
