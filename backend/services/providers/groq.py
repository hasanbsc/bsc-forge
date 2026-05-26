"""Groq provider — tool-calling adımı.

`groq_tools_schema()` aynı zamanda DeepSeek tarafından da kullanılır (OpenAI-uyumlu).
"""
import json

from groq import AsyncGroq

from config import settings
from services.provider_utils import is_fallbackable_error
from services.providers.base import StepResult, ToolCall
from services.tools import TOOL_SCHEMAS


def groq_tools_schema() -> list[dict]:
    """OpenAI-uyumlu tool şeması (Groq + DeepSeek aynı formatı kullanır)."""
    return [
        {
            "type": "function",
            "function": {
                "name": s["name"],
                "description": s["description"],
                "parameters": s["parameters"],
            },
        }
        for s in TOOL_SCHEMAS
    ]


async def step_groq(messages: list[dict], model: str) -> StepResult:
    if not settings.is_groq_configured():
        return StepResult(tool_calls=[], direct_text=None)

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    groq_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] in ("system", "user", "assistant")
    ]

    try:
        completion = await client.chat.completions.create(
            model=model,
            messages=groq_messages,
            tools=groq_tools_schema(),
            tool_choice="auto",
            temperature=0.4,
            max_tokens=4096,
        )
    except Exception as e:
        if is_fallbackable_error(e):
            raise
        return StepResult(tool_calls=[], direct_text=f"[HATA] Groq: {e}")

    msg = completion.choices[0].message
    tool_calls: list[ToolCall] = []

    if msg.tool_calls:
        for tc in msg.tool_calls:
            raw_args = tc.function.arguments or "{}"
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(ToolCall(name=tc.function.name, args=args))

    direct = (msg.content or "").strip() or None
    return StepResult(tool_calls=tool_calls, direct_text=direct if not tool_calls else None)
