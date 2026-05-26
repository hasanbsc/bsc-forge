"""DeepSeek provider — tool-calling adımı (OpenAI-uyumlu HTTP API)."""
import json

import httpx

from config import settings
from services.provider_utils import is_fallbackable_error
from services.providers.base import StepResult, ToolCall
from services.providers.groq import groq_tools_schema  # OpenAI şeması — aynı format


DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"


async def step_deepseek(messages: list[dict], model: str) -> StepResult:
    if not settings.is_deepseek_configured():
        return StepResult(tool_calls=[], direct_text=None)

    ds_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in messages
        if m["role"] in ("system", "user", "assistant")
    ]

    headers = {
        "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": ds_messages,
        "tools": groq_tools_schema(),
        "tool_choice": "auto",
        "temperature": 0.4,
        "max_tokens": 4096,
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
            if response.status_code != 200:
                body = response.text
                err = f"Deepseek HTTP {response.status_code}: {body[:300]}"
                if is_fallbackable_error(err):
                    raise RuntimeError(err)
                return StepResult(tool_calls=[], direct_text=f"[HATA] {err}")
            data = response.json()
    except httpx.HTTPError as e:
        raise RuntimeError(f"Deepseek bağlantı hatası: {e}") from e
    except Exception as e:
        if is_fallbackable_error(e):
            raise
        return StepResult(tool_calls=[], direct_text=f"[HATA] Deepseek: {e}")

    choices = data.get("choices") or []
    if not choices:
        return StepResult(tool_calls=[], direct_text=None)
    msg = choices[0].get("message", {}) or {}

    tool_calls: list[ToolCall] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        raw_args = fn.get("arguments") or "{}"
        try:
            args = (
                json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            )
        except json.JSONDecodeError:
            args = {}
        name = fn.get("name") or ""
        if name:
            tool_calls.append(ToolCall(name=name, args=args))

    direct = (msg.get("content") or "").strip() or None
    return StepResult(
        tool_calls=tool_calls,
        direct_text=direct if not tool_calls else None,
    )
