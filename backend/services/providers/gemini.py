"""Gemini provider — tool-calling adımı."""
from google import genai
from google.genai import types

from config import settings
from services.providers.base import StepResult, ToolCall
from services.tools import TOOL_SCHEMAS


def _gemini_tools() -> list[types.Tool]:
    declarations = [
        types.FunctionDeclaration(
            name=s["name"],
            description=s["description"],
            parameters=s["parameters"],
        )
        for s in TOOL_SCHEMAS
    ]
    return [types.Tool(function_declarations=declarations)]


def _gemini_contents(messages: list[dict]) -> list[types.Content]:
    contents = []
    for msg in messages:
        role = msg["role"]
        if role == "system":
            role = "user"
        if role not in ("user", "model", "assistant"):
            continue
        gemini_role = "user" if role in ("user", "system") else "model"
        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part(text=msg["content"])],
            )
        )
    return contents


async def step_gemini(messages: list[dict], model: str) -> StepResult:
    if not settings.is_gemini_configured():
        raise RuntimeError("Gemini yapılandırılmamış")

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=model,
        contents=_gemini_contents(messages),
        config=types.GenerateContentConfig(
            tools=_gemini_tools(),
            temperature=0.4,
            # Site/HTML üretimleri kolayca 4-8k token sürüyor; Flash 65k destekler
            max_output_tokens=16384,
        ),
    )

    tool_calls: list[ToolCall] = []
    texts: list[str] = []

    if not response.candidates:
        return StepResult(tool_calls=[], direct_text="[HATA] Gemini boş yanıt döndü.")

    candidate = response.candidates[0]
    # content None olabilir: MAX_TOKENS, SAFETY, RECITATION, MALFORMED_FUNCTION_CALL...
    if candidate.content is None or not candidate.content.parts:
        finish = getattr(candidate, "finish_reason", None)
        reason = getattr(finish, "name", str(finish)) if finish else "bilinmiyor"
        # Fallback'le kurtarılabilecek sebepler — exception fırlat ki
        # cascade (Gemini → Groq → DeepSeek → Ollama) devreye girsin
        fallbackable = {"MALFORMED_FUNCTION_CALL", "MAX_TOKENS", "OTHER", "UNKNOWN"}
        if reason in fallbackable:
            raise RuntimeError(f"Gemini {reason} — fallback gerek")
        # Aksi halde kullanıcıya bilgi (başka modelle çözülemez)
        hint = {
            "SAFETY": "Güvenlik filtresi yanıtı engelledi. İsteği biraz farklı ifade et.",
            "RECITATION": "Model alıntı kısıtına takıldı; isteği yeniden ifade et.",
        }.get(reason, "Yanıt üretilemedi.")
        return StepResult(
            tool_calls=[],
            direct_text=f"[HATA] Gemini yanıt veremedi (sebep: {reason}). {hint}",
        )

    for part in candidate.content.parts:
        if part.function_call:
            fc = part.function_call
            args = dict(fc.args) if fc.args else {}
            tool_calls.append(ToolCall(name=fc.name, args=args))
        elif part.text:
            texts.append(part.text)

    direct = "\n".join(texts).strip() or None
    return StepResult(tool_calls=tool_calls, direct_text=direct if not tool_calls else None)
